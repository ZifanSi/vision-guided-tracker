import time
import logging
import numpy as np
import torch
import cv2
from typing import List, Dict, Tuple, Optional, Any, Union

log = logging.getLogger(__name__)


def label_sam_masks_with_gdino(
    img_bgr: np.ndarray,
    sam_masks: Union[List[dict], np.ndarray],
    text_prompt: str,
    gdino_model: Any,
    box_score_thresh: float = 0.25,
    min_mask_area: int = 100,
    use_crop: bool = True,
    padding: int = 10,
    batch_process: bool = False
) -> List[Dict[str, Any]]:
    """
    Label SAM masks by sending each masked region to GDINO for classification.
    
    Args:
        img_bgr: Original image in BGR format
        sam_masks: SAM masks (list of dicts with 'segmentation' key or numpy array)
        text_prompt: Text prompt for GDINO labeling
        gdino_model: GDINO model instance
        box_score_thresh: Confidence threshold for GDINO
        min_mask_area: Minimum mask area to process
        use_crop: If True, crops masked region; if False, uses full image with mask
        padding: Padding around crop region (if use_crop=True)
        batch_process: If True, batch process multiple masks (experimental)
        
    Returns:
        List of dicts with keys:
            - 'mask': Original binary mask
            - 'bbox': Bounding box [x, y, w, h]
            - 'label': GDINO label for this mask
            - 'score': Confidence score
            - 'area': Mask area in pixels
    """
    # Parse masks to uniform format
    parsed_masks = _parse_sam_masks(sam_masks)
    
    if len(parsed_masks) == 0:
        log.warning("[SAM-GDINO] No masks to process")
        return []
    
    log.info(f"[SAM-GDINO] Processing {len(parsed_masks)} masks with prompt='{text_prompt}'")
    
    results = []
    
    if batch_process:
        # Process all masks in batches (experimental)
        results = _batch_process_masks(
            img_bgr, parsed_masks, text_prompt, gdino_model,
            box_score_thresh, min_mask_area, use_crop, padding
        )
    else:
        # Process each mask individually
        for idx, mask_data in enumerate(parsed_masks):
            mask = mask_data['mask']
            
            # Skip small masks
            area = np.sum(mask)
            if area < min_mask_area:
                continue
            
            # Get label for this specific mask
            label_result = _label_single_mask(
                img_bgr, mask, text_prompt, gdino_model,
                box_score_thresh, use_crop, padding
            )
            
            # Calculate bounding box
            bbox = _mask_to_bbox(mask)
            
            results.append({
                'mask': mask,
                'bbox': bbox,
                'label': label_result['label'],
                'score': label_result['score'],
                'area': int(area),
                'index': idx
            })
            
            log.debug(f"[SAM-GDINO] Mask {idx}: label='{label_result['label']}' score={label_result['score']:.3f}")
    
    # Summary
    labeled_count = sum(1 for r in results if r['label'] is not None)
    log.info(f"[SAM-GDINO] Labeled {labeled_count}/{len(results)} masks successfully")
    
    return results


def _label_single_mask(
    img_bgr: np.ndarray,
    mask: np.ndarray,
    text_prompt: str,
    gdino_model: Any,
    box_score_thresh: float,
    use_crop: bool,
    padding: int
) -> Dict[str, Any]:
    """
    Label a single mask by sending the masked region to GDINO.
    
    Args:
        img_bgr: Original image in BGR
        mask: Binary mask
        text_prompt: GDINO prompt
        gdino_model: GDINO model
        box_score_thresh: Confidence threshold
        use_crop: Whether to crop to mask region
        padding: Padding for crop
        
    Returns:
        Dict with 'label' and 'score'
    """
    if use_crop:
        # Crop the image to mask region with padding
        cropped_img, crop_info = _crop_to_mask(img_bgr, mask, padding)
        
        # Create mask for cropped region
        y1, y2, x1, x2 = crop_info
        cropped_mask = mask[y1:y2, x1:x2]
        
        # Apply mask to cropped image (set non-mask areas to white/black)
        masked_crop = _apply_mask_to_image(cropped_img, cropped_mask, background='white')
        
        # Send to GDINO
        gdino_input = masked_crop
    else:
        # Use full image with mask applied
        gdino_input = _apply_mask_to_image(img_bgr, mask, background='blur')
    
    # Run GDINO on the masked region
    try:
        t0 = time.perf_counter()
        result = gdino_model.predict_with_caption(
            image=gdino_input[:, :, ::-1],  # BGR->RGB
            caption=text_prompt,
            box_threshold=box_score_thresh,
            text_threshold=0.25
        )
        elapsed = (time.perf_counter() - t0) * 1000
        log.debug(f"[GDINO] Inference took {elapsed:.1f}ms")
        
    except Exception as e:
        log.error(f"[GDINO] Failed: {e}")
        return {'label': None, 'score': 0.0}
    
    # Parse GDINO result
    label, score = _parse_gdino_result_for_mask(result)
    
    return {'label': label, 'score': score}


