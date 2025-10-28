# yolo_v4l2_display.py  —— 极简加速版（保持你的结构）
import os, time, cv2, torch
from collections import deque
from ultralytics import YOLO
import numpy as np

# 把窗口显示到 Jetson 本地屏幕
os.environ.setdefault("DISPLAY", ":0")
os.environ.setdefault("XAUTHORITY", "/home/rocam/.Xauthority")

# ---- PyTorch / CUDA 加速开关（关键）----
torch.backends.cudnn.benchmark = True
try:
    # PyTorch 2.x 可用；对 matmul 内核选择更激进
    torch.set_float32_matmul_precision("high")
except Exception:
    pass

DEV = "/dev/video0"
W, H, FPS = 1280, 720, 30

# 用 V4L2 后端直连（不依赖 OpenCV 的 GStreamer）
cap = cv2.VideoCapture(DEV, cv2.CAP_V4L2)
assert cap.isOpened(), f"V4L2 打不开: {DEV}"

# ======== 摄像头参数：尽量减少延迟 / 解码负担 ========
# 若 CPU 解码吃紧，可考虑改用 YUYV（去掉 MJPG 这一行），详见下方注释
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
cap.set(cv2.CAP_PROP_FPS,         FPS)

# 减少缓冲（降低延迟，避免积帧）
try:
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
except Exception:
    pass

# 预创建窗口，避免反复创建带来的开销
cv2.namedWindow("YOLO V4L2", cv2.WINDOW_NORMAL | cv2.WINDOW_GUI_NORMAL)

# 加载模型（可换成你的权重）
model = YOLO("weights/yolo12n")  # 或 "yolov8n.pt"
device = "cuda:0" if torch.cuda.is_available() else "cpu"
model.to(device)

# 模型层融合（卷积+BN），推理更快一点
try:
    model.fuse()
except Exception:
    pass

# FP16：Jetson / NVIDIA GPU 上普遍显著提速
if device.startswith("cuda"):
    try:
        model.model.half()
        USE_HALF = True
    except Exception:
        USE_HALF = False
else:
    USE_HALF = False

# —— 方案A：1秒窗口的吞吐FPS（最小改动） ——
clock = time.perf_counter
tsq = deque()
frames = 0

# 渲染节流：不是每帧都重绘，可减少可视化开销
RENDER_EVERY = 2  # 每 2 帧绘制一次，可按需改 2~3
last_vis = None

# 推理输入分辨率（比 640 再低一点，常能明显涨 FPS）
IMGSZ = 512  # 384/448/512/576 都可以试；512 常是甜点
CONF = 0.6   # 适当降低 conf，对速度影响小，但可减少后处理负担

print("Press ESC to quit")
while True:
    ok, frame = cap.read()
    if not ok:
        print("grab failed")
        break

    # 如果你改用 YUYV/UYVY，请去掉 MJPG 那行，并用以下之一解码为 BGR：
    # frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_YUYV)  # YUYV
    # frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_UYVY)  # UYVY

    # 确保内存连续，减少拷贝/转换开销
    frame = np.ascontiguousarray(frame)

    # 推理（不要再传 device 参数）
    # 注意：Ultralytics 内部会做 resize 与预处理，这里只给 imgsz/置信度
    r = model(frame, imgsz=IMGSZ, conf=CONF, verbose=False)

    # 渲染节流：不是每帧都plot（plot 里用到 PIL，比较慢）
    if frames % RENDER_EVERY == 0:
        # line_width=1 会更快一些
        last_vis = r[0].plot(line_width=1)
    vis = last_vis if last_vis is not None else frame

    # 更新时间戳队列（保留最近1秒）
    now = clock()
    tsq.append(now)
    one_sec_ago = now - 1.0
    while tsq and tsq[0] < one_sec_ago:
        tsq.popleft()

    frames += 1
    if frames % 30 == 0:
        fps = len(tsq) / 1.0  # 最近1秒的端到端吞吐FPS
        cv2.setWindowTitle("YOLO V4L2", f"YOLO V4L2  ~{fps:.1f} FPS (imgsz={IMGSZ}, half={USE_HALF})")

    cv2.imshow("YOLO V4L2", vis)
    if cv2.waitKey(1) == 27:  # ESC
        break

cap.release()
cv2.destroyAllWindows()
