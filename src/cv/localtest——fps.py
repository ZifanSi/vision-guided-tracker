# cam_fps.py
from ultralytics import YOLO
import torch, cv2, time
from collections import deque

WEIGHTS = "weights/bestR.pt"

# 设备自动选择：Apple 芯片用 mps，否则用 cpu（有独显可改为 "0"）
device = "mps" if torch.backends.mps.is_available() else "cpu"
print("Using device:", device)

model = YOLO(WEIGHTS)

# 平滑一下 FPS（滚动窗口平均），避免抖动
fps_hist = deque(maxlen=30)
last_t = time.time()

try:
    # source=0 是 Mac 的前置/默认摄像头；imgsz 可改小提速，如 640/512
    for res in model.predict(source=0, stream=True, device=device,
                             conf=0.25, imgsz=1024, verbose=False):
        now = time.time()
        dt = now - last_t
        last_t = now
        if dt > 0:
            fps_hist.append(1.0 / dt)
        fps = sum(fps_hist) / len(fps_hist) if fps_hist else 0.0

        frame = res.plot()  # 已带检测框的图
        cv2.putText(frame, f"FPS: {fps:.1f}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

        cv2.imshow("YOLO Camera (press q/Esc to quit)", frame)
        key = cv2.waitKey(1) & 0xFF
        if key in (27, ord('q')):
            break
finally:
    cv2.destroyAllWindows()