def _parse_gdino_result_for_mask(result: Any) -> Tuple[Optional[str], float]:
    """
    Parse GDINO result for a single masked region.
    
    Args:
        result: GDINO output (tuple of detections and labels)
        
    Returns:
        Tuple of (label, score) - returns best detection or (None, 0.0)
    """
    if result is None:
        return None, 0.0
    
    if isinstance(result, tuple) and len(result) == 2:
        dets, labels = result
        
        if hasattr(dets, 'xyxy') and hasattr(dets, 'confidence'):
            if len(dets.xyxy) == 0:
                return None, 0.0
            
            # Get the highest confidence detection
            confidences = dets.confidence
            best_idx = np.argmax(confidences)
            
            label = labels[best_idx] if best_idx < len(labels) else None
            score = float(confidences[best_idx])
            
            return label, score
    
    return None, 0.0


def _crop_to_mask(
    img: np.ndarray,
    mask: np.ndarray,
    padding: int = 10
) -> Tuple[np.ndarray, Tuple[int, int, int, int]]:
    """
    Crop image to mask bounding box with padding.
    
    Args:
        img: Input image
        mask: Binary mask
        padding: Padding around mask
        
    Returns:
        Tuple of (cropped_image, (y1, y2, x1, x2))
    """
    # Find mask bounds
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    
    if not rows.any() or not cols.any():
        return img, (0, img.shape[0], 0, img.shape[1])
    
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    
    # Add padding
    y1 = max(0, rmin - padding)
    y2 = min(img.shape[0], rmax + padding + 1)
    x1 = max(0, cmin - padding)
    x2 = min(img.shape[1], cmax + padding + 1)
    
    cropped = img[y1:y2, x1:x2].copy()
    
    return cropped, (y1, y2, x1, x2)


def _apply_mask_to_image(
    img: np.ndarray,
    mask: np.ndarray,
    background: str = 'white'
) -> np.ndarray:
    """
    Apply mask to image with specified background.
    
    Args:
        img: Input image
        mask: Binary mask
        background: 'white', 'black', 'blur', or 'gray'
        
    Returns:
        Masked image
    """
    result = img.copy()
    
    if background == 'white':
        result[~mask] = 255
    elif background == 'black':
        result[~mask] = 0
    elif background == 'gray':
        result[~mask] = 128
    elif background == 'blur':
        # Blur the background
        blurred = cv2.GaussianBlur(img, (21, 21), 0)
        result[~mask] = blurred[~mask]
    
    return result


def _parse_sam_masks(masks: Union[List[dict], np.ndarray]) -> List[dict]:
    """Parse SAM masks into uniform format."""
    parsed = []
    
    if isinstance(masks, np.ndarray):
        if masks.ndim == 3:  # (N, H, W)
            for i in range(masks.shape[0]):
                parsed.append({'mask': masks[i].astype(bool)})
        elif masks.ndim == 2:  # Single mask
            parsed.append({'mask': masks.astype(bool)})
    
    elif isinstance(masks, list):
        for mask_item in masks:
            if isinstance(mask_item, dict):
                # SAM format with 'segmentation' key
                if 'segmentation' in mask_item:
                    parsed.append({'mask': mask_item['segmentation'].astype(bool)})
            elif isinstance(mask_item, np.ndarray):
                parsed.append({'mask': mask_item.astype(bool)})
    
    return parsed


def _mask_to_bbox(mask: np.ndarray) -> Optional[List[int]]:
    """Convert mask to bounding box [x, y, w, h]."""
    if not mask.any():
        return None
    
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    
    return [int(cmin), int(rmin), int(cmax - cmin + 1), int(rmax - rmin + 1)]


def _batch_process_masks(
    img_bgr: np.ndarray,
    parsed_masks: List[dict],
    text_prompt: str,
    gdino_model: Any,
    box_score_thresh: float,
    min_mask_area: int,
    use_crop: bool,
    padding: int
) -> List[Dict[str, Any]]:
    """
    Batch process multiple masks (experimental).
    Could be optimized for better performance.
    """
    # This is a placeholder for potential batch processing optimization
    # Currently just calls single mask processing
    results = []
    
    for idx, mask_data in enumerate(parsed_masks):
        mask = mask_data['mask']
        area = np.sum(mask)
        
        if area < min_mask_area:
            continue
        
        label_result = _label_single_mask(
            img_bgr, mask, text_prompt, gdino_model,
            box_score_thresh, use_crop, padding
        )
        
        bbox = _mask_to_bbox(mask)
        
        results.append({
            'mask': mask,
            'bbox': bbox,
            'label': label_result['label'],
            'score': label_result['score'],
            'area': int(area),
            'index': idx
        })
    
    return results


# ============= Alternative: Create composite image for GDINO =============

def create_gdino_composite_image(
    img_bgr: np.ndarray,
    sam_masks: Union[List[dict], np.ndarray],
    min_mask_area: int = 100,
    grid_size: Optional[Tuple[int, int]] = None,
    segment_size: Tuple[int, int] = (224, 224),
    padding: int = 5
) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
    """
    Create a composite grid image of all SAM masks for batch GDINO processing.
    
    This is an alternative approach where all masks are arranged in a grid
    and sent to GDINO in one shot, then results are mapped back.
    
    Args:
        img_bgr: Original image
        sam_masks: SAM masks
        min_mask_area: Minimum area filter
        grid_size: Grid dimensions (rows, cols)
        segment_size: Size of each segment in grid
        padding: Padding between segments
        
    Returns:
        Tuple of (composite_image, mask_info_list)
        mask_info_list contains position mapping for each mask
    """
    parsed_masks = _parse_sam_masks(sam_masks)
    valid_masks = []
    
    # Filter valid masks
    for idx, mask_data in enumerate(parsed_masks):
        mask = mask_data['mask']
        area = np.sum(mask)
        if area >= min_mask_area:
            valid_masks.append((idx, mask))
    
    if not valid_masks:
        return np.zeros((segment_size[1], segment_size[0], 3), dtype=np.uint8), []
    
    # Determine grid size
    n_masks = len(valid_masks)
    if grid_size is None:
        cols = int(np.ceil(np.sqrt(n_masks)))
        rows = int(np.ceil(n_masks / cols))
    else:
        rows, cols = grid_size
    
    # Create composite image
    grid_h = rows * (segment_size[1] + padding) + padding
    grid_w = cols * (segment_size[0] + padding) + padding
    composite = np.ones((grid_h, grid_w, 3), dtype=np.uint8) * 255
    
    mask_info = []
    
    for grid_idx, (orig_idx, mask) in enumerate(valid_masks):
        if grid_idx >= rows * cols:
            break
        
        # Get grid position
        row = grid_idx // cols
        col = grid_idx % cols
        y = row * (segment_size[1] + padding) + padding
        x = col * (segment_size[0] + padding) + padding
        
        # Crop and resize mask region
        cropped, crop_info = _crop_to_mask(img_bgr, mask, padding=10)
        masked = _apply_mask_to_image(cropped, mask[crop_info[0]:crop_info[1], crop_info[2]:crop_info[3]], 'white')
        
        # Resize to segment size
        resized = cv2.resize(masked, segment_size, interpolation=cv2.INTER_AREA)
        
        # Place in grid
        composite[y:y+segment_size[1], x:x+segment_size[0]] = resized
        
        # Store mapping info
        mask_info.append({
            'original_index': orig_idx,
            'grid_position': (row, col),
            'grid_bbox': [x, y, segment_size[0], segment_size[1]],
            'mask': mask,
            'area': int(np.sum(mask))
        })
    
    return composite, mask_info
