from typing import Tuple, Optional
import threading
import time
import queue
import logging
from gimbal import GimbalSerial

logger = logging.getLogger(__name__)

class Tracking:
    def __init__(self, gimbal: GimbalSerial, width: int, height: int, k_p: float):
        self._gimbal = gimbal
        self._width = width
        self._height = height
        self._k_p = k_p

        # use a queue of size 1; when full, we will drop the old value
        self._queue: "queue.Queue[Optional[Tuple[float, float]]]" = queue.Queue(maxsize=1)
        self._stop_event = threading.Event()

        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def on_detection(self, center: Optional[Tuple[float, float]]):
        # try to put; if full, drop the old value and put the new one
        try:
            self._queue.put_nowait(center)
        except queue.Full:
            try:
                # drop oldest
                _ = self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(center)
            except queue.Full:
                # if it still fails, just ignore (rare)
                pass

    def _worker(self):
        # consume latest detection from the queue and apply control
        while not self._stop_event.is_set():
            try:
                center = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if center:
                try:
                    cx, cy = center
                    error_x = cx - self._width / 2.0
                    error_y = cy - self._height / 2.0

                    delta_pan = error_x * self._k_p
                    delta_tilt = -error_y * self._k_p

                    current_tilt, current_pan = self._gimbal.measure_deg()
                    # time.sleep(0.01)
                    new_tilt = current_tilt + delta_tilt
                    new_pan = current_pan + delta_pan

                    # clamp ranges
                    new_tilt = max(0.0, min(90.0, new_tilt))
                    new_pan = max(-45.0, min(45.0, new_pan))

                    self._gimbal.move_deg(new_tilt, new_pan)
                    # time.sleep(0.01)
                except Exception as e:
                    logger.error(f"Tracking worker error: {e}")

    def stop(self, timeout: Optional[float] = 1.0):
        self._stop_event.set()
        self._thread.join(timeout)
