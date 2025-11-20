import os
import shutil
from pathlib import Path

# Set your source folder
SRC = Path(r"C:\Personal-Project\vision-guided-tracker\src\cv\data\grand_dataset\all_label")

IM_DIR = SRC / "images"
LB_DIR = SRC / "labels"
UNMATCHED_IMG = SRC / "unmatched_images"
UNMATCHED_LB = SRC / "unmatched_labels"

IM_DIR.mkdir(exist_ok=True)
LB_DIR.mkdir(exist_ok=True)
UNMATCHED_IMG.mkdir(exist_ok=True)
UNMATCHED_LB.mkdir(exist_ok=True)

# 1. Move files into images/ and labels/
for f in SRC.iterdir():
    if f.suffix.lower() in [".jpg", ".jpeg", ".png"]:
        shutil.move(str(f), IM_DIR / f.name)
    elif f.suffix.lower() == ".txt":
        shutil.move(str(f), LB_DIR / f.name)

# 2. Check alignment
images = {p.stem for p in IM_DIR.iterdir() if p.suffix.lower() in [".jpg", ".jpeg", ".png"]}
labels = {p.stem for p in LB_DIR.iterdir() if p.suffix.lower() == ".txt"}

missing_labels = images - labels
missing_images = labels - images

# Move unmatched
for name in missing_labels:
    img = IM_DIR / f"{name}.jpg"
    if not img.exists():
        img = IM_DIR / f"{name}.jpeg"
    if not img.exists():
        img = IM_DIR / f"{name}.png"
    if img.exists():
        shutil.move(str(img), UNMATCHED_IMG / img.name)

for name in missing_images:
    lb = LB_DIR / f"{name}.txt"
    if lb.exists():
        shutil.move(str(lb), UNMATCHED_LB / lb.name)

print("Done.")
print(f"Missing labels: {len(missing_labels)} moved to unmatched_images/")
print(f"Missing images: {len(missing_images)} moved to unmatched_labels/")
