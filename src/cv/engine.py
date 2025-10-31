from ultralytics import YOLO

model = YOLO("weights/yolo12n.pt")  # 确保是 .pt 权重
model.export(
    format="engine",   # 直接导出 TensorRT 引擎
    imgsz=1024,        # 和你推理时用的一致
    device=0,          # Jetson 的 GPU
    half=True          # half=True => FP16
)


#
# # 用 TensorRT 引擎而不是 .pt
# trt_model = YOLO("yolo12n.engine")