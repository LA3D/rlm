#!/usr/bin/env python3
"""
Extract and crop figures from OCR'd documents.

Uses detection metadata from DeepSeek-OCR to:
- Identify image regions and captions
- Crop figures from page images
- Optionally generate descriptions using VLM
"""

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from uuid import uuid4

from PIL import Image
from mlx_vlm import load, generate
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config

from ocr_processor import extract_detections


def norm_to_pixels(bbox: List[int], img_size: Tuple[int, int]) -> List[int]:
    """
    Convert normalized bounding box (0-1000) to pixel coordinates.

    Args:
        bbox: [x1, y1, x2, y2] in 0-1000 normalized space
        img_size: (width, height) of image in pixels

    Returns:
        [x1, y1, x2, y2] in pixel coordinates
    """
    w, h = img_size
    x1, y1, x2, y2 = bbox
    return [
        int(x1 / 1000 * w),
        int(y1 / 1000 * h),
        int(x2 / 1000 * w),
        int(y2 / 1000 * h),
    ]


class FigureExtractor:
    """Extract and process figures from OCR'd documents."""

    # Labels that indicate image content
    IMAGE_LABELS = {"image", "image_caption"}

    def __init__(
        self,
        pages_dir: Path,
        ocr_dir: Path,
        output_dir: Path,
        describe_figures: bool = False,
        model_path: Optional[str] = None
    ):
        """
        Initialize figure extractor.

        Args:
            pages_dir: Directory containing page_XXX.png files
            ocr_dir: Directory containing OCR markdown files
            output_dir: Directory for extracted figures
            describe_figures: Whether to generate VLM descriptions
            model_path: Model path for VLM descriptions (if describe_figures=True)
        """
        self.pages_dir = pages_dir
        self.ocr_dir = ocr_dir
        self.output_dir = output_dir
        self.describe_figures = describe_figures

        output_dir.mkdir(parents=True, exist_ok=True)

        # Load VLM for descriptions if needed
        self.model = None
        self.processor = None
        self.config = None

        if describe_figures:
            if model_path is None:
                model_path = "mlx-community/DeepSeek-OCR-2-bf16"
            print(f"Loading VLM for descriptions: {model_path}")
            self.model, self.processor = load(model_path)
            self.config = load_config(model_path)
            print("✓ VLM loaded")

    def extract_figures(self) -> List[Dict[str, Any]]:
        """
        Extract all figures from OCR'd pages.

        Returns:
            List of figure metadata dicts
        """
        page_images = sorted(self.pages_dir.glob("page_*.png"))
        page_mds = sorted(self.ocr_dir.glob("page_*.md"))

        if len(page_images) != len(page_mds):
            raise ValueError(
                f"Mismatch: {len(page_images)} page images but {len(page_mds)} OCR files"
            )

        print(f"\nExtracting figures from {len(page_images)} pages...")

        figures = []

        for page_idx, (img_path, md_path) in enumerate(zip(page_images, page_mds), start=1):
            # Read OCR text
            page_text = md_path.read_text(encoding="utf-8")

            # Extract detections
            detections = extract_detections(page_text)

            # Open page image
            with Image.open(img_path) as page_img:
                img_size = page_img.size

                # Find image detections
                for det in detections:
                    if det["label"] not in self.IMAGE_LABELS:
                        continue

                    # Process each bbox (could be multiple)
                    for bbox_idx, bbox_norm in enumerate(det["bboxes"]):
                        bbox_px = norm_to_pixels(bbox_norm, img_size)

                        # Crop figure
                        crop = page_img.crop(bbox_px)

                        # Save cropped figure
                        fig_name = f"fig_page{page_idx:03d}_{bbox_idx+1:02d}.png"
                        fig_path = self.output_dir / fig_name
                        crop.save(fig_path)

                        figure = {
                            "id": str(uuid4()),
                            "page": page_idx,
                            "label": det["label"],
                            "bbox_norm": bbox_norm,
                            "bbox_px": bbox_px,
                            "image_path": str(fig_path),
                            "page_text": page_text,
                        }

                        figures.append(figure)

            if page_idx % 10 == 0:
                print(f"  Processed {page_idx}/{len(page_images)} pages...")

        print(f"\n✓ Extracted {len(figures)} figures to {self.output_dir}")

        # Generate descriptions if requested
        if self.describe_figures:
            print("\nGenerating VLM descriptions...")
            self._add_descriptions(figures)

        return figures

    def _add_descriptions(self, figures: List[Dict[str, Any]]) -> None:
        """
        Add VLM-generated descriptions to figures.

        Args:
            figures: List of figure dicts to augment with descriptions
        """
        describe_prompt = (
            "<|grounding|>Describe this image in detail for a technical document index. "
            "Focus on what is shown, key elements, and any notable features. "
            "Do not mention that you are looking at an 'image' or 'figure'."
        )

        for idx, fig in enumerate(figures, start=1):
            print(f"  [{idx}/{len(figures)}] Describing {Path(fig['image_path']).name}...")

            images = [fig["image_path"]]
            formatted_prompt = apply_chat_template(
                self.processor,
                self.config,
                describe_prompt,
                num_images=len(images),
            )

            output = generate(
                self.model,
                self.processor,
                formatted_prompt,
                images,
                temp=0.1,
                max_tokens=512,
                verbose=False,
            )

            description = getattr(output, "text", str(output)).strip()
            fig["description"] = description

            # Create text for RAG
            fig["text_for_rag"] = f"Description: {description}"

        print(f"✓ Added descriptions to {len(figures)} figures")

    def save_metadata(self, figures: List[Dict[str, Any]], output_path: Path) -> None:
        """Save figure metadata to JSON file."""
        output_path.write_text(
            json.dumps(figures, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        print(f"✓ Saved metadata to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract figures from OCR'd document pages"
    )
    parser.add_argument(
        "pages_dir",
        type=Path,
        help="Directory containing page_XXX.png files"
    )
    parser.add_argument(
        "ocr_dir",
        type=Path,
        help="Directory containing OCR markdown files"
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        help="Output directory for figures (default: figures/)"
    )
    parser.add_argument(
        "-d", "--describe",
        action="store_true",
        help="Generate VLM descriptions for figures"
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        help="Model path for descriptions (default: DeepSeek-OCR-2)"
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        help="Save figure metadata to JSON file"
    )

    args = parser.parse_args()

    # Default output dir
    if args.output_dir is None:
        args.output_dir = Path("figures")

    if not args.pages_dir.exists():
        print(f"Error: Pages directory not found: {args.pages_dir}")
        return 1

    if not args.ocr_dir.exists():
        print(f"Error: OCR directory not found: {args.ocr_dir}")
        return 1

    extractor = FigureExtractor(
        pages_dir=args.pages_dir,
        ocr_dir=args.ocr_dir,
        output_dir=args.output_dir,
        describe_figures=args.describe,
        model_path=args.model,
    )

    figures = extractor.extract_figures()

    if args.metadata:
        extractor.save_metadata(figures, args.metadata)

    return 0


if __name__ == "__main__":
    exit(main())
