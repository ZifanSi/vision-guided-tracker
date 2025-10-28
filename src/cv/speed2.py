# yolo_v4l2_display.py —— 最小化无损优化版（保持 imgsz≈1080, conf=0.13；自动对齐到32的倍数）
import os, time, cv2, torch, threading
from collections import deque
from collections import deque as _deque
import numpy as np
from ultralytics import YOLO
import math

# ---------- 显示/底层加速（无损） ----------
os.environ.setdefault("DISPLAY", ":0")
os.environ.setdefault("XAUTHORITY", "/home/rocam/.Xauthority")
cv2.setNumThreads(1)
cv2.setUseOptimized(True)

torch.backends.cudnn.benchmark = True
try:
    torch.set_float32_matmul_precision("high")
except Exception:
    pass

# ---------- 相机参数 ----------
DEV = "/dev/video0"
W, H, FPS = 1280, 720, 30

# 是否使用无压缩 YUYV（更低延迟、更好画质；USB2 可能带不动 720p 以上）
USE_YUYV = False  # 先沿用你原来的 MJPG；若USB3/带宽允许可改 True

# 用 V4L2 后端直连
cap = cv2.VideoCapture(DEV, cv2.CAP_V4L2)
assert cap.isOpened(), f"V4L2 打不开: {DEV}"

if USE_YUYV:
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
else:
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

cap.set(cv2.CAP_PROP_FRAME_WIDTH,  W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
cap.set(cv2.CAP_PROP_FPS,         FPS)
# 尽量减小采集端缓冲，避免积帧
try:
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
except Exception:
    pass

# ====== 后台抓帧（只保留最新一帧，主动丢旧帧）======
class LatestFrameGrabber:
    def __init__(self, cap, use_yuyv=False, drops=1):
        self.cap = cap
        self.use_yuyv = use_yuyv
        self.drops = max(0, int(drops))  # 每圈 grab 丢旧帧次数
        self.buf = _deque(maxlen=1)      # 仅保留最新一帧
        self.stop_flag = False
        self.t = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self.t.start()
        return self

    def _loop(self):
        while not self.stop_flag:
            # 主动丢旧帧，降低尾延迟（根据负载可设为 1~3）
            for _ in range(self.drops):
                self.cap.grab()

            if self.use_yuyv:
                ok = self.cap.grab()
                if not ok:
                    continue
                ok, frame = self.cap.retrieve()
                if not ok:
                    continue
                # YUYV -> BGR（无压缩解码）
                frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_YUYV)
            else:
                ok, frame = self.cap.read()  # MJPG: read 内含 JPEG 解码
                if not ok:
                    continue

            frame = np.ascontiguousarray(frame)
            self.buf.clear()
            self.buf.append(frame)

    def get(self, timeout_ms=100):
        end = time.time() + timeout_ms/1000.0
        while not self.buf and time.time() < end and not self.stop_flag:
            time.sleep(0.001)
        return self.buf[0] if self.buf else None

    def stop(self):
        self.stop_flag = True
        self.t.join(timeout=0.5)

grabber = LatestFrameGrabber(cap, use_yuyv=USE_YUYV, drops=1).start()

# ---------- 加载模型 ----------
model = YOLO("weights/yolo12n")  # 或 "yolov8n.pt"
device = "cuda:0" if torch.cuda.is_available() else "cpu"
model.to(device)

# —— 计算与1080最接近且满足stride要求的IMGSZ（一次性） —— #
BASE_IMGSZ = 1080
try:
    stride = int(getattr(model.model, "stride").max().item())
except Exception:
    stride = 32
IMGSZ = int(math.ceil(BASE_IMGSZ / stride) * stride)  # 1080 -> 1088
HALF_INFER = device.startswith("cuda")

# 预热：不影响结果，只是消除首帧抖动
warm = grabber.get(timeout_ms=500)
if warm is not None:
    for _ in range(8):
        _ = model(warm, imgsz=IMGSZ, conf=0.13, half=HALF_INFER, verbose=False)

# ---------- 自绘框（替代 r[0].plot()，不影响检测结果，只省渲染时间） ----------
def draw_detections(img, res):
    vis = img
    if res.boxes is None or len(res.boxes) == 0:
        return vis
    b = res.boxes
    xyxy = b.xyxy.int().cpu().numpy()
    conf = b.conf.cpu().numpy() if b.conf is not None else []
    cls  = b.cls.int().cpu().numpy() if b.cls is not None else []
    names = res.names if hasattr(res, "names") else {}
    for i, (x1, y1, x2, y2) in enumerate(xyxy):
        cv2.rectangle(vis, (x1, y1), (x2, y2), (0, 255, 0), 2)
        if i < len(conf):
            label = f"{names.get(int(cls[i]), str(int(cls[i])))} {conf[i]:.2f}"
            cv2.putText(vis, label, (x1, max(0, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0),
                        1, cv2.LINE_AA)
    return vis

# —— 1秒窗口的吞吐FPS（与你原来一致） ——
clock = time.perf_counter
tsq = deque()
frames = 0

cv2.namedWindow("YOLO V4L2", cv2.WINDOW_NORMAL)
print("Press ESC to quit")
try:
    while True:
        # 从后台线程拿“最新一帧”；若暂时还没帧，就继续等一会儿
        frame = grabber.get(timeout_ms=100)
        if frame is None:
            continue

        # 推理（使用对齐后的 IMGSZ，避免每帧警告）
        r = model(frame, imgsz=IMGSZ, conf=0.13, half=HALF_INFER, verbose=False)

        # 自绘（不改变检测结果）
        vis = draw_detections(frame, r[0])

        # 更新时间戳队列（保留最近1秒）
        now = clock()
        tsq.append(now)
        one_sec_ago = now - 1.0
        while tsq and tsq[0] < one_sec_ago:
            tsq.popleft()

        frames += 1
        if frames % 30 == 0:
            fps = len(tsq) / 1.0  # 最近1秒端到端吞吐FPS
            mode = "YUYV" if USE_YUYV else "MJPG"
            cv2.setWindowTitle("YOLO V4L2",
                               f"YOLO V4L2  ~{fps:.1f} FPS | {mode} {W}x{H}@{FPS} | imgsz={IMGSZ} | half={HALF_INFER}")

        cv2.imshow("YOLO V4L2", vis)
        if cv2.waitKey(1) == 27:  # ESC
            break
finally:
    grabber.stop()
    cap.release()
    cv2.destroyAllWindows()
