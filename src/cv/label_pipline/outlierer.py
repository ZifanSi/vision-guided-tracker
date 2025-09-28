import os, time, cv2, torch, numpy as np, logging
from typing import List, Tuple
from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
from groundingdino.util.inference import Model as GroundingDINO
from torchvision.ops import nms
from matplotlib import pyplot as plt
from torchvision.ops import box_convert
import supervision as sv
# ----------------------------
# Logging (switch to DEBUG for more)
# ----------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("SAM-GDINO")

# ----------------------------
# 1) Load Models
# ----------------------------
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

SAM_CKPT = r"C:\Personal-Project\vision-guided-tracker\src\cv\weights\sam_vit_h_4b8939.pth"
SAM_TYPE = "vit_h"

GDINO_CKPT = r"C:\Personal-Project\vision-guided-tracker\src\cv\weights\groundingdino_swint_ogc.pth"
GDINO_CFG  = r"C:\Personal-Project\vision-guided-tracker\src\cv\models\DINO\GroundingDINO_SwinT_OGC.py"

assert os.path.isfile(SAM_CKPT), f"SAM checkpoint not found: {SAM_CKPT}"
assert os.path.isfile(GDINO_CKPT), f"GroundingDINO checkpoint not found: {GDINO_CKPT}"
assert os.path.isfile(GDINO_CFG),  f"GroundingDINO config not found: {GDINO_CFG}"

log.info(f"Device: {DEVICE} | Torch {torch.__version__}")
log.info(f"SAM: {SAM_TYPE} @ {SAM_CKPT}")
log.info(f"GDINO: cfg={GDINO_CFG} ckpt={GDINO_CKPT}")

t0 = time.perf_counter()
sam = sam_model_registry[SAM_TYPE](checkpoint=SAM_CKPT).to(DEVICE).eval()
mask_gen = SamAutomaticMaskGenerator(
    model=sam,
    points_per_side=32,
    pred_iou_thresh=0.84,
    stability_score_thresh=0.92,
    box_nms_thresh=0.6,
)
log.info(f"Load SAM took {(time.perf_counter()-t0)*1000:.1f} ms")

t0 = time.perf_counter()
gdino = GroundingDINO(model_config_path=GDINO_CFG, model_checkpoint_path=GDINO_CKPT, device=DEVICE)
log.info(f"Load GroundingDINO took {(time.perf_counter()-t0)*1000:.1f} ms")

# ----------------------------
# 2) Helpers
# ----------------------------
def masks_to_xyxy(masks: List[dict], image_wh: Tuple[int,int]) -> torch.Tensor:
    W, H = image_wh
    log.debug(f"[masks_to_xyxy] masks={len(masks)} img={W}x{H}")
    boxes = []
    for k, m in enumerate(masks):
        if "bbox" not in m:
            log.warning(f"[masks_to_xyxy] mask #{k} missing 'bbox'; skipping")
            continue
        x, y, w, h = m["bbox"]
        boxes.append([x, y, x+w, y+h, float(m.get("stability_score", 0.0))])

    if not boxes:
        log.info("[masks_to_xyxy] 0 boxes after parsing masks")
        return torch.empty((0,4), dtype=torch.float32)

    boxes = torch.tensor(boxes, dtype=torch.float32)
    keep = nms(boxes[:, :4], boxes[:, 4], iou_threshold=0.6)
    boxes_kept = boxes[keep, :4]
    log.info(f"[masks_to_xyxy] proposals: {len(boxes)} -> after NMS: {len(boxes_kept)}")
    return boxes_kept

def showRBG(img_rgb: np.ndarray, title="Image"):
    plt.figure(figsize=(10,10))
    plt.imshow(img_rgb)
    plt.title(title)
    plt.axis('off')
    plt.show()

