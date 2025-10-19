# file: yolo_csi_argus.py
from ultralytics import YOLO
import cv2

# 1280x720 @ 30fps，可改为 1920x1080 或 3840x2160（先确认能跑动）
GST = (
    "nvarguscamerasrc ! "
    "video/x-raw(memory:NVMM), width=1280, height=720, framerate=30/1, format=NV12 ! "
    "nvvidconv ! video/x-raw, format=BGRx ! "
    "videoconvert ! video/x-raw, format=BGR ! "
    "appsink drop=true sync=false max-buffers=1"
)

cap = cv2.VideoCapture(GST, cv2.CAP_GSTREAMER)
assert cap.isOpened(), "GStreamer 打开失败（nvarguscamerasrc）。请关闭 qv4l2 / 其它占用进程再试。"

model = YOLO("yolov11n.pt")   # 可换 yolov8n.pt / 你的自训权重
while True:
    ok, frame = cap.read()
    if not ok:
        print("读取帧失败"); break
    r = model.predict(source=frame, device=0, imgsz=640, conf=0.25, verbose=False)
    vis = r[0].plot()
    cv2.imshow("YOLO CSI (Argus)", vis)
    if cv2.waitKey(1) & 0xFF == 27:  # ESC
        break

cap.release()
cv2.destroyAllWindows()
