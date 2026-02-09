#!/usr/bin/env python3
"""
OCR processor using DeepSeek-OCR-2 with MLX-VLM.

Processes page images and extracts:
- Markdown text
- Detection metadata (images, captions, equations, etc.)
- Bounding boxes for layout elements
"""

import argparse
import re
import ast
from pathlib import Path
from typing import List, Dict, Any, Optional

import mlx.core as mx
from mlx_vlm import load, generate
from mlx_vlm.prompt_utils import apply_chat_template
from mlx_vlm.utils import load_config


class DeepSeekOCR2Processor:
    """Handles OCR processing with DeepSeek-OCR-2."""

    # Default model for OCR2
    DEFAULT_MODEL = "mlx-community/DeepSeek-OCR-2-bf16"

    # Prompt with grounding tokens for better results
    DEFAULT_PROMPT = "<|grounding|> Convert this document page to Markdown, preserving detection tags."

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL,
        verbose: bool = False
    ):
        """
        Initialize the OCR processor.

        Args:
            model_path: HuggingFace model path for DeepSeek-OCR-2
            verbose: Whether to print detailed generation info
        """
        self.model_path = model_path
        self.verbose = verbose

        print(f"Loading model: {model_path}")
        self.model, self.processor = load(model_path)
        self.config = load_config(model_path)
        print("✓ Model loaded successfully")

    def ocr_image(
        self,
        image_path: Path,
        prompt: str = DEFAULT_PROMPT,
        max_tokens: int = 4096,
        temperature: float = 0.0
    ) -> str:
        """
        Perform OCR on a single image.

        Args:
            image_path: Path to the image file
            prompt: OCR prompt (use grounding token for structured output)
            max_tokens: Maximum tokens to generate
            temperature: Generation temperature (0.0 for deterministic)

        Returns:
            OCR text output with detection tags
        """
        images = [str(image_path)]

        formatted_prompt = apply_chat_template(
            self.processor,
            self.config,
            prompt,
            num_images=len(images),
        )

        output = generate(
            self.model,
            self.processor,
            formatted_prompt,
            images,
            temp=temperature,
            max_tokens=max_tokens,
            verbose=self.verbose,
        )

        # Extract text from GenerationResult
        return getattr(output, "text", str(output))

    def process_pages(
        self,
        pages_dir: Path,
        output_dir: Path,
        prompt: str = DEFAULT_PROMPT,
        max_tokens: int = 4096,
        save_individual: bool = True
    ) -> List[str]:
        """
        Process all page images in a directory.

        Args:
            pages_dir: Directory containing page_XXX.png files
            output_dir: Directory for output markdown files
            prompt: OCR prompt
            max_tokens: Maximum tokens per page
            save_individual: Whether to save individual page markdown files

        Returns:
            List of OCR text for each page
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        page_images = sorted(pages_dir.glob("page_*.png"))
        if not page_images:
            raise ValueError(f"No page_*.png files found in {pages_dir}")

        print(f"\nProcessing {len(page_images)} pages from {pages_dir}")

        page_texts = []

        for idx, img_path in enumerate(page_images, start=1):
            print(f"  [{idx}/{len(page_images)}] OCR'ing {img_path.name}...")

            text = self.ocr_image(img_path, prompt, max_tokens)
            page_texts.append(text)

            if save_individual:
                md_path = output_dir / f"page_{idx:03d}.md"
                md_path.write_text(text, encoding="utf-8")

        # Save merged document
        merged_path = output_dir / "document.md"
        merged_content = "\n\n---\n\n".join(page_texts)
        merged_path.write_text(merged_content, encoding="utf-8")

        print(f"\n✓ Saved {len(page_images)} individual pages to {output_dir}")
        print(f"✓ Saved merged document to {merged_path}")

        return page_texts


def extract_detections(page_text: str) -> List[Dict[str, Any]]:
    """
    Extract DeepSeek-OCR detection metadata from OCR text.

    Parses tags like:
        <|ref|>label<|/ref|><|det|>[[x1, y1, x2, y2], ...]<|/det|>

    Args:
        page_text: OCR output text containing detection tags

    Returns:
        List of detection dicts with 'label' and 'bboxes' keys
    """
    pattern = re.compile(
        r"<\|ref\|>(?P<label>.*?)<\|/ref\|><\|det\|>(?P<bboxes>.*?)<\|/det\|>",
        re.DOTALL,
    )

    detections = []
    for match in pattern.finditer(page_text):
        label = match.group("label")
        bboxes_raw = match.group("bboxes").strip()

        try:
            # DeepSeek uses Python-like lists [x1, y1, x2, y2]
            # Coordinates are normalized to 0-1000 range
            bboxes = ast.literal_eval(bboxes_raw)
        except Exception as e:
            # Skip malformed bboxes
            continue

        detections.append({
            "label": label,
            "bboxes": bboxes,  # List of [x1, y1, x2, y2] in 0-1000 range
        })

    return detections


def main():
    parser = argparse.ArgumentParser(
        description="OCR page images using DeepSeek-OCR-2"
    )
    parser.add_argument(
        "pages_dir",
        type=Path,
        help="Directory containing page_XXX.png files"
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        help="Output directory for markdown files (default: <pages_dir>_ocr)"
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default=DeepSeekOCR2Processor.DEFAULT_MODEL,
        help=f"Model path (default: {DeepSeekOCR2Processor.DEFAULT_MODEL})"
    )
    parser.add_argument(
        "-p", "--prompt",
        type=str,
        default=DeepSeekOCR2Processor.DEFAULT_PROMPT,
        help="OCR prompt"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Maximum tokens per page (default: 4096)"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output during generation"
    )

    args = parser.parse_args()

    # Default output dir
    if args.output_dir is None:
        args.output_dir = args.pages_dir.parent / f"{args.pages_dir.name}_ocr"

    if not args.pages_dir.exists():
        print(f"Error: Pages directory not found: {args.pages_dir}")
        return 1

    processor = DeepSeekOCR2Processor(
        model_path=args.model,
        verbose=args.verbose
    )

    processor.process_pages(
        pages_dir=args.pages_dir,
        output_dir=args.output_dir,
        prompt=args.prompt,
        max_tokens=args.max_tokens,
    )

    return 0


if __name__ == "__main__":
    exit(main())
