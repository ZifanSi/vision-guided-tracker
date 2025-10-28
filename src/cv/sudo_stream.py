# yolo_v4l2_display.py
import os, time, cv2, torch
from ultralytics import YOLO

# --- 显示环境修复（关键） ---
os.environ.setdefault("DISPLAY", ":0")  # 若用 SSH -Y，会自动给 DISPLAY，不需要这行
os.environ.setdefault("XAUTHORITY", "/home/rocam/.Xauthority")
os.environ.setdefault("GDK_BACKEND", "x11")  # Wayland 下用 XWayland

def can_show():
    # 有 DISPLAY 且不是纯 headless；sudo -E 后这里应有值
    return bool(os.environ.get("DISPLAY"))

# --- 你的原始参数 ---
DEV = "/dev/video0"
W, H, FPS = 1280, 720, 30

cap = cv2.VideoCapture(DEV, cv2.CAP_V4L2)
assert cap.isOpened(), f"V4L2 打不开: {DEV}"

cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
cap.set(cv2.CAP_PROP_FPS,          FPS)

model = YOLO("weights/yolo12n")
model.to("cuda:0" if torch.cuda.is_available() else "cpu")

# 提前创建窗口，避免后面 setWindowTitle 找不到
if can_show():
    cv2.namedWindow("YOLO V4L2", cv2.WINDOW_NORMAL)

t0, frames = time.time(), 0
print("Press ESC to quit")
while True:
    ok, frame = cap.read()
    if not ok:
        print("grab failed")
        break

    r = model(frame, imgsz=640, conf=0.01, verbose=False)
    vis = r[0].plot()

    frames += 1
    if can_show():
        if frames % 30 == 0:
            fps = frames / (time.time() - t0)
            cv2.setWindowTitle("YOLO V4L2", f"YOLO V4L2  ~{fps:.1f} FPS")
        cv2.imshow("YOLO V4L2", vis)
        if cv2.waitKey(1) == 27:
            break
    else:
        # 无头环境兜底：每 60 帧存一张，或写视频/推流
        if frames % 60 == 0:
            cv2.imwrite(f"/tmp/yolo_frame_{frames}.jpg", vis)

cap.release()
if can_show():
    cv2.destroyAllWindows()
