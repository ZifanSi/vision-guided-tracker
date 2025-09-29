import numpy as np
import cv2
from typing import List, Dict, Union, Optional, Tuple


def extract_segmented_regions(
    image: np.ndarray,
    masks: Union[List[dict], np.ndarray],
    background_color: Optional[Tuple[int, int, int]] = None,
    crop_to_bbox: bool = True,
    min_area: int = 100,
    return_info: bool = False
) -> List[Union[np.ndarray, Dict]]:
    """
    Extract individual segmented regions from an image using SAM masks.
    
    Args:
        image: Original image in BGR or RGB format
        masks: Either a list of mask dictionaries from SAM or numpy array of masks
               If dict, expects key 'segmentation' for the mask
               If array, expects shape (N, H, W) where N is number of masks
        background_color: RGB color for background pixels. If None, uses transparency (alpha channel)
        crop_to_bbox: If True, crops each segment to its bounding box. If False, keeps original image size
        min_area: Minimum area (in pixels) for a segment to be included
        return_info: If True, returns dict with image and metadata. If False, returns just the image
        
    Returns:
        List of segmented images in RGB format (or RGBA if background_color is None)
        If return_info=True, returns list of dicts with keys:
            - 'image': segmented image
            - 'bbox': bounding box [x, y, w, h]
            - 'area': segment area in pixels
            - 'mask': original binary mask
            - 'index': original mask index
    """
    # Convert BGR to RGB if needed
    if len(image.shape) == 3 and image.shape[2] == 3:
        # Assuming BGR if it comes from cv2.imread
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    else:
        image_rgb = image.copy()
    
    # Parse masks into uniform format
    parsed_masks = _parse_masks_for_extraction(masks)
    
    if len(parsed_masks) == 0:
        print("No masks to extract")
        return []
    
    extracted_segments = []
    
    for idx, mask_data in enumerate(parsed_masks):
        mask = mask_data['mask']
        
        if mask is None or not mask.any():
            continue
            
        # Check minimum area
        area = np.sum(mask)
        if area < min_area:
            continue
        
        # Extract the segment
        segment = _extract_single_segment(
            image_rgb, 
            mask, 
            background_color,
            crop_to_bbox
        )
        
        if segment is None:
            continue
        
        if return_info:
            # Calculate bounding box
            bbox = _get_mask_bbox(mask)
            
            extracted_segments.append({
                'image': segment,
                'bbox': bbox,
                'area': int(area),
                'mask': mask,
                'index': idx
            })
        else:
            extracted_segments.append(segment)
    
    return extracted_segments


def extract_segmented_regions_with_labels(
    image: np.ndarray,
    masks: Union[List[dict], np.ndarray],
    labels: Optional[List[str]] = None,
    scores: Optional[List[float]] = None,
    background_color: Optional[Tuple[int, int, int]] = None,
    crop_to_bbox: bool = True,
    min_area: int = 100,
    add_label_to_image: bool = False,
    label_color: Tuple[int, int, int] = (255, 255, 255),
    label_background: Optional[Tuple[int, int, int]] = (0, 0, 0)
) -> List[Dict]:
    """
    Extract segmented regions with associated labels and metadata.
    
    Args:
        image: Original image in BGR or RGB format
        masks: SAM masks
        labels: Optional labels for each mask (e.g., from GDINO)
        scores: Optional confidence scores for each mask
        background_color: RGB color for background. None for transparency
        crop_to_bbox: Whether to crop to bounding box
        min_area: Minimum segment area in pixels
        add_label_to_image: If True, adds label text to the image
        label_color: RGB color for label text
        label_background: RGB color for label background (None for no background)
        
    Returns:
        List of dictionaries containing:
            - 'image': segmented image
            - 'label': associated label (if provided)
            - 'score': confidence score (if provided)
            - 'bbox': bounding box
            - 'area': segment area
            - 'mask': original mask
            - 'index': original index
    """
    # Get base extractions with info
    segments = extract_segmented_regions(
        image=image,
        masks=masks,
        background_color=background_color,
        crop_to_bbox=crop_to_bbox,
        min_area=min_area,
        return_info=True
    )
    
    # Add labels and scores
    for seg_dict in segments:
        idx = seg_dict['index']
        
        # Add label if available
        if labels and idx < len(labels):
            seg_dict['label'] = labels[idx]
            
            # Optionally add label to image
            if add_label_to_image and labels[idx]:
                seg_dict['image'] = _add_label_to_image(
                    seg_dict['image'],
                    labels[idx],
                    label_color,
                    label_background
                )
        else:
            seg_dict['label'] = None
        
        # Add score if available
        if scores and idx < len(scores):
            seg_dict['score'] = scores[idx]
        else:
            seg_dict['score'] = None
    
    return segments


