#!/usr/bin/env python3
import argparse, random, yaml
from pathlib import Path
from sklearn.model_selection import KFold
from ultralytics import YOLO

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

def find_pairs(data_root: Path):
    imdir = data_root / "images"
    lbdir = data_root / "labels"
    assert imdir.exists() and lbdir.exists(), "Expect images/ and labels/ under data-root"
    images = []
    for p in imdir.rglob("*"):
        if p.suffix.lower() in IMG_EXTS:
            if (lbdir / (p.stem + ".txt")).exists():
                images.append(p.resolve())
    if not images:
        raise RuntimeError("No (image,label) pairs found.")
    images.sort()
    return images

def write_list(items, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(str(it) + "\n")

def load_base_yaml(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def make_fold_yaml(base_cfg: dict, train_list: Path, val_list: Path, out_yaml: Path):
    cfg = dict(base_cfg)  # shallow copy
    cfg["train"] = str(train_list)
    cfg["val"] = str(val_list)
    # Optional: remove 'path' if it conflicts with list-files approach
    cfg.pop("path", None)
    out_yaml.parent.mkdir(parents=True, exist_ok=True)
    with out_yaml.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, sort_keys=False)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True, help="Dataset root with images/ and labels/")
    ap.add_argument("--base-yaml", required=True, help="Base data YAML (contains nc/names)")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--model", default="yolov12n.pt")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--degrees", type=float, default=180.0, help="Max rotation for augmentation")
    ap.add_argument("--project", default="yolov12_kfold")
    ap.add_argument("--name", default="exp")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    data_root = Path(args.data_root).resolve()
    base_yaml = Path(args.base_yaml).resolve()
    base_cfg = load_base_yaml(base_yaml)

    images = find_pairs(data_root)
    print(f"Found {len(images)} paired images.")

    kf = KFold(n_splits=args.k, shuffle=True, random_state=args.seed)

    for fold, (train_idx, val_idx) in enumerate(kf.split(images), start=1):
        fold_dir = data_root / f"kfold/fold_{fold}"
        train_list = fold_dir / "train.txt"
        val_list = fold_dir / "val.txt"
        write_list([images[i] for i in train_idx], train_list)
        write_list([images[i] for i in val_idx], val_list)

        fold_yaml = fold_dir / f"fold_{fold}.yaml"
        make_fold_yaml(base_cfg, train_list, val_list, fold_yaml)

        print(f"\n=== Fold {fold}/{args.k} ===")
        print(f"Train images: {len(train_idx)}  |  Val images: {len(val_idx)}")
        print(f"YAML: {fold_yaml}")

        model = YOLO(args.model)
        model.train(
            data=str(fold_yaml),
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            degrees=args.degrees,     # rotate up to ±degrees
            # You can tweak other augs if desired:
            # fliplr=0.5, flipud=0.5, mosaic=0.0, perspective=0.0, shear=0.0
            project=args.project,
            name=f"{args.name}_fold{fold}",
            exist_ok=True,
        )

if __name__ == "__main__":
    main()
