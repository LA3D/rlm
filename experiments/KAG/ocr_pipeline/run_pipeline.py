#!/usr/bin/env python3
"""
Complete OCR pipeline orchestrator.

Runs the full workflow:
1. PDF → page images
2. Page images → OCR (markdown + detection metadata)
3. Extract and crop figures
4. (Optional) Generate figure descriptions
"""

import argparse
from pathlib import Path
from typing import Dict
import sys

from pdf_to_images import pdf_to_images
from ocr_processor import DeepSeekOCR2Processor
from figure_extractor import FigureExtractor


def run_pipeline(
    pdf_path: Path,
    output_base: Path,
    model_path: str,
    describe_figures: bool = False,
    scale: float = 2.0,
    max_tokens: int = 4096,
    skip_pdf_conversion: bool = False,
    skip_ocr: bool = False,
) -> Dict[str, Path]:
    """
    Run the complete OCR pipeline.

    Args:
        pdf_path: Input PDF file
        output_base: Base directory for all outputs
        model_path: DeepSeek-OCR-2 model path
        describe_figures: Whether to generate VLM descriptions
        scale: PDF rendering scale
        max_tokens: Max tokens per OCR page
        skip_pdf_conversion: Skip PDF→images step (use existing images)
        skip_ocr: Skip OCR step (use existing OCR outputs)

    Returns:
        Dictionary of output paths
    """
    output_base.mkdir(parents=True, exist_ok=True)

    pages_dir = output_base / "pages"
    ocr_dir = output_base / "ocr"
    figures_dir = output_base / "figures"
    metadata_path = output_base / "figures_metadata.json"

    outputs = {
        "pages_dir": pages_dir,
        "ocr_dir": ocr_dir,
        "figures_dir": figures_dir,
        "metadata": metadata_path,
    }

    print("=" * 70)
    print("DeepSeek-OCR-2 Document Processing Pipeline")
    print("=" * 70)
    print(f"Input PDF: {pdf_path}")
    print(f"Output directory: {output_base}")
    print(f"Model: {model_path}")
    print("=" * 70)

    # Step 1: Convert PDF to images
    if not skip_pdf_conversion:
        print("\n[STEP 1/3] Converting PDF to page images...")
        print("-" * 70)
        pdf_to_images(pdf_path, pages_dir, scale=scale)
    else:
        print("\n[STEP 1/3] Skipping PDF conversion (using existing images)")
        if not pages_dir.exists():
            raise ValueError(f"Pages directory not found: {pages_dir}")

    # Step 2: OCR pages
    if not skip_ocr:
        print("\n[STEP 2/3] Running OCR on page images...")
        print("-" * 70)
        processor = DeepSeekOCR2Processor(model_path=model_path)
        processor.process_pages(
            pages_dir=pages_dir,
            output_dir=ocr_dir,
            max_tokens=max_tokens,
        )
    else:
        print("\n[STEP 2/3] Skipping OCR (using existing outputs)")
        if not ocr_dir.exists():
            raise ValueError(f"OCR directory not found: {ocr_dir}")

    # Step 3: Extract figures
    print("\n[STEP 3/3] Extracting figures...")
    print("-" * 70)
    extractor = FigureExtractor(
        pages_dir=pages_dir,
        ocr_dir=ocr_dir,
        output_dir=figures_dir,
        describe_figures=describe_figures,
        model_path=model_path if describe_figures else None,
    )

    figures = extractor.extract_figures()
    extractor.save_metadata(figures, metadata_path)

    # Summary
    print("\n" + "=" * 70)
    print("Pipeline Complete!")
    print("=" * 70)
    print(f"Page images:    {pages_dir}")
    print(f"OCR outputs:    {ocr_dir}")
    print(f"Figures:        {figures_dir}")
    print(f"Metadata:       {metadata_path}")
    print(f"\nExtracted {len(figures)} figures")
    print("=" * 70)

    return outputs


def main():
    parser = argparse.ArgumentParser(
        description="Complete OCR pipeline for PDF documents using DeepSeek-OCR-2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage - just OCR
  %(prog)s input.pdf -o output/

  # OCR + figure descriptions
  %(prog)s input.pdf -o output/ --describe

  # Use custom model
  %(prog)s input.pdf -o output/ -m mlx-community/DeepSeek-OCR-2-bf16

  # Resume from existing OCR outputs
  %(prog)s input.pdf -o output/ --skip-ocr --skip-pdf
        """
    )

    parser.add_argument(
        "pdf_path",
        type=Path,
        help="Input PDF file to process"
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        required=True,
        help="Output directory for all results"
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default="mlx-community/DeepSeek-OCR-2-bf16",
        help="DeepSeek-OCR-2 model path (default: mlx-community/DeepSeek-OCR-2-bf16)"
    )
    parser.add_argument(
        "-d", "--describe",
        action="store_true",
        help="Generate VLM descriptions for extracted figures"
    )
    parser.add_argument(
        "-s", "--scale",
        type=float,
        default=2.0,
        help="PDF rendering scale factor (default: 2.0)"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Maximum tokens per OCR page (default: 4096)"
    )
    parser.add_argument(
        "--skip-pdf",
        action="store_true",
        help="Skip PDF conversion (use existing page images)"
    )
    parser.add_argument(
        "--skip-ocr",
        action="store_true",
        help="Skip OCR step (use existing OCR outputs)"
    )

    args = parser.parse_args()

    if not args.pdf_path.exists():
        print(f"Error: PDF file not found: {args.pdf_path}", file=sys.stderr)
        return 1

    try:
        run_pipeline(
            pdf_path=args.pdf_path,
            output_base=args.output_dir,
            model_path=args.model,
            describe_figures=args.describe,
            scale=args.scale,
            max_tokens=args.max_tokens,
            skip_pdf_conversion=args.skip_pdf,
            skip_ocr=args.skip_ocr,
        )
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
