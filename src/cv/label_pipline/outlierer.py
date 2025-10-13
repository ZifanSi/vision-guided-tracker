import cv2
import numpy as np
import torch
from pathlib import Path
from PIL import Image
import matplotlib.pyplot as plt
from typing import List, Dict, Tuple
import os

# Install required packages:
# pip install torch torchvision
# pip install git+https://github.com/facebookresearch/segment-anything.git
# pip install git+https://github.com/IDEA-Research/GroundingDINO.git
# pip install opencv-python pillow matplotlib supervision

from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
from groundingdino.util.inference import load_model, load_image, predict

class VideoSegmentationPipeline:
    def __init__(self, sam_checkpoint, sam_model_type="vit_h", 
                 gdino_config=r"C:\Personal-Project\vision-guided-tracker\src\cv\models\DINO\GroundingDINO_SwinT_OGC.py",
                 gdino_checkpoint=r"C:\Personal-Project\vision-guided-tracker\src\cv\data\weights\groundingdino_swint_ogc.pth"):
        """
        Initialize the pipeline with SAM and Grounding DINO models
        
        Args:
            sam_checkpoint: Path to SAM checkpoint (e.g., 'sam_vit_h_4b8939.pth')
            sam_model_type: SAM model type ('vit_h', 'vit_l', or 'vit_b')
            gdino_config: Path to Grounding DINO config file
            gdino_checkpoint: Path to Grounding DINO checkpoint
        """
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Using device: {self.device}")
        
        # Initialize SAM
        print("Loading SAM model...")
        sam = sam_model_registry[sam_model_type](checkpoint=sam_checkpoint)
        sam.to(device=self.device)
        self.mask_generator = SamAutomaticMaskGenerator(sam)
        
        # Initialize Grounding DINO
        print("Loading Grounding DINO model...")
        self.gdino_model = load_model(gdino_config, gdino_checkpoint)
        
        self.output_dir = Path(r"C:\Personal-Project\vision-guided-tracker\src\cv\data\pipeline_output")
        self.output_dir.mkdir(exist_ok=True)
        
    def step1_video_to_images(self, video_path: str, frame_interval: int = 30) -> List[np.ndarray]:
        """
        Convert video to images
        
        Args:
            video_path: Path to input video
            frame_interval: Extract every Nth frame (default: 30)
            
        Returns:
            List of frames as numpy arrays
        """
        print(f"\n[STEP 1] Converting video to images...")
        cap = cv2.VideoCapture(video_path)
        frames = []
        frame_count = 0
        extracted_count = 0
        
        frames_dir = self.output_dir / "frames"
        frames_dir.mkdir(exist_ok=True)
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            if frame_count % frame_interval == 0:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append(frame_rgb)
                
                # Save frame
                frame_path = frames_dir / f"frame_{extracted_count:04d}.jpg"
                cv2.imwrite(str(frame_path), frame)
                extracted_count += 1
                
            frame_count += 1
            
        cap.release()
        print(f"Extracted {len(frames)} frames from video")
        return frames
    
    def step2_segment_with_sam(self, image: np.ndarray) -> List[Dict]:
        """
        Generate masks using SAM
        
        Args:
            image: Input image as numpy array
            
        Returns:
            List of mask dictionaries from SAM
        """
        print(f"[STEP 2] Generating masks with SAM...")
        masks = self.mask_generator.generate(image)
        print(f"Generated {len(masks)} masks")
        return masks
    
    def step3_extract_masks(self, image: np.ndarray, masks: List[Dict]) -> List[Tuple[np.ndarray, Dict]]:
        """
        Extract individual masked regions from image
        
        Args:
            image: Original image
            masks: List of mask dictionaries from SAM
            
        Returns:
            List of tuples (masked_image, mask_info)
        """
        print(f"[STEP 3] Extracting {len(masks)} individual masks...")
        extracted = []
        
        for idx, mask_data in enumerate(masks):
            mask = mask_data['segmentation']
            bbox = mask_data['bbox']  # [x, y, w, h]
            
            # Create masked image
            masked_img = image.copy()
            masked_img[~mask] = 0  # Set non-mask pixels to black
            
            # Crop to bounding box
            x, y, w, h = map(int, bbox)
            cropped = masked_img[y:y+h, x:x+w]
            
            extracted.append((cropped, mask_data))
            
        return extracted
    
    def step4_label_with_gdino(self, image: np.ndarray, text_prompt: str = "object. thing. item.",
                                box_threshold: float = 0.3, text_threshold: float = 0.25) -> List[Tuple[str, float]]:
        """
        Label image regions using Grounding DINO
        
        Args:
            image: Input image (cropped mask region)
            text_prompt: Text prompt for Grounding DINO
            box_threshold: Box confidence threshold
            text_threshold: Text confidence threshold
            
        Returns:
            List of (label, confidence) tuples
        """
        # Convert numpy array to PIL Image and save temporarily
        temp_path = self.output_dir / "temp_crop.jpg"
        Image.fromarray(image).save(temp_path)
        
        # Load and predict with Grounding DINO
        image_source, image_tensor = load_image(str(temp_path))
        boxes, logits, phrases = predict(
            model=self.gdino_model,
            image=image_tensor,
            caption=text_prompt,
            box_threshold=box_threshold,
            text_threshold=text_threshold,
            device=self.device
        )
        
        # Clean up temp file
        temp_path.unlink()
        
        # Return labels with confidence scores
        results = [(phrase, logit.item()) for phrase, logit in zip(phrases, logits)]
        return results if results else [("unknown", 0.0)]
    
    def step5_visualize_results(self, image: np.ndarray, masks: List[Dict], 
                                labels: List[List[Tuple[str, float]]], frame_idx: int = 0):
        """
        Visualize segmentation and labeling results
        
        Args:
            image: Original image
            masks: List of mask dictionaries
            labels: List of labels for each mask
            frame_idx: Frame index for saving
        """
        print(f"[STEP 5] Visualizing results...")
        
        fig, axes = plt.subplots(1, 2, figsize=(20, 10))
        
        # Left: All masks overlay
        axes[0].imshow(image)
        self._show_masks_on_image(image, masks, axes[0])
        axes[0].set_title(f"SAM Segmentation ({len(masks)} masks)")
        axes[0].axis('off')
        
        # Right: Labeled masks
        axes[1].imshow(image)
        self._show_labeled_masks(image, masks, labels, axes[1])
        axes[1].set_title("Grounding DINO Labels")
        axes[1].axis('off')
        
        plt.tight_layout()
        
        # Save result
        result_path = self.output_dir / f"result_frame_{frame_idx:04d}.jpg"
        plt.savefig(result_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Saved result to {result_path}")
        
    def _show_masks_on_image(self, image, masks, ax):
        """Helper to overlay masks on image"""
        sorted_masks = sorted(masks, key=lambda x: x['area'], reverse=True)
        
        for mask_data in sorted_masks:
            mask = mask_data['segmentation']
            color = np.random.random(3)
            
            # Create colored overlay
            colored_mask = np.zeros((*mask.shape, 4))
            colored_mask[mask] = [*color, 0.4]
            ax.imshow(colored_mask)
    
    def _show_labeled_masks(self, image, masks, labels, ax):
        """Helper to show masks with labels"""
        for idx, (mask_data, mask_labels) in enumerate(zip(masks, labels)):
            mask = mask_data['segmentation']
            bbox = mask_data['bbox']
            
            # Draw mask outline
            color = np.random.random(3)
            contours, _ = cv2.findContours(mask.astype(np.uint8), 
                                          cv2.RETR_EXTERNAL, 
                                          cv2.CHAIN_APPROX_SIMPLE)
            
            for contour in contours:
                contour = contour.squeeze()
                if len(contour.shape) == 2:
                    ax.plot(contour[:, 0], contour[:, 1], color=color, linewidth=2)
            
            # Add label text
            if mask_labels:
                label, conf = mask_labels[0]  # Take top label
                x, y, w, h = bbox
                ax.text(x, y - 5, f"{label} ({conf:.2f})", 
                       color='white', fontsize=10, 
                       bbox=dict(boxstyle='round', facecolor=color, alpha=0.8))
    
    def run_pipeline(self, video_path: str, frame_interval: int = 30, 
                     text_prompt: str = "object. thing. item. person. animal."):
        """
        Run the complete pipeline
        
        Args:
            video_path: Path to input video
            frame_interval: Extract every Nth frame
            text_prompt: Text prompt for object detection
        """
        print("="*60)
        print("STARTING VIDEO SEGMENTATION PIPELINE")
        print("="*60)
        
        # Step 1: Video to images
        frames = self.step1_video_to_images(video_path, frame_interval)
        
        # Process each frame
        for frame_idx, frame in enumerate(frames):
            print(f"\n{'='*60}")
            print(f"Processing frame {frame_idx + 1}/{len(frames)}")
            print(f"{'='*60}")
            
            # Step 2: Segment with SAM
            masks = self.step2_segment_with_sam(frame)
            
            # Step 3: Extract masks
            extracted_masks = self.step3_extract_masks(frame, masks)
            
            # Step 4: Label with Grounding DINO
            print(f"[STEP 4] Labeling {len(extracted_masks)} masks with Grounding DINO...")
            all_labels = []
            for idx, (masked_img, mask_data) in enumerate(extracted_masks):
                if masked_img.size > 0:  # Skip empty masks
                    labels = self.step4_label_with_gdino(masked_img, text_prompt)
                    all_labels.append(labels)
                    if labels and labels[0][0] != "unknown":
                        print(f"  Mask {idx}: {labels[0][0]} (conf: {labels[0][1]:.2f})")
                else:
                    all_labels.append([("empty", 0.0)])
            
            # Step 5: Visualize
            self.step5_visualize_results(frame, masks, all_labels, frame_idx)
        
        print(f"\n{'='*60}")
        print(f"PIPELINE COMPLETE! Results saved to {self.output_dir}")
        print(f"{'='*60}")


# Example usage
if __name__ == "__main__":
    # Initialize pipeline
    pipeline = VideoSegmentationPipeline(
        sam_checkpoint=r"C:\Personal-Project\vision-guided-tracker\src\cv\data\weights\sam_vit_h_4b8939.pth",  # Download from SAM repo
        sam_model_type="vit_h"
    )
    
    # Run pipeline on video
    pipeline.run_pipeline(
        video_path=r"C:\Personal-Project\vision-guided-tracker\src\cv\data\alot_of_things\ETS_launch_.mp4",
        frame_interval=2, 
        text_prompt="person. car. object. animal. building. tree."
    )