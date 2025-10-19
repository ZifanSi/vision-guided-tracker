# yolo_v4l2_display.py
import os, time, cv2, torch
from ultralytics import YOLO

# 把窗口显示到 Jetson 本地屏幕
os.environ.setdefault("DISPLAY", ":0")
os.environ.setdefault("XAUTHORITY", "/home/rocam/.Xauthority")

DEV = "/dev/video0"
W, H, FPS = 1280, 720, 30

# 用 V4L2 后端直连（不依赖 OpenCV 的 GStreamer）
cap = cv2.VideoCapture(DEV, cv2.CAP_V4L2)
assert cap.isOpened(), f"V4L2 打不开: {DEV}"

# 先尝试 MJPG（更省带宽）；如果你的设备不支持，注释掉此行并用 YUYV（见下面注释）
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

# 分辨率与帧率（不被设备支持时会被忽略；以 v4l2-ctl --list-formats-ext 为准）
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
cap.set(cv2.CAP_PROP_FPS,         FPS)

# 加载模型（可换成你的权重）
model = YOLO("weights/yolo12n")  # 或 "yolov8n.pt"
model.to("cuda:0" if torch.cuda.is_available() else "cpu")  # 只在这里指定一次设备

t0, frames = time.time(), 0
print("Press ESC to quit")
while True:
    ok, frame = cap.read()
    if not ok:
        print("grab failed")
        break

    # 如果你改用 YUYV/UYVY，请去掉 MJPG 那行，并解码成 BGR：
    # frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_YUY2)  # YUYV
    # frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_UYVY)  # UYVY

    # 推理（不要再传 device 参数）
    r = model(frame, imgsz=640, conf=0.01, verbose=False)
    vis = r[0].plot()

    frames += 1
    if frames % 30 == 0:
        fps = frames / (time.time() - t0)
        cv2.setWindowTitle("YOLO V4L2", f"YOLO V4L2  ~{fps:.1f} FPS")

    cv2.imshow("YOLO V4L2", vis)
    if cv2.waitKey(1) == 27:  # ESC
        break

cap.release()
cv2.destroyAllWindows()
