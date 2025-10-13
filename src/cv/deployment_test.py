#!/usr/bin/env python3
import argparse, os, sys, time, cv2
from ultralytics import YOLO

def csi_gstreamer(width=1280, height=720, fps=30, flip=0):
    return (
        f"nvarguscamerasrc ! video/x-raw(memory:NVMM), "
        f"width=(int){width}, height=(int){height}, framerate=(fraction){fps}/1 ! "
        f"nvvidconv flip-method={flip} ! video/x-raw, format=(string)BGRx ! "
        f"videoconvert ! video/x-raw, format=(string)BGR ! appsink drop=1"
    )

def open_video_source(src: str):
    if src == "csi":
        return cv2.VideoCapture(csi_gstreamer(), cv2.CAP_GSTREAMER)
    try:
        i = int(src)
        return cv2.VideoCapture(i)        # USB webcam: --source 0
    except ValueError:
        return cv2.VideoCapture(src)      # file/RTSP path

def main():
    ap = argparse.ArgumentParser(description="YOLO quick deploy (Jetson GPU)")
    ap.add_argument("--model", default="yolov8n.pt",
                    help="Path to .pt (PyTorch) or .engine (TensorRT).")
    ap.add_argument("--source", default="0",
                    help="'0' for USB cam, 'csi' for CSI cam, or path/rtsp url.")
    ap.add_argument("--imgsz", type=int, default=640, help="Inference size.")
    ap.add_argument("--conf", type=float, default=0.25, help="Confidence threshold.")
    ap.add_argument("--save", action="store_true", help="Save annotated video to out.mp4")
    ap.add_argument("--show", action="store_true", help="Show live window")
    args = ap.parse_args()

    # Prefer TensorRT if .engine is supplied (no PyTorch needed to run)
    use_trt = args.model.endswith(".engine")
    device = 0 if not use_trt else "cpu"  # Ultralytics handles TRT internally; device is ignored for .engine

    # Load model
    model = YOLO(args.model)

    # Open source
    cap = open_video_source(args.source)
    if not cap.isOpened():
        print(f"ERROR: cannot open source: {args.source}", file=sys.stderr)
        sys.exit(1)

    # Optional video writer
    writer = None
    if args.save:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
        writer = cv2.VideoWriter("out.mp4", fourcc, 30, (w, h))

    # Warm-up (first TRT context build / GPU init)
    t0 = time.time()
    warm = True

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        # Inference (GPU if .pt with device=0; TensorRT if .engine)
        results = model.predict(
            source=frame,
            imgsz=args.imgsz,
            conf=args.conf,
            device=device,
            verbose=False
        )

        annotated = results[0].plot()

        if warm and time.time() - t0 > 1.0:
            warm = False

        if args.show:
            cv2.imshow("YOLO (Jetson GPU)", annotated)
            if (cv2.waitKey(1) & 0xFF) == 27:  # ESC
                break

        if writer:
            writer.write(annotated)

    cap.release()
    if writer: writer.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
