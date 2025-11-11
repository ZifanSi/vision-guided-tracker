#评估
# bench_offline.py
from ultralytics import YOLO
from pathlib import Path
import csv
import glob

MODEL_PATH = "weights/bestR270.pt"   # 也可以写死具体路径
DATA_YAML  = "Rocket-Tracking-221/data.yaml"
IMG_SIZE   = 1024
CONF_THRES = 0.25
IOU_THRES  = 0.7

def read_last_row(csv_path):
    with open(csv_path, newline='') as f:
        rows = list(csv.DictReader(f))
        return rows[-1] if rows else {}

def main():
    # 1) 选一个最新的 best.pt
    candidates = sorted(glob.glob(MODEL_PATH))
    assert candidates, "找不到 best.pt，请确认路径。"
    model_p = candidates[-1]
    print(f"[INFO] Using model: {model_p}")

    # 2) 对 val/test split 做标准评估，并绘图
    model = YOLO(model_p)
    metrics = model.val(
        data=DATA_YAML,
        imgsz=IMG_SIZE,
        conf=CONF_THRES,
        iou=IOU_THRES,
        device="mps",
        plots=True,        # 生成 PR 曲线、混淆矩阵、样例可视化
        save_json=False,   # 若是 COCO 标注，可设 True 导出 COCO-json 便于第三方评估
    )
    print("[INFO] Val done. See runs/detect/val* for PR曲线/混淆矩阵等图。")

    # 3) 顺手把训练阶段的结果（results.csv 最后一行）读出来对比
    train_dir = Path(model_p).parents[1]   # runs/detect/trainXX
    csv_path = train_dir / "results.csv"
    if csv_path.exists():
        last = read_last_row(str(csv_path))
        # 常见列名（不同版本列名可能略有差异，这里做容错抓取）
        def pick(*keys, default="NA"):
            for k in keys:
                if k in last: return last[k]
            return default

        prec = pick("metrics/precision(B)", "metrics/precision")
        rec  = pick("metrics/recall(B)",    "metrics/recall")
        map50 = pick("metrics/mAP50(B)",   "metrics/mAP50")
        map5095 = pick("metrics/mAP50-95(B)","metrics/mAP50-95","metrics/mAP50-95(B)")

        print("\n[Training Summary: results.csv last row]")
        print(f"Precision: {prec}")
        print(f"Recall   : {rec}")
        print(f"mAP@0.50 : {map50}")
        print(f"mAP@.50:.95: {map5095}")
    else:
        print("[WARN] 未找到 results.csv，跳过训练曲线对照。")

if __name__ == "__main__":
    main()