def save_segmented_regions(
    segments: Union[List[np.ndarray], List[Dict]],
    output_dir: str,
    prefix: str = "segment",
    image_format: str = "png"
) -> List[str]:
    """
    Save extracted segments to individual files.
    
    Args:
        segments: List of segment images or dicts from extract_segmented_regions
        output_dir: Directory to save images
        prefix: Prefix for filenames
        image_format: Image format (png, jpg, etc.)
        
    Returns:
        List of saved file paths
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    saved_paths = []
    
    for idx, segment in enumerate(segments):
        # Extract image from dict if needed
        if isinstance(segment, dict):
            img = segment['image']
            # Use label in filename if available
            label = segment.get('label', '')
            score = segment.get('score', None)
            
            if label:
                filename = f"{prefix}_{idx:03d}_{label}"
                if score is not None:
                    filename += f"_{score:.2f}"
            else:
                filename = f"{prefix}_{idx:03d}"
        else:
            img = segment
            filename = f"{prefix}_{idx:03d}"
        
        # Ensure valid filename
        filename = "".join(c for c in filename if c.isalnum() or c in ('_', '-', '.'))
        filepath = os.path.join(output_dir, f"{filename}.{image_format}")
        
        # Convert RGBA to RGB for formats that don't support alpha
        if image_format.lower() in ['jpg', 'jpeg'] and img.shape[2] == 4:
            # Create white background
            rgb_img = np.ones((img.shape[0], img.shape[1], 3), dtype=np.uint8) * 255
            # Apply alpha blending
            alpha = img[:, :, 3:4] / 255.0
            rgb_img = (1 - alpha) * rgb_img + alpha * img[:, :, :3]
            img = rgb_img.astype(np.uint8)
        
        # Convert RGB to BGR for cv2.imwrite
        if len(img.shape) == 3:
            if img.shape[2] == 3:
                img_bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            elif img.shape[2] == 4:
                img_bgr = cv2.cvtColor(img, cv2.COLOR_RGBA2BGRA)
            else:
                img_bgr = img
        else:
            img_bgr = img
        
        cv2.imwrite(filepath, img_bgr)
        saved_paths.append(filepath)
    
    print(f"Saved {len(saved_paths)} segments to {output_dir}")
    return saved_paths


def create_segment_grid(
    segments: Union[List[np.ndarray], List[Dict]],
    grid_size: Optional[Tuple[int, int]] = None,
    segment_size: Tuple[int, int] = (256, 256),
    background_color: Tuple[int, int, int] = (255, 255, 255),
    padding: int = 10,
    add_labels: bool = True
) -> np.ndarray:
    """
    Create a grid visualization of all segments.
    
    Args:
        segments: List of segment images or dicts
        grid_size: (rows, cols) for grid. If None, automatically determined
        segment_size: Size to resize each segment for grid
        background_color: RGB color for grid background
        padding: Pixels between segments
        add_labels: If True and segments are dicts with labels, add labels
        
    Returns:
        Grid image in RGB format
    """
    if len(segments) == 0:
        return np.ones((segment_size[1], segment_size[0], 3), dtype=np.uint8) * 255
    
    # Extract images and labels
    images = []
    labels = []
    
    for seg in segments:
        if isinstance(seg, dict):
            images.append(seg['image'])
            labels.append(seg.get('label', ''))
        else:
            images.append(seg)
            labels.append('')
    
    n_segments = len(images)
    
    # Determine grid size
    if grid_size is None:
        cols = int(np.ceil(np.sqrt(n_segments)))
        rows = int(np.ceil(n_segments / cols))
    else:
        rows, cols = grid_size
    
    # Calculate grid image size
    grid_width = cols * (segment_size[0] + padding) + padding
    grid_height = rows * (segment_size[1] + padding) + padding
    
    # Create grid image
    grid_img = np.ones((grid_height, grid_width, 3), dtype=np.uint8)
    grid_img[:] = background_color
    
    for idx, img in enumerate(images):
        if idx >= rows * cols:
            break
        
        row = idx // cols
        col = idx % cols
        
        # Resize segment to fit
        resized = _resize_with_aspect_ratio(img, segment_size, background_color)
        
        # Calculate position
        y = row * (segment_size[1] + padding) + padding
        x = col * (segment_size[0] + padding) + padding
        
        # Place segment in grid
        grid_img[y:y+segment_size[1], x:x+segment_size[0]] = resized[:, :, :3]
        
        # Add label if available
        if add_labels and labels[idx]:
            _add_text_to_grid(grid_img, labels[idx], (x, y + segment_size[1] - 25))
    
    return grid_img


# --- Helper Functions ---

def _parse_masks_for_extraction(masks: Union[List[dict], np.ndarray]) -> List[dict]:
    """Parse masks into uniform format for extraction."""
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
                # SAM format
                mask = mask_item.get('segmentation')
                if mask is not None:
                    parsed.append({'mask': mask.astype(bool)})
            elif isinstance(mask_item, np.ndarray):
                parsed.append({'mask': mask_item.astype(bool)})
    
    return parsed


def _extract_single_segment(
    image: np.ndarray,
    mask: np.ndarray,
    background_color: Optional[Tuple[int, int, int]],
    crop_to_bbox: bool
) -> Optional[np.ndarray]:
    """Extract a single segment with optional cropping."""
    if not mask.any():
        return None
    
    # Create output image with alpha channel if no background color specified
    if background_color is None:
        # RGBA format
        output = np.zeros((*image.shape[:2], 4), dtype=np.uint8)
        output[:, :, :3] = image
        output[:, :, 3] = mask.astype(np.uint8) * 255
    else:
        # RGB format with colored background
        output = np.ones_like(image, dtype=np.uint8)
        output[:] = background_color
        output[mask] = image[mask]
    
    # Crop to bounding box if requested
    if crop_to_bbox:
        bbox = _get_mask_bbox(mask)
        if bbox is not None:
            x, y, w, h = bbox
            output = output[y:y+h, x:x+w]
    
    return output


def _get_mask_bbox(mask: np.ndarray) -> Optional[List[int]]:
    """Get bounding box [x, y, w, h] from mask."""
    if not mask.any():
        return None
    
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]
    
    return [int(cmin), int(rmin), int(cmax - cmin + 1), int(rmax - rmin + 1)]


def _add_label_to_image(
    image: np.ndarray,
    label: str,
    text_color: Tuple[int, int, int],
    background_color: Optional[Tuple[int, int, int]]
) -> np.ndarray:
    """Add label text to an image."""
    img_with_label = image.copy()
    
    # Set up text parameters
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.6
    thickness = 2
    
    # Get text size
    (text_width, text_height), baseline = cv2.getTextSize(
        label, font, font_scale, thickness
    )
    
    # Position at top-left with padding
    x, y = 10, 30
    
    # Add background rectangle if specified
    if background_color is not None:
        cv2.rectangle(
            img_with_label,
            (x - 5, y - text_height - 5),
            (x + text_width + 5, y + 5),
            background_color,
            -1
        )
    
    # Add text (need to convert RGB to BGR for cv2)
    img_bgr = cv2.cvtColor(img_with_label, cv2.COLOR_RGB2BGR)
    cv2.putText(
        img_bgr,
        label,
        (x, y),
        font,
        font_scale,
        text_color[::-1],  # Convert RGB to BGR
        thickness,
        cv2.LINE_AA
    )
    
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


def _resize_with_aspect_ratio(
    image: np.ndarray,
    target_size: Tuple[int, int],
    background_color: Tuple[int, int, int]
) -> np.ndarray:
    """Resize image maintaining aspect ratio."""
    h, w = image.shape[:2]
    target_w, target_h = target_size
    
    # Calculate scaling factor
    scale = min(target_w / w, target_h / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    # Resize image
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    
    # Create canvas with background color
    canvas = np.ones((target_h, target_w, 3), dtype=np.uint8)
    canvas[:] = background_color
    
    # Center the resized image
    y_offset = (target_h - new_h) // 2
    x_offset = (target_w - new_w) // 2
    
    # Handle both RGB and RGBA
    if resized.shape[2] == 4:
        # Apply alpha blending
        alpha = resized[:, :, 3:4] / 255.0
        canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = \
            (1 - alpha) * canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] + \
            alpha * resized[:, :, :3]
    else:
        canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized[:, :, :3]
    
    return canvas


def _add_text_to_grid(
    image: np.ndarray,
    text: str,
    position: Tuple[int, int],
    font_scale: float = 0.5
) -> None:
    """Add text directly to grid image."""
    img_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    cv2.putText(
        img_bgr,
        text,
        position,
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        (0, 0, 0),  # Black text
        1,
        cv2.LINE_AA
    )
    image[:] = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)