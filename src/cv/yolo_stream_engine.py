import os, time, cv2, torch
from collections import deque
from ultralytics import YOLO
import threading
from collections import deque as _deque

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

# ====== 后台抓帧：只保留最新一帧 ======
class LatestFrameGrabber:
    def __init__(self, cap):
        self.cap = cap
        self.buf = _deque(maxlen=1)   # 仅保留最新一帧
        self.stop_flag = False
        self.t = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self.t.start()
        return self

    def _loop(self):
        while not self.stop_flag:
            ok, frame = self.cap.read()
            if not ok:
                continue
            self.buf.clear()          # 丢掉旧帧
            self.buf.append(frame)

    def get(self, timeout_ms=100):
        # 简单等待：避免主线程空转
        end = time.time() + timeout_ms/1000.0
        while not self.buf and time.time() < end and not self.stop_flag:
            time.sleep(0.001)
        return self.buf[0] if self.buf else None

    def stop(self):
        self.stop_flag = True
        self.t.join(timeout=0.5)

grabber = LatestFrameGrabber(cap).start()

# ========= 加载 TensorRT engine =========
# 假设你已经在 Jetson 上生成了 FP16/INT8 TensorRT 引擎文件，比如 weights/yolo12n.engine
# 这里不再调用 .to("cuda")，TensorRT 引擎本身已经是部署态
engine_model = YOLO("weights/yolo12n.engine")

# —— 方案A：1秒窗口的吞吐FPS（保持不变） ——
clock = time.perf_counter
tsq = deque()
frames = 0

print("Press ESC to quit")
try:
    while True:
        # 从后台线程拿“最新一帧”；若暂时还没帧，就继续等一会儿
        frame = grabber.get(timeout_ms=100)
        if frame is None:
            print("no frame yet")
            continue

        # 如果你改用 YUYV/UYVY，请去掉 MJPG 那行，并解码成 BGR：
        # frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_YUYV)  # YUYV
        # frame = cv2.cvtColor(frame, cv2.COLOR_YUV2BGR_UYVY)  # UYVY

        # 使用 TensorRT 引擎推理
        # imgsz 必须和你导出 engine 时用的一样，比如 1088
        r = engine_model(frame, imgsz=1088, conf=0.13, verbose=False)

        # 可视化检测框
        vis = r[0].plot()

        # 更新时间戳队列（保留最近1秒）
        now = clock()
        tsq.append(now)
        one_sec_ago = now - 1.0
        while tsq and tsq[0] < one_sec_ago:
            tsq.popleft()

        frames += 1
        if frames % 30 == 0:
            fps = len(tsq) / 1.0  # 最近1秒的端到端吞吐FPS
            cv2.setWindowTitle("YOLO V4L2", f"YOLO V4L2 TRT ~{fps:.1f} FPS")

        cv2.imshow("YOLO V4L2", vis)
        if cv2.waitKey(1) == 27:  # ESC
            break
finally:
    grabber.stop()
    cap.release()
    cv2.destroyAllWindows()
