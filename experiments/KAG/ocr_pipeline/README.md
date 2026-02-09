# OCR Pipeline - DeepSeek-OCR-2 Document Processing

## Overview

Self-contained pipeline for processing PDF documents into structured OCR outputs using DeepSeek-OCR-2 with MLX-VLM (Apple Silicon optimized).

**Purpose:** Create new test cases for the KAG agentic document understanding experiments.

## Pipeline Components

### 1. `pdf_to_images.py`
Converts PDF pages to high-resolution PNG images.

```bash
python pdf_to_images.py input.pdf -o output/pages/ --scale 2.0
```

**Output:** `page_001.png`, `page_002.png`, etc. (~150-200 DPI)

### 2. `ocr_processor.py`
Runs DeepSeek-OCR-2 to extract markdown with detection tags.

```bash
python ocr_processor.py output/pages/ -o output/ocr/
```

**Output:**
- `page_001.md`, `page_002.md`, etc. (per-page markdown)
- `document.md` (concatenated full document)
- Detection tags: `<|ref|>label<|/ref|><|det|>bbox<|/det|>`

### 3. `figure_extractor.py`
Extracts figures using bounding box detection.

```bash
python figure_extractor.py output/pages/ output/ocr/ -o output/figures/
```

**Output:**
- `fig_page002_01.png`, etc. (cropped figures)
- `figures_metadata.json` (structured metadata)

### 4. `run_pipeline.py`
Complete orchestration: PDF → images → OCR → figures

```bash
python run_pipeline.py input.pdf -o output/
```

**Output directory structure:**
```
output/
├── pages/                    # Page PNGs
├── ocr/                      # Markdown with detection tags
│   ├── page_001.md
│   ├── page_002.md
│   └── document.md
├── figures/                  # Extracted figures
│   ├── fig_page002_01.png
│   └── ...
└── figures_metadata.json     # Figure metadata
```

## DeepSeek-OCR-2 Detection Tags

The OCR processor uses a grounding prompt to extract semantic structure:

```
Prompt: "<|grounding|> Convert this document page to Markdown, preserving detection tags."
```

**Detection Types:**
- `title` - Document/article title
- `sub_title` - Section/subsection headings
- `text` - Body paragraphs
- `equation` - Mathematical formulas
- `image` - Figures/diagrams
- `table` - Tabular data
- `figure_title` - Figure captions
- `table_title` - Table captions

**Bounding Box Format:**
- Normalized 0-1000 coordinate space
- `[[x1, y1, x2, y2]]` - top-left to bottom-right

**Example:**
```markdown
<|ref|>title<|/ref|><|det|>[[75, 133, 744, 160]]<|/det|>
# Low-temperature retro Diels-Alder reactions

<|ref|>image<|/ref|><|det|>[[515, 626, 920, 816]]<|/det|>

<|ref|>figure_title<|/ref|><|det|>[[504, 821, 929, 892]]<|/det|>
Figure 1. Crystal structures...
```

## Requirements

```bash
# MLX and DeepSeek-OCR-2
pip install mlx mlx-vlm

# PDF processing
pip install pypdfium2 Pillow

# DeepSeek-OCR-2 model (auto-downloads on first use)
# Model: mlx-community/DeepSeek-OCR-2-bf16
```

## Usage Examples

### Process a New Paper

```bash
# Download a paper
curl -o paper.pdf https://example.com/paper.pdf

# Run complete pipeline
python run_pipeline.py paper.pdf -o ../test_data/new_paper/

# Output will be in:
# ../test_data/new_paper_ocr/
# ../test_data/new_paper_figures/
# ../test_data/new_paper_figures_metadata.json
```

### Process Just OCR (Skip Figures)

```bash
python run_pipeline.py paper.pdf -o output/paper/ --no-figures
```

### Add Figure Descriptions (VLM)

```bash
python run_pipeline.py paper.pdf -o output/paper/ --describe
```

**Note:** VLM descriptions are often inaccurate for complex scientific figures. Use with caution.

### Custom OCR Settings

```bash
python ocr_processor.py pages/ -o ocr/ \
    --model mlx-community/DeepSeek-OCR-2-bf16 \
    --max-tokens 8192
```

## Integration with KAG Experiments

After processing a new document:

```python
# Copy to test_data
import shutil
from pathlib import Path

src = Path("output/new_paper")
dst = Path("../test_data/new_paper_ocr")

shutil.copytree(src / "ocr", dst)
shutil.copytree(src / "figures", dst.parent / "new_paper_figures")
shutil.copy(src / "figures_metadata.json",
            dst.parent / "new_paper_figures_metadata.json")

# Now run KAG experiments on new document
from run_kag_0 import run_baseline_parser

result = run_baseline_parser(
    ocr_dir=Path("../test_data/new_paper_ocr"),
    output_dir=Path("results/new_paper")
)
```

## Processing Statistics

From existing test cases:

| Document | Pages | OCR Time | Figures | Detection Tags |
|----------|-------|----------|---------|----------------|
| chemrxiv | 8 | ~2 min | 6 | ~150 |
| pet_test | 8 | ~2 min | 5 | ~100 |
| omd_test | 8 | ~2 min | 1 | ~80 |

**Hardware:** Apple Silicon (M1/M2/M3) with MLX optimization

## Limitations

### OCR Quality
- ✅ Excellent on clean research papers
- ✅ Good equation detection
- ⚠️ May miss complex multi-column layouts
- ⚠️ Small/rotated text can be missed

### Figure Extraction
- ✅ Accurate bounding boxes from detection
- ⚠️ VLM descriptions often poor for scientific figures
- ⚠️ Complex figures (reaction schemes) may need manual review

### Chemistry-Specific
- ⚠️ SMILES extraction is limited (use DECIMER instead)
- ⚠️ Complex reaction schemes may not parse well
- ✅ Chemical equations generally work

## Troubleshooting

### OCR Returns Empty/Garbled Text
```bash
# Try higher resolution
python pdf_to_images.py input.pdf -o pages/ --scale 3.0

# Or increase max tokens
python ocr_processor.py pages/ -o ocr/ --max-tokens 8192
```

### Figures Not Extracted
```bash
# Check detection tags in markdown
grep '<|ref|>image<|/ref|>' ocr/page_*.md

# If tags exist but extraction fails, check bbox format
python figure_extractor.py pages/ ocr/ -o figures/ --verbose
```

### Out of Memory
```bash
# Process pages individually instead of batch
for page in pages/*.png; do
    python ocr_processor.py "$page" -o ocr/
done
```

## File Organization

```
ocr_pipeline/
├── README.md              # This file
├── pdf_to_images.py       # PDF → PNG conversion
├── ocr_processor.py       # DeepSeek-OCR-2 processing
├── figure_extractor.py    # Figure extraction
└── run_pipeline.py        # Complete orchestration
```

## Future Enhancements

Potential improvements (not yet implemented):

- [ ] Batch processing multiple PDFs
- [ ] Table extraction and parsing
- [ ] Equation rendering (LaTeX → image)
- [ ] Multi-column layout detection
- [ ] Citation extraction
- [ ] Better chemistry structure recognition (integrate DECIMER)
- [ ] Parallel processing for faster OCR
- [ ] Progress bars for long documents

## References

- DeepSeek-OCR: https://arxiv.org/html/2510.18234v1
- DeepSeek-OCR-2: Improved version with better detection
- MLX-VLM: https://github.com/Blaizzy/mlx-vlm
- pypdfium2: https://github.com/pypdfium2-team/pypdfium2
