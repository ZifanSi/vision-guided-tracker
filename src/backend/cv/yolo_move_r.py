# yolo_v4l2_display.py
import os, time, cv2, torch
from collections import deque
from ultralytics import YOLO
import threading
from collections import deque as _deque

from backend.Gimbal import GimbalSerial

# 把窗口显示到 Jetson 本地屏幕
os.environ.setdefault("DISPLAY", ":0")
os.environ.setdefault("XAUTHORITY", "/home/rocam/.Xauthority")

DEV = "/dev/video0"
W, H, FPS = 1280, 720, 30

# === 旋转设置：0=不旋转；90=顺时针90°；-90=逆时针90°；180=倒转 ===
ROTATE_DEG = 90   # ← 按需改：不旋转填 0
_ROT_MAP = {90: cv2.ROTATE_90_CLOCKWISE, -90: cv2.ROTATE_90_COUNTERCLOCKWISE, 180: cv2.ROTATE_180}

# 用 V4L2 后端直连（不依赖 OpenCV 的 GStreamer）
cap = cv2.VideoCapture(DEV, cv2.CAP_V4L2)
assert cap.isOpened(), f"V4L2 打不开: {DEV}"

# 先尝试 MJPG（更省带宽）；如果你的设备不支持，注释掉此行并用 YUYV（见下面注释）
cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

# 分辨率与帧率（不被设备支持时会被忽略；以 v4l2-ctl --list-formats-ext 为准）
cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)
cap.set(cv2.CAP_PROP_FPS, FPS)


# ====== 新增：后台抓帧（只保留最新一帧）======
class LatestFrameGrabber:
    def __init__(self, cap):
        self.cap = cap
        self.buf = _deque(maxlen=1)  # 仅保留最新一帧
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
            # —— 新增：可选90°整数旋转（极低开销） ——
            if ROTATE_DEG in _ROT_MAP:
                frame = cv2.rotate(frame, _ROT_MAP[ROTATE_DEG])

            self.buf.clear()  # 丢掉旧帧
            self.buf.append(frame)

    def get(self, timeout_ms=100):
        # 简单等待：避免主线程空转
        end = time.time() + timeout_ms / 1000.0
        while not self.buf and time.time() < end and not self.stop_flag:
            time.sleep(0.001)
        return self.buf[0] if self.buf else None

    def stop(self):
        self.stop_flag = True
        self.t.join(timeout=0.5)


grabber = LatestFrameGrabber(cap).start()

# 加载模型（可换成你的权重）
model = YOLO("weights/pega_11n_map95.pt")  # 或 "yolov8n.pt"
model.to("cuda:0" if torch.cuda.is_available() else "cpu")  # 只在这里指定一次设备

# —— 方案A：1秒窗口的吞吐FPS（最小改动） ——
clock = time.perf_counter
tsq = deque()
frames = 0

gimbal = GimbalSerial(port="/dev/ttyTHS1", baudrate=115200, timeout=0.5)
# gimbal.move_deg(0, 0)
gimbal_tilt = 0
gimbal_pan = 0
time.sleep(1)

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

        # 推理（不要再传 device 参数）
        r = model(frame, imgsz=1088, conf=0.5, verbose=False,iou=0.08)

        # ========== 新增：拿最高置信度框 ==========
        best_box_xyxy = None  # 默认没有目标
        best_conf = None

        boxes = r[0].boxes  # ultralytics.engine.results.Boxes

        if boxes is not None and boxes.shape[0] > 0:
            confs = boxes.conf  # tensor [N]
            xyxy = boxes.xyxy   # tensor [N,4]  format: x1,y1,x2,y2

            # 找到最大置信度的下标
            max_idx = torch.argmax(confs).item()

            # 取该框的坐标和置信度
            best_conf = float(confs[max_idx].item())
            best_box_xyxy = xyxy[max_idx].tolist()  # [x1,y1,x2,y2] as python list[4]

            # 中心点
            x1, y1, x2, y2 = best_box_xyxy
            cx = 0.5 * (x1 + x2)
            cy = 0.5 * (y1 + y2)

            # —— 关键：用当前帧的实际宽高（旋转后自动适配） ——
            h, w = frame.shape[:2]
            center_x = w / 2.0
            center_y = h / 2.0

            error_x = cx - center_x
            error_y = cy - center_y

            # 保持你原有的云台映射与符号（最小化修改）
            gimbal_pan  -= error_y * 0.01
            gimbal_tilt -= error_x * 0.01

            if gimbal_pan > 45:
                gimbal_pan = 45
            elif gimbal_pan < -45:
                gimbal_pan = -45
            if gimbal_tilt > 90:
                gimbal_tilt = 90
            elif gimbal_tilt < 0:
                gimbal_tilt = 0
            gimbal.move_deg(gimbal_tilt, gimbal_pan)

            print(f"[TRACK] best_conf={best_conf:.3f}, box={best_box_xyxy}, center=({cx:.1f},{cy:.1f})")
        else:
            # 没检测到
            print("[TRACK] no detections")

        # 带框可视化
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
            cv2.setWindowTitle("YOLO V4L2", f"YOLO V4L2  ~{fps:.1f} FPS")

        cv2.imshow("YOLO V4L2", vis)
        if cv2.waitKey(1) == 27:  # ESC
            break
finally:
    grabber.stop()
    cap.release()
    cv2.destroyAllWindows()
