from ultralytics import YOLO
# 1. 先加载 TensorRT 引擎
trt_model = YOLO("yolo12n.engine")  # FP16 TensorRT engine
# 注意：不需要 .to("cuda")，它已经是GPU engine了


# # 预热
# _tmp = grabber.get(timeout_ms=500)
# if _tmp is not None:
#     for _ in range(5):
#         _ = model(_tmp, imgsz=1088, conf=0.13, verbose=False)
# #


clock = time.perf_counter
tsq = deque()
frames = 0

print("Press ESC to quit")
try:
    while True:
        frame = grabber.get(timeout_ms=100)
        if frame is None:
            print("no frame yet")
            continue

        # TensorRT 推理
        # 这里 imgsz 必须和导出时一致，比如 1088
        r = trt_model(frame, imgsz=1080, conf=0.13, verbose=False)
        vis = r[0].plot()

        # FPS统计同你原来的逻辑
        now = clock()
        tsq.append(now)
        one_sec_ago = now - 1.0
        while tsq and tsq[0] < one_sec_ago:
            tsq.popleft()

        frames += 1
        if frames % 30 == 0:
            fps = len(tsq) / 1.0
            cv2.setWindowTitle("YOLO V4L2", f"YOLO V4L2 TRT ~{fps:.1f} FPS")

        cv2.imshow("YOLO V4L2", vis)
        if cv2.waitKey(1) == 27:
            break
finally:
    grabber.stop()
    cap.release()
    cv2.destroyAllWindows()