def showDINO(img_rgb: np.ndarray, dets : sv.Detections, labels):
    img = img_rgb.copy()
    h, w, _ = img.shape

    boxes = boxes * torch.Tensor([w, h, w, h])
    xyxy = box_convert(boxes=boxes, in_fmt="cxcywh", out_fmt="xyxy").numpy()
    for i, box in enumerate(xyxy):
        x1, y1, x2, y2 = map(int, box)
        cv2.rectangle(img, (x1, y1), (x2, y2), (0,255,0), 2)
        label = f"{scores[i]:.2f}"
        cv2.putText(img, label, (x1, max(0,y1-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2, cv2.LINE_AA)
    showRBG(img, title="GroundingDINO Detections")

def label_boxes_with_gdino(img_bgr: np.ndarray, boxes_xyxy: torch.Tensor,
                           text_prompt: str, box_score_thresh=0.25):
    log.info(f"[GDINO] prompt='{text_prompt}' | boxes_in={boxes_xyxy.size(0)}")
    if boxes_xyxy.numel() == 0:
        return []

    # --- Run GDINO (handle multiple return formats) ---
    t0 = time.perf_counter()
    showRBG(img_bgr[:, :, ::-1], title=text_prompt)
    try:
        result = gdino.predict_with_caption(
            image=img_bgr[:, :, ::-1],  # BGR->RGB
            caption=text_prompt,
            box_threshold=box_score_thresh,
            text_threshold=0.25
        )
    except Exception as e:
        log.exception(f"[GDINO] predict_with_caption failed: {e}")
        return [{"box": b.tolist(), "label": None, "score": None} for b in boxes_xyxy]
    log.info(f"[GDINO] predict_with_caption took {(time.perf_counter()-t0)*1000:.1f} ms")

    # --- Normalize result into gd_boxes (Nx4), gd_scores (N,), gd_labels (list[str]) ---
    gd_boxes, gd_scores, gd_labels = None, None, None

    def to_tensor(x, dtype=torch.float32):
        x = np.array(x) if not torch.is_tensor(x) else x.cpu().numpy()
        return torch.tensor(x, dtype=dtype)

    if result is None:
        log.warning("[GDINO] detections is None")
        return [{"box": b.tolist(), "label": None, "score": None} for b in boxes_xyxy]

    if isinstance(result, tuple):
        # Common patterns:
        # (detections, labels)  OR  (boxes, scores/logits, phrases)
        dets, labels = result
        showDINO(img_bgr[:, :, ::-1], dets, labels)  # visualize raw GDINO output
        if len(result) == 2:
            dets, labels = result
            # dets could be attr-obj or dict
            if hasattr(dets, "boxes"):
                gd_boxes = to_tensor(dets.boxes)
                gd_scores = to_tensor(getattr(dets, "scores", []))
            else:
                gd_boxes = to_tensor(dets.get("boxes", []))
                gd_scores = to_tensor(dets.get("scores", []))
            gd_labels = list(labels) if labels is not None else []
        elif len(result) == 3:
            boxes, scores, phrases = result
            gd_boxes  = to_tensor(boxes)
            gd_scores = to_tensor(scores)
            gd_labels = list(phrases)
        else:
            log.warning(f"[GDINO] unexpected tuple len={len(result)}; treating as empty")
            gd_boxes, gd_scores, gd_labels = torch.zeros((0,4)), torch.zeros((0,)), []
    else:
        # Single object or dict
        dets = result
        try:
            gd_boxes  = to_tensor(dets.boxes)
            gd_scores = to_tensor(getattr(dets, "scores", []))
            gd_labels = list(getattr(dets, "phrases", []))
        except AttributeError:
            gd_boxes  = to_tensor(dets.get("boxes", []))
            gd_scores = to_tensor(dets.get("scores", []))
            gd_labels = list(dets.get("phrases", []))

    # Safety: shapes/lengths
    if gd_boxes is None or gd_boxes.numel() == 0:
        log.warning("[GDINO] 0 detections; returning unlabeled proposals")
        return [{"box": b.tolist(), "label": None, "score": None} for b in boxes_xyxy]
    if gd_scores is None or gd_scores.numel() != gd_boxes.shape[0]:
        # pad/trim scores to match boxes
        n = gd_boxes.shape[0]
        s = gd_scores.numel() if gd_scores is not None else 0
        log.debug(f"[GDINO] score length mismatch boxes={n} scores={s}; fixing")
        if s < n:
            pad = torch.zeros(n - s, dtype=torch.float32)
            gd_scores = torch.cat([gd_scores if s > 0 else torch.zeros(0), pad], dim=0)
        else:
            gd_scores = gd_scores[:n]
    if gd_labels is None:
        gd_labels = []
    if len(gd_labels) != gd_boxes.shape[0]:
        # If model returns 1 label for whole caption, broadcast; else trim/pad
        if len(gd_labels) == 1:
            gd_labels = gd_labels * gd_boxes.shape[0]
        else:
            log.debug(f"[GDINO] label length mismatch boxes={gd_boxes.shape[0]} labels={len(gd_labels)}; fixing")
            gd_labels = (gd_labels[:gd_boxes.shape[0]] +
                         [""] * max(0, gd_boxes.shape[0] - len(gd_labels)))

    log.info(f"[GDINO] normalized: boxes={gd_boxes.size(0)} labels={len(gd_labels)} scores={gd_scores.numel()}")

    # --- IoU assignment from SAM boxes to GDINO detections ---
    def iou(a,b):
        tl = torch.max(a[:, None, :2], b[None, :, :2])
        br = torch.min(a[:, None, 2:], b[None, :, 2:])
        wh = (br - tl).clamp(min=0)
        inter = wh[..., 0] * wh[..., 1]
        area_a = (a[:, 2]-a[:, 0]) * (a[:, 3]-a[:, 1])
        area_b = (b[:, 2]-b[:, 0]) * (b[:, 3]-b[:, 1])
        union = area_a[:, None] + area_b[None, :] - inter
        return inter / union.clamp(min=1e-6)

    ious = iou(boxes_xyxy, gd_boxes)
    best_gdino = torch.argmax(ious, dim=1)
    best_iou = ious[torch.arange(ious.size(0)), best_gdino]

    out, labeled = [], 0
    for i, b in enumerate(boxes_xyxy):
        j = int(best_gdino[i])
        ok = bool(best_iou[i] >= 0.3)
        lbl = (gd_labels[j] if ok and j < len(gd_labels) and gd_labels[j] else None)
        scr = (float(gd_scores[j]) if ok and j < gd_scores.numel() else None)
        if ok and lbl is not None:
            labeled += 1
        out.append({"box": b.tolist(), "label": lbl, "score": scr})

    log.info(f"[GDINO] assigned labels: {labeled}/{boxes_xyxy.size(0)} (IoU>=0.3)")
    return out


def draw_dets(img_bgr: np.ndarray, dets: List[dict]):
    img = img_bgr.copy()
    for idx, d in enumerate(dets):
        try:
            x1, y1, x2, y2 = map(int, d["box"])
        except Exception:
            log.warning(f"[draw_dets] bad box for det #{idx}: {d}")
            continue
        cv2.rectangle(img, (x1, y1), (x2, y2), (0,255,0), 2)
        if d.get("label"):
            txt = f'{d["label"]} ({d["score"]:.2f})' if d.get("score") is not None else d["label"]
            cv2.putText(img, txt, (x1, max(0, y1-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,0), 2, cv2.LINE_AA)
    return img

# ----------------------------
# 3) Run on an image
# ----------------------------
def run_on_image(img_path: str, text_prompt: str, out_path: str):
    log.info(f"[IMAGE] input={img_path} out={out_path} prompt='{text_prompt}'")
    img = cv2.imread(img_path)
    assert img is not None, f"cannot read {img_path}"
    log.info(f"[IMAGE] shape={img.shape}")

    try:
        t0 = time.perf_counter()
        masks = mask_gen.generate(img)
        log.info(f"[SAM] generate (image) took {(time.perf_counter()-t0)*1000:.1f} ms")
    except Exception as e:
        log.exception(f"[SAM] generate failed on image: {e}")
        return

    boxes = masks_to_xyxy(masks, (img.shape[1], img.shape[0]))
    dets  = label_boxes_with_gdino(img, boxes, text_prompt)
    vis   = draw_dets(img, dets)

    ok = cv2.imwrite(out_path, vis)
    log.info(f"[IMAGE] write result -> {out_path} | ok={ok}")

# ----------------------------
# 4) Run on a video (per-frame)
# ----------------------------
def run_on_video(src_mp4: str, dst_mp4: str, text_prompt: str, every_n=1):
    log.info(f"[VIDEO] src={src_mp4} -> dst={dst_mp4} | prompt='{text_prompt}' | every_n={every_n}")
    cap = cv2.VideoCapture(src_mp4)
    assert cap.isOpened(), f"cannot open {src_mp4}"
    w  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps= cap.get(cv2.CAP_PROP_FPS) or 30
    out = cv2.VideoWriter(dst_mp4, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w,h))
    log.info(f"[VIDEO] size={w}x{h} fps={fps:.2f} total_frames={int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)}")

    fidx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            log.info("[VIDEO] end of stream or read error")
            break

        if fidx % every_n == 0:
            log.info(f"[Frame {fidx}] Processing...")
            try:
                t0 = time.perf_counter()
                masks = mask_gen.generate(frame)
                log.info(f"[SAM] generate (frame {fidx}) took {(time.perf_counter()-t0)*1000:.1f} ms")
            except Exception as e:
                log.exception(f"[SAM] generate failed at frame {fidx}: {e}")
                out.write(frame); fidx += 1; continue

            boxes = masks_to_xyxy(masks, (w, h))
            dets  = label_boxes_with_gdino(frame, boxes, text_prompt)
            frame = draw_dets(frame, dets)
            log.info(f"[Frame {fidx}] wrote frame with {len(dets)} dets (boxes_in={boxes.size(0)})")
        out.write(frame)
        fidx += 1

    cap.release(); out.release()
    log.info(f"[VIDEO] done. frames_processed={fidx}, output={dst_mp4}")

# ----------------------------
# 5) Example usage
# ----------------------------
if __name__ == "__main__":
    run_on_video(
        src_mp4 = r"C:\Personal-Project\vision-guided-tracker\src\cv\data\alot_of_things\Carleton__launch.mp4",
        dst_mp4 = r"C:\Personal-Project\vision-guided-tracker\src\cv\runs\detect\Carleton__launch.mp4",
        text_prompt = "rocket",
        every_n = 5
    )
