#!/usr/bin/env python3
"""
Convert PDF files to raster images for OCR processing.

Uses pypdfium2 to render each page at high resolution.
"""

import argparse
from pathlib import Path
import pypdfium2 as pdfium


def pdf_to_images(
    pdf_path: Path,
    output_dir: Path,
    scale: float = 2.0,
    dpi_equivalent: str = "~150-200 DPI"
) -> int:
    """
    Convert a PDF to individual page images.

    Args:
        pdf_path: Path to the input PDF file
        output_dir: Directory where page images will be saved
        scale: Rendering scale factor (default: 2.0)
        dpi_equivalent: Description of DPI for logging

    Returns:
        Number of pages processed
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    pdf = pdfium.PdfDocument(str(pdf_path))
    page_count = len(pdf)

    print(f"Processing {pdf_path.name}...")
    print(f"Total pages: {page_count}")
    print(f"Scale: {scale} ({dpi_equivalent})")
    print(f"Output directory: {output_dir}")

    for i in range(page_count):
        page = pdf.get_page(i)
        pil_image = page.render(scale=scale).to_pil()
        output_path = output_dir / f"page_{i+1:03d}.png"
        pil_image.save(output_path)

        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{page_count} pages...")

    print(f"✓ Saved {page_count} page images to {output_dir}")
    return page_count


def main():
    parser = argparse.ArgumentParser(
        description="Convert PDF to page images for OCR processing"
    )
    parser.add_argument(
        "pdf_path",
        type=Path,
        help="Path to input PDF file"
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        help="Output directory for page images (default: <pdf_name>_pages)"
    )
    parser.add_argument(
        "-s", "--scale",
        type=float,
        default=2.0,
        help="Rendering scale factor (default: 2.0)"
    )

    args = parser.parse_args()

    # Default output dir based on PDF name
    if args.output_dir is None:
        args.output_dir = args.pdf_path.parent / f"{args.pdf_path.stem}_pages"

    if not args.pdf_path.exists():
        print(f"Error: PDF file not found: {args.pdf_path}")
        return 1

    pdf_to_images(args.pdf_path, args.output_dir, args.scale)
    return 0


if __name__ == "__main__":
    exit(main())
