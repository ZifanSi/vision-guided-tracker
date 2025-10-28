# yolo_v4l2_display.py  —— 线程抓帧 + 无损优化 + 自绘框（保持 imgsz=640, conf=0.8）
import os, time, cv2, torch, threading
import numpy as np
from collections import deque
from ultralytics import YOLO

# ------------ 显示与加速设置（无损） ------------
os.environ.setdefault("DISPLAY", ":0")
os.environ.setdefault("XAUTHORITY", "/home/rocam/.Xauthority")
cv2.setNumThreads(1)
cv2.useOptimized(True)
torch.backends.cudnn.benchmark = True
try:
    torch.set_float32_matmul_precision("high")
except Exception:
    pass

# ------------ 相机参数 ------------
DEV = "/dev/video0"
W, H, FPS = 1280, 720, 30
USE_YUYV = True   # True=YUYV(推荐, 无压缩), False=MJPG(压缩, CPU需解码)

# ------------ 打开摄像头 ------------
cap = cv2.VideoCapture(DEV, cv2.CAP_V4L2)
assert cap.isOpened(), f"V4L2 打不开: {DEV}"

if USE_YUYV:
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
else:
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

cap.set(cv2.CAP_PROP_FRAME_WIDTH,  W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
cap.set(cv2.CAP_PROP_FPS,         FPS)
try:
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)   # 尽量减小积帧
except Exception:
    pass

# ------------ 后台抓帧（只保留最新一帧） ------------
class LatestFrameGrabber:
    def __init__(self, cap, use_yuyv=True, drops=1):
        self.cap = cap
        self.use_yuyv = use_yuyv
        self.drops = max(0, int(drops))  # 每圈先 grab 丢旧帧次数
        self.latest = None
        self.lock = threading.Lock()
        self.stop_flag = False
        self.t = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self.t.start()
        return self

    def _loop(self):
        while not self.stop_flag:
            # 丢掉可能积压的旧帧，降低尾延迟
            for _ in range(self.drops):
                self.cap.grab()

            if self.use_yuyv:
                ok = self.cap.grab()
                if not ok:
                    continue
                ok, frame = self.cap.retrieve()
                if not ok:
                    continue
                # YUYV → BGR（无压缩）
                frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_YUYV)
            else:
                ok, frame = self.cap.read()  # MJPG: read 内含解码
                if not ok:
                    continue

            # 保证内存连续，减少后续拷贝
            frame = np.ascontiguousarray(frame)

            with self.lock:
                self.latest = frame

    def get(self, timeout_ms=100):
        end = time.time() + timeout_ms/1000.0
        while time.time() < end and not self.stop_flag:
            with self.lock:
                if self.latest is not None:
                    return self.latest
            time.sleep(0.001)
        with self.lock:
            return self.latest

    def stop(self):
        self.stop_flag = True
        self.t.join(timeout=0.5)

grabber = LatestFrameGrabber(cap, use_yuyv=USE_YUYV, drops=1).start()

# ------------ 加载 YOLO（保持你的检测质量不变） ------------
model = YOLO("weights/yolo12n")  # 或 "yolov8n.pt"
device = "cuda:0" if torch.cuda.is_available() else "cpu"
model.to(device)

# 可选：FP16（基本无损；若你追求完全 FP32，可注释掉）
USE_HALF = False
if device.startswith("cuda"):
    try:
        model.model.half()
        USE_HALF = True
    except Exception:
        pass

# ------------ 预热（消除首帧内核构建抖动） ------------
warm = grabber.get(timeout_ms=500)
if warm is not None:
    for _ in range(10):
        _ = model(warm, imgsz=640, conf=0.8, verbose=False)

# ------------ 工具：自绘检测框（替代 r[0].plot） ------------
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

# ------------ 主循环 ------------
clock = time.perf_counter
tsq = deque()
frames = 0
cv2.namedWindow("YOLO V4L2", cv2.WINDOW_NORMAL)

print("Press ESC to quit")
try:
    while True:
        frame = grabber.get(timeout_ms=200)
        if frame is None:
            # 暂无帧，继续等待
            continue

        # 推理（不再传 device 参数）
        r = model(frame, imgsz=640, conf=0.8, verbose=False)
        vis = draw_detections(frame, r[0])

        # 最近 1 秒吞吐 FPS
        now = clock()
        tsq.append(now)
        one_sec_ago = now - 1.0
        while tsq and tsq[0] < one_sec_ago:
            tsq.popleft()

        frames += 1
        if frames % 30 == 0:
            fps = len(tsq) / 1.0
            mode = "YUYV" if USE_YUYV else "MJPG"
            cv2.setWindowTitle("YOLO V4L2",
                               f"YOLO V4L2  ~{fps:.1f} FPS | {mode} {W}x{H}@{FPS} | half={USE_HALF}")

        cv2.imshow("YOLO V4L2", vis)
        if cv2.waitKey(1) == 27:  # ESC
            break
finally:
    grabber.stop()
    cap.release()
    cv2.destroyAllWindows()
