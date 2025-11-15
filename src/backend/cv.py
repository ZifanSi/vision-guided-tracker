import logging
import time
import cv2
import torch
from collections import deque
from ultralytics import YOLO
import threading
import queue
import numpy as np
from Xlib import display

logger = logging.getLogger(__name__)


class CVPipeline:
    def __init__(self, device, width, height, fps, weight_path, detection_callback):
        self.cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            raise RuntimeError("Failed to open video device %s" % device)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('U', 'Y', 'V', 'Y'))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_FPS, fps)

        self.model = YOLO(weight_path, task="detect")

        self.running = False
        self._detection_callback = detection_callback
        # internal structures
        self._frames_q = None
        self._results_q = None
        self._stop_event = None
        self._t_capture = None
        self._t_infer = None
        self._t_display = None
        logger.info("CV pipeline initialized")

    def _capture_loop(self):
        while not self._stop_event.is_set():
            ret, frame = self.cap.read()
            frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            if not ret:
                logger.error("Failed to read frame")
                self._stop_event.set()
                break
            if self._frames_q.full():
                try:
                    self._frames_q.get_nowait()
                except queue.Empty:
                    pass
            try:
                self._frames_q.put(frame, timeout=0.01)
            except queue.Full:
                pass

    def _inference_loop(self):
        while not self._stop_event.is_set():
            try:
                frame = self._frames_q.get(timeout=0.1)
            except queue.Empty:
                continue
            results = self.model(frame, device=0, imgsz=640, verbose=False)
            result = results[0]
            # user callback
            try:
                boxes = result.boxes
                if boxes is not None and boxes.shape[0] > 0:
                    confs = boxes.conf  # tensor [N]
                    xyxy = boxes.xyxy  # tensor [N,4]  format: x1,y1,x2,y2

                    max_idx = torch.argmax(confs).item()

                    best_box_xyxy = xyxy[max_idx].tolist()

                    x1, y1, x2, y2 = best_box_xyxy
                    cx = 0.5 * (x1 + x2)
                    cy = 0.5 * (y1 + y2)

                    self._detection_callback((cx, cy))
                else:
                    self._detection_callback(None)
            except Exception as e:
                logger.debug(f"detection_callback error: {e}")
            if self._results_q.full():
                try:
                    self._results_q.get_nowait()
                except queue.Empty:
                    pass
            try:
                self._results_q.put(result, timeout=0.01)
            except queue.Full:
                pass

    def _display_loop(self):
        fps_values = deque(maxlen=30)
        prev_time = time.time()
        window_name = "RoCam"

        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        time.sleep(0.5)

        d = display.Display()
        screen = d.screen()
        screen_w = screen.width_in_pixels
        screen_h = screen.height_in_pixels
        if screen_w <= 0 or screen_h <= 0:
            raise RuntimeError("invalid window size")
        logger.info("Display window size: %dx%d" % (screen_w, screen_h))

        while not self._stop_event.is_set():
            try:
                result = self._results_q.get(timeout=0.2)
            except queue.Empty:
                continue
            annotated = result.plot()
            now = time.time()
            dt = now - prev_time
            prev_time = now
            inst_fps = 1.0 / dt if dt > 0 else 0.0
            fps_values.append(inst_fps)
            avg_fps = sum(fps_values) / len(fps_values) if fps_values else 0.0
            cv2.putText(annotated, f"{avg_fps:.1f} FPS", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2, cv2.LINE_AA)

            h, w = annotated.shape[:2]
            scale = min(screen_w / w, screen_h / h) if (screen_w and screen_h) else 1.0
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            resized = cv2.resize(annotated, (new_w, new_h), interpolation=cv2.INTER_AREA)

            canvas = np.zeros((screen_h, screen_w, 3), dtype=resized.dtype)
            x = (screen_w - new_w) // 2
            y = (screen_h - new_h) // 2
            canvas[y:y + new_h, x:x + new_w] = resized

            cv2.imshow(window_name, resized)
            if cv2.waitKey(1) & 0xFF == 27:
                # ESC
                self._stop_event.set()
                break

    def start(self):
        if self.running:
            return
        self._frames_q = queue.Queue(maxsize=2)
        self._results_q = queue.Queue(maxsize=2)
        self._stop_event = threading.Event()
        self._t_capture = threading.Thread(target=self._capture_loop, daemon=True)
        self._t_infer = threading.Thread(target=self._inference_loop, daemon=True)
        self._t_display = threading.Thread(target=self._display_loop, daemon=True)
        self.running = True
        self._t_capture.start()
        self._t_infer.start()
        self._t_display.start()
        logger.info("CV pipeline started")

    def stop(self):
        if not self.running:
            return
        self._stop_event.set()
        for t in (self._t_display, self._t_infer, self._t_capture):
            if t:
                t.join(timeout=1)
        self.cap.release()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass
        self.running = False
        logger.info("CV pipeline stopped")
