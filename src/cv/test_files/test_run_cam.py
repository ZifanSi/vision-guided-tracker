#!/usr/bin/env python3
"""
Run YOLO detection on a camera stream.

Examples:
  # Webcam 0 with your weights
  python detect_cam.py --weights /path/to/best.pt --source 0

  # RTSP stream, lower conf, save to file
  python detect_cam.py --weights /path/to/best.pt --source rtsp://user:pass@ip/stream --conf 0.25 --save out.mp4

  # Force CPU
  python detect_cam.py --weights /path/to/best.pt --source 0 --device cpu
"""

import argparse
import time
from pathlib import Path

import cv2
import torch
from ultralytics import YOLO


def parse_args():
    p = argparse.ArgumentParser(description="Camera YOLO detector (Ultralytics).")
    p.add_argument("--weights", required=True, help="Path to .pt/.onnx YOLO weights")
    p.add_argument("--source", default="0",
                   help="Camera index (e.g., 0,1) or URL (rtsp/http) or video path")
    p.add_argument("--imgsz", type=int, default=640, help="Inference size")
    p.add_argument("--conf", type=float, default=0.1, help="Confidence threshold")
    p.add_argument("--device", default=None, choices=["cpu", "cuda", None],
                   help="Force device; default auto")
    p.add_argument("--save", default=None, help="Optional output video path (e.g., out.mp4)")
    p.add_argument("--show", action="store_true", help="Show window (on by default if no --save-only)")
    p.add_argument("--save_only", action="store_true", help="Don’t display window, only save")
    p.add_argument("--stride", type=int, default=1, help="Process every Nth frame (performance)")
    return p.parse_args()


def open_source(src_str):
    # Try to parse integer index, else treat as path/URL
    try:
        idx = int(src_str)
        cap = cv2.VideoCapture(idx)
    except ValueError:
        cap = cv2.VideoCapture(src_str)

    return cap


def main():
    args = parse_args()

    # Device selection
    if args.device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = args.device

    # Load model
    model = YOLO(args.weights)
    model.to(device)
    # Optional small boost
    try:
        model.fuse()
    except Exception:
        pass

    names = model.names if hasattr(model, "names") else {}

    # Open source
    cap = open_source(args.source)
    if not cap.isOpened():
        raise RuntimeError(f"Failed to open source: {args.source}")

    # Prepare writer if saving
    writer = None
    if args.save is not None:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        # Probe one frame to get size/fps
        ret, frame = cap.read()
        if not ret:
            raise RuntimeError("Failed to read initial frame.")
        h, w = frame.shape[:2]
        fps_probe = cap.get(cv2.CAP_PROP_FPS)
        if fps_probe is None or fps_probe <= 0:
            fps_probe = 30.0
        Path(args.save).parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(args.save, fourcc, fps_probe, (w, h))
        # Rewind frame into pipeline
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    show_window = (not args.save_only)
    if show_window:
        cv2.namedWindow("YOLO", cv2.WINDOW_NORMAL)

    frame_i = 0
    t0 = time.time()
    fps_smoothed = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_i += 1
        if args.stride > 1 and (frame_i % args.stride) != 0:
            # Still display/save skipped frames unchanged
            out_frame = frame
        else:
            ts = time.time()
            results = model.predict(
                frame,
                imgsz=args.imgsz,
                conf=args.conf,
                device=device,
                verbose=False
            )
            te = time.time()
            inf_dt = te - ts
            fps_inst = 1.0 / max(inf_dt, 1e-6)
            fps_smoothed = fps_inst if fps_smoothed is None else fps_smoothed * 0.9 + fps_inst * 0.1

            # Draw detections on a copy
            out_frame = frame.copy()
            if len(results):
                r = results[0]
                if r.boxes is not None:
                    boxes = r.boxes
                    for i in range(len(boxes)):
                        xyxy = boxes.xyxy[i].tolist()  # [x1,y1,x2,y2]
                        conf = float(boxes.conf[i]) if boxes.conf is not None else 0.0
                        cls_id = int(boxes.cls[i]) if boxes.cls is not None else -1
                        label = names.get(cls_id, str(cls_id))

                        x1, y1, x2, y2 = map(int, xyxy)
                        cv2.rectangle(out_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        txt = f"{label} {conf:.2f}"
                        cv2.putText(out_frame, txt, (x1, max(0, y1 - 6)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2, cv2.LINE_AA)

            # FPS overlay
            if fps_smoothed is not None:
                cv2.putText(out_frame, f"FPS: {fps_smoothed:.1f}  Device: {device}",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)

        # Write/save
        if writer is not None:
            writer.write(out_frame)

        # Show
        if show_window:
            cv2.imshow("YOLO", out_frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):  # ESC or q
                break

    cap.release()
    if writer is not None:
        writer.release()
    if show_window:
        cv2.destroyAllWindows()

    total_time = time.time() - t0
    print(f"Done. Processed {frame_i} frames in {total_time:.2f}s")


if __name__ == "__main__":
    main()
