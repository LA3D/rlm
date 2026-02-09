# Test Data for KAG Document Understanding Experiments

## Overview

This directory contains OCR outputs from DeepSeek-OCR-2 for testing agentic document graph construction. All papers were processed using the automated pipeline in `techindex-exp/scripts/`.

## DeepSeek OCR Detection Structure

DeepSeek-OCR-2 provides semantic detection tags with bounding boxes:

```markdown
<|ref|>LABEL<|/ref|><|det|>[[x1, y1, x2, y2]]<|/det|>
Content here...
```

**Detection Types:**
- `title` - Document title
- `sub_title` - Section/subsection headings
- `text` - Body text paragraphs
- `equation` - Mathematical equations
- `image` - Figures/diagrams
- `table` - Tabular data
- `figure_title` - Figure captions
- `table_title` - Table captions

**Bounding Boxes:**
- Normalized 0-1000 coordinate space
- Format: `[[x1, y1, x2, y2]]` (top-left, bottom-right)
- Can convert to pixel coords using page dimensions

## Test Documents

### 1. chemrxiv (Chemistry Paper)
- **Title:** "Low-temperature retro Diels-Alder reactions"
- **Authors:** Wolfarth et al.
- **Pages:** 8
- **Type:** Research paper (chemistry)
- **Features:**
  - IMRaD structure (Intro, Methods, Results, Discussion)
  - 6 figures (reaction schemes, plots, crystal structures)
  - Multiple equations (thermodynamic calculations)
  - 3 tables (experimental data)
- **OCR:** `chemrxiv_ocr/page_*.md`
- **Figures:** `chemrxiv_figures/fig_page*.png`
- **Metadata:** `chemrxiv_figures_metadata.json`

### 2. pet_test (PET Imaging Paper)
- **Type:** Medical imaging / radiology
- **Pages:** 8
- **Features:**
  - Medical imaging figures (PET scans)
  - Clinical data tables
  - Technical methodology
- **OCR:** `pet_test_ocr/page_*.md`
- **Figures:** `pet_test_figures/fig_page*.png`
- **Metadata:** `pet_test_figures_metadata.json`

### 3. omd_test (OpenMD Documentation)
- **Type:** Technical documentation
- **Pages:** 8
- **Features:**
  - Software documentation structure
  - Code examples
  - Diagrams
- **OCR:** `omd_test_ocr/page_*.md`
- **Figures:** `omd_test_figures/fig_page*.png`
- **Metadata:** `omd_test_figures_metadata.json`

## Directory Structure

```
test_data/
├── chemrxiv_ocr/              # Markdown with detection tags
│   ├── page_001.md
│   ├── page_002.md
│   └── ...
├── chemrxiv_figures/          # Extracted figure images
│   ├── fig_page002_01.png
│   └── ...
├── chemrxiv_figures_metadata.json  # Structured metadata
├── pet_test_ocr/
├── pet_test_figures/
├── pet_test_figures_metadata.json
├── omd_test_ocr/
├── omd_test_figures/
└── omd_test_figures_metadata.json
```

## Usage in Experiments

### Load OCR Markdown
```python
from pathlib import Path

ocr_dir = Path("test_data/chemrxiv_ocr")
pages = sorted(ocr_dir.glob("page_*.md"))

for page in pages:
    content = page.read_text()
    # Parse detection tags: <|ref|>label<|/ref|><|det|>bbox<|/det|>
```

### Load Figure Metadata
```python
import json

metadata = json.load(open("test_data/chemrxiv_figures_metadata.json"))

for fig in metadata:
    print(f"Figure on page {fig['page']}: {fig['image_path']}")
    print(f"  Bbox: {fig['bbox_norm']}")
    print(f"  Caption context: {fig['page_text'][:100]}...")
```

## Expected Agent Behavior

An agentic document understanding system should:

1. **Parse detection tags** from markdown (not hardcoded regex)
2. **Reason about structure** using tag types and spatial info
3. **Build hierarchy** (Document → Section → Paragraph/Figure/Equation)
4. **Link figures to captions** using figure_title proximity
5. **Link tables to mentions** in text
6. **Create multi-level summaries** (coarse → fine)
7. **Return handles** not payloads (RLM-compliant)

## Why DeepSeek OCR Structure is Good

✅ **Semantic labels** - Meaningful types (not just "text block")
✅ **Hierarchy markers** - title vs sub_title indicates structure
✅ **Spatial information** - Bboxes enable proximity reasoning
✅ **Multimodal** - Separate tags for text, images, equations, tables
✅ **Caption linking** - figure_title enables figure understanding
✅ **Domain-agnostic** - Same structure works across chemistry, medical, technical docs

This is much better than generic OCR (Tesseract) which provides only undifferentiated text.

## Processing Statistics

| Paper | Pages | Figures | Equations | Tables | Detection Tags |
|-------|-------|---------|-----------|--------|----------------|
| chemrxiv | 8 | 6 | ~12 | 3 | ~150 |
| pet_test | 8 | 5 | few | several | ~100 |
| omd_test | 8 | 1 | none | some | ~80 |

## Next Steps

1. Build Agent 1 (StructureParser) to parse these into DocumentTree
2. Test on all three papers to validate domain-agnostic reasoning
3. Build Agent 2 (HierarchicalSummarizer) for multi-level summaries
4. Build Agent 3 (RelationExtractor) to link figures/tables/citations
5. Build Agent 4 (KGConstructor) to create RDF knowledge graph
6. Build Agent 5 (StructureValidator) to judge quality

All following RLM principles: handles not payloads, bounded access, trajectory logging.
