# yolo_v4l2_display_latency_only.py
import os, time, cv2
from collections import deque

# 把窗口显示到 Jetson 本地屏幕
os.environ.setdefault("DISPLAY", ":0")
os.environ.setdefault("XAUTHORITY", "/home/rocam/.Xauthority")

DEV = "/dev/video0"
W, H, FPS = 1280, 720, 30

# 用 V4L2 后端直连（不依赖 OpenCV 的 GStreamer）
cap = cv2.VideoCapture(DEV, cv2.CAP_V4L2)
assert cap.isOpened(), f"V4L2 打不开: {DEV}"

# 先尝试 MJPG（更省带宽）；如不支持，请注释本行改用 YUYV（见下面注释）
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

# 分辨率与帧率（以 v4l2-ctl --list-formats-ext 为准，不一定都生效）
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
cap.set(cv2.CAP_PROP_FPS,         FPS)

# 为降低积帧（延迟），尽量缩小缓冲
try:
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
except Exception:
    pass

clock = time.perf_counter
tsq = deque()
frames = 0

def ema(prev, val, alpha=0.2):
    return val if prev is None else (alpha * val + (1 - alpha) * prev)

ema_read = ema_total = None

cv2.namedWindow("CAM LAT", cv2.WINDOW_NORMAL)

print("Press ESC to quit")
while True:
    t0 = clock()

    # 采集
    t_r0 = clock()
    ok, frame = cap.read()
    t_r1 = clock()
    if not ok:
        print("grab failed")
        break
    read_ms = (t_r1 - t_r0) * 1000.0

    # 如改用 YUYV/UYVY，请去掉 MJPG 那行，并解码为 BGR：
    # frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_YUYV)  # YUYV
    # frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_UYVY)  # UYVY

    # 端到端显示前的软件延迟（采集+任何处理，这里无推理，仅绘字）
    info = f"read:{read_ms:.1f}ms"
    cv2.putText(frame, info, (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2, cv2.LINE_AA)

    total_ms = (clock() - t0) * 1000.0
    ema_read  = ema(ema_read,  read_ms)
    ema_total = ema(ema_total, total_ms)

    # 最近1秒吞吐FPS
    now = clock()
    tsq.append(now)
    one_sec_ago = now - 1.0
    while tsq and tsq[0] < one_sec_ago:
        tsq.popleft()
    fps = len(tsq) / 1.0

    # 叠加显示更平滑的统计
    info2 = f"total:{ema_total:.1f}ms  FPS:{fps:.1f}"
    cv2.putText(frame, info2, (10, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2, cv2.LINE_AA)

    frames += 1
    if frames % 30 == 0:
        cv2.setWindowTitle("CAM LAT", f"CAM LAT  FPS~{fps:.1f} | read {ema_read:.1f}ms, total {ema_total:.1f}ms")

    cv2.imshow("CAM LAT", frame)
    if cv2.waitKey(1) == 27:  # ESC
        break

cap.release()
cv2.destroyAllWindows()
