# cam.py
from ultralytics import YOLO
import torch

model = YOLO("weights/bestR.pt")
device = "mps" if torch.backends.mps.is_available() else "cpu"
model.predict(source=0, show=True, conf=0.25, device=device)  # 0=前置摄像头
