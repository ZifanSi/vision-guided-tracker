#!/usr/bin/env python3
# yolo_auto_train.py
# Train and auto-finetune YOLO model (Ultralytics)

import json, random
from pathlib import Path
from datetime import datetime
from ultralytics import YOLO

# ===============================
# CONFIGURATION VARIABLES
# ===============================
DATA_PATH = "data.yaml"                 # path to data.yaml
MODEL_PATH = "yolo12n.pt"               # pretrained model path or name
IMG_SIZE = 640
EPOCHS_FINAL = 1000
EPOCHS_TUNE = 30
BATCH_SIZE = 16
TUNE_ITERS = 10                         # number of tuning trials
PROJECT_DIR = Path("runs/auto_train")
RUN_NAME = f"exp-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
SEED = 42
SKIP_TUNE = False                       # True → skip tuning

# Hyperparameter search space
SEARCH_SPACE = {
    "lr0": (1e-4, 1e-2),
    "lrf": (0.01, 0.3),
    "momentum": (0.8, 0.98),
    "weight_decay": (0.0001, 0.01),
    "warmup_epochs": (0.0, 5.0),
    "box": (5.0, 10.0),
    "cls": (0.2, 1.0),
    "dfl": (0.5, 2.0),
    "hsv_h": (0.0, 0.02),
    "hsv_s": (0.0, 0.8),
    "hsv_v": (0.0, 0.8),
    "degrees": (0.0, 20.0),
    "translate": (0.0, 0.2),
    "scale": (0.7, 1.3),
    "shear": (0.0, 2.0),
    "flipud": (0.0, 0.2),
    "fliplr": (0.0, 0.8),
    "mosaic": (0.0, 0.5),
}
METRIC_KEYS = ["metrics/mAP50-95(B)", "metrics/mAP50-95"]

# ===============================
# CORE LOGIC
# ===============================
def now_tag() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def sample_params(space):
    params = {}
    for k, v in space.items():
        lo, hi = v
        params[k] = random.uniform(lo, hi)
    return params

def read_best_metric(run_dir: Path) -> float:
    results_json = run_dir / "results.json"
    best = float("-inf")
    if results_json.exists():
        try:
            with open(results_json, "r") as f:
                js = json.load(f)
            for rec in js:
                for key in METRIC_KEYS:
                    if key in rec:
                        best = max(best, float(rec[key]))
        except Exception:
            pass
    return best

def train_once(model_path, data, imgsz, epochs, batch, project, name, params):
    model = YOLO(model_path)
    result = model.train(
        data=data,
        imgsz=imgsz,
        epochs=epochs,
        batch=batch,
        project=str(project),
        name=name,
        exist_ok=True,
        **params,
    )
    return Path(result.save_dir)

def try_ultralytics_tune(model_path, data, imgsz, epochs, project, name, iterations, space):
    model = YOLO(model_path)
    tune_dir = project / f"{name}_tune"
    tune_dir.mkdir(parents=True, exist_ok=True)
    res = model.tune(
        data=data,
        imgsz=imgsz,
        epochs=epochs,
        iterations=iterations,
        space=space,
        project=str(project),
        name=f"{name}_tune",
        exist_ok=True,
        plots=False,
    )
    if isinstance(res, dict) and "best_params" in res:
        return res["best_params"], Path(res.get("save_dir", tune_dir))
    raise RuntimeError("Ultralytics tune did not return parameters.")

def manual_random_search(model_path, data, imgsz, epochs, batch, project, name, iterations, space):
    best_params, best_score, best_dir = None, float("-inf"), None
    for i in range(iterations):
        params = sample_params(space)
        trial_name = f"{name}_t{i+1:02d}"
        run_dir = train_once(model_path, data, imgsz, epochs, batch, project, trial_name, params)
        score = read_best_metric(run_dir)
        if score > best_score:
            best_score, best_params, best_dir = score, params, run_dir
    return best_params, best_dir

def main():
    random.seed(SEED)
    PROJECT_DIR.mkdir(parents=True, exist_ok=True)

    best_params, tune_dir = {}, None

    if not SKIP_TUNE and TUNE_ITERS > 0:
        print("[INFO] Starting hyperparameter tuning...")
        try:
            best_params, tune_dir = try_ultralytics_tune(
                MODEL_PATH, DATA_PATH, IMG_SIZE, EPOCHS_TUNE,
                PROJECT_DIR, RUN_NAME, TUNE_ITERS, SEARCH_SPACE
            )
        except Exception:
            print("[WARN] Falling back to manual random search.")
            best_params, tune_dir = manual_random_search(
                MODEL_PATH, DATA_PATH, IMG_SIZE, EPOCHS_TUNE, BATCH_SIZE,
                PROJECT_DIR, RUN_NAME + "_manual", TUNE_ITERS, SEARCH_SPACE
            )
        with open(PROJECT_DIR / f"{RUN_NAME}_best_params.json", "w") as f:
            json.dump(best_params, f, indent=2)
        print("[INFO] Best parameters saved.")
    else:
        print("[INFO] Skipping tuning.")

    print("[INFO] Starting final training...")
    final_name = f"{RUN_NAME}_final"
    final_dir = train_once(
        MODEL_PATH, DATA_PATH, IMG_SIZE, EPOCHS_FINAL, BATCH_SIZE,
        PROJECT_DIR, final_name, best_params
    )

    summary = {
        "project": str(PROJECT_DIR.resolve()),
        "tune_dir": str(tune_dir.resolve()) if tune_dir else None,
        "final_dir": str(final_dir.resolve()),
        "best_params": best_params,
        "best_final_metric": read_best_metric(final_dir),
        "artifacts": {
            "best_weights": str((final_dir / "weights" / "best.pt").resolve()),
            "last_weights": str((final_dir / "weights" / "last.pt").resolve()),
        },
    }

    with open(final_dir / "auto_train_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    print("[DONE] Training complete.")

if __name__ == "__main__":
    main()
