###############################################
#                CONFIG AREA                  #
###############################################

# ---- Paths ----
SAM_CHECKPOINT = r"C:\Personal-Project\vision-guided-tracker\src\cv\data\weights\sam_vit_h_4b8939.pth"
SAM_MODEL_TYPE = "vit_h"

GDINO_CONFIG = r"C:\Personal-Project\vision-guided-tracker\src\cv\models\DINO\GroundingDINO_SwinT_OGC.py"
GDINO_CHECKPOINT = r"C:\Personal-Project\vision-guided-tracker\src\cv\data\weights\groundingdino_swint_ogc.pth"

INPUT_FOLDER = r"C:\Personal-Project\vision-guided-tracker\rocam_data_15000\data_15000\images\train"
OUTPUT_FOLDER = r"C:\Personal-Project\vision-guided-tracker\src\cv\data\pipeline_out"

# ---- Grounding DINO settings ----
TEXT_PROMPT = "person. car. object. animal. building. tree."
BOX_THRESHOLD = 0.3
TEXT_THRESHOLD = 0.25

# ---- NEW: limit number of images ----
# 0 or negative => use all images in folder
TOP_K_IMAGES = 1


###############################################
#              PIPELINE SCRIPT                #
###############################################

import cv2
import numpy as np
import torch
from pathlib import Path
from PIL import Image
import matplotlib.pyplot as plt
from typing import List, Dict, Tuple
import os

from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
from groundingdino.util.inference import load_model, load_image, predict


class SegmentationLabelingPipeline:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Using device: {self.device}")

        print("Loading SAM...")
        sam = sam_model_registry[SAM_MODEL_TYPE](checkpoint=SAM_CHECKPOINT)
        sam.to(self.device)
        self.mask_generator = SamAutomaticMaskGenerator(sam)

        print("Loading Grounding DINO...")
        self.gdino_model = load_model(GDINO_CONFIG, GDINO_CHECKPOINT)

        self.output_dir = Path(OUTPUT_FOLDER)
        self.output_dir.mkdir(exist_ok=True)

    def segment(self, image: np.ndarray):
        return self.mask_generator.generate(image)

    def extract_masks(self, image, masks):
        extracted = []
        for mask_data in masks:
            mask = mask_data["segmentation"]
            x, y, w, h = map(int, mask_data["bbox"])
            masked = image.copy()
            masked[~mask] = 0
            crop = masked[y:y + h, x:x + w]
            extracted.append((crop, mask_data))
        return extracted

    def label_with_gdino(self, crop_img):
        temp = self.output_dir / "temp_crop.jpg"
        Image.fromarray(crop_img).save(temp)

        _, tensor = load_image(str(temp))
        boxes, logits, phrases = predict(
            model=self.gdino_model,
            image=tensor,
            caption=TEXT_PROMPT,
            box_threshold=BOX_THRESHOLD,
            text_threshold=TEXT_THRESHOLD,
            device=self.device
        )
        temp.unlink()

        results = [(p, l.item()) for p, l in zip(phrases, logits)]
        return results if results else [("unknown", 0.0)]

    def visualize(self, image, masks, labels, output_name):
        fig, axes = plt.subplots(1, 2, figsize=(20, 10))

        axes[0].imshow(image)
        self._overlay_masks(image, masks, axes[0])
        axes[0].axis("off")
        axes[0].set_title("SAM Segmentation")

        axes[1].imshow(image)
        self._overlay_labels(image, masks, labels, axes[1])
        axes[1].axis("off")
        axes[1].set_title("Grounding DINO Labels")

        plt.tight_layout()
        plt.savefig(self.output_dir / output_name, dpi=150)
        plt.close()

    def _overlay_masks(self, image, masks, ax):
        for m in masks:
            mask = m["segmentation"]
            color = np.random.rand(3)
            colored = np.zeros((*mask.shape, 4))
            colored[mask] = [*color, 0.4]
            ax.imshow(colored)

    def _overlay_labels(self, image, masks, labels, ax):
        for m, labs in zip(masks, labels):
            x, y, w, h = map(int, m["bbox"])
            color = np.random.rand(3)

            contours, _ = cv2.findContours(
                m["segmentation"].astype(np.uint8),
                cv2.RETR_EXTERNAL,
                cv2.CHAIN_APPROX_SIMPLE
            )
            for c in contours:
                c = c.squeeze()
                if len(c.shape) == 2:
                    ax.plot(c[:, 0], c[:, 1], color=color, linewidth=2)

            label, conf = labs[0]
            ax.text(x, y - 5, f"{label} ({conf:.2f})",
                    color="white", fontsize=10,
                    bbox=dict(boxstyle='round', facecolor=color, alpha=0.8))

    # ---------- UPDATED: support top-k ----------
    def run_on_folder(self, folder_path: str):
        folder = Path(folder_path)
        images = sorted(
            [p for p in folder.iterdir()
             if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}]
        )

        if not images:
            print("No images found.")
            return

        # apply top-k limit from config
        if TOP_K_IMAGES > 0:
            images = images[:TOP_K_IMAGES]
        print(f"\nProcessing {len(images)} images (TOP_K_IMAGES = {TOP_K_IMAGES})...\n")

        for idx, img_path in enumerate(images):
            print(f"[{idx+1}/{len(images)}] {img_path.name}")

            bgr = cv2.imread(str(img_path))
            if bgr is None:
                print("   failed to load, skipping.")
                continue

            image = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

            masks = self.segment(image)
            crops = self.extract_masks(image, masks)

            lbls = []
            for crop, _ in crops:
                if crop.size == 0:
                    lbls.append([("empty", 0.0)])
                else:
                    lbls.append(self.label_with_gdino(crop))

            out_name = f"{img_path.stem}_labeled.jpg"
            self.visualize(image, masks, lbls, out_name)

        print("\nDone! Output saved to:", self.output_dir)


###############################################
#                MAIN ENTRY                  #
###############################################
if __name__ == "__main__":
    pipeline = SegmentationLabelingPipeline()
    pipeline.run_on_folder(INPUT_FOLDER)
