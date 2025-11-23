# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**FiscalTone** is a research project analyzing fiscal policy communications from Peru's Fiscal Council (Consejo Fiscal). The pipeline scrapes, processes, and analyzes PDF documents to extract fiscal tone sentiment using LLM-based classification.

The project involves:
1. **Data Collection**: Web scraping PDFs from cf.gob.pe
2. **Data Curation**: Classification (editable vs scanned), text extraction, metadata enrichment
3. **LLM Analysis**: Using GPT-4o to score fiscal risk sentiment (1-5 scale)
4. **Visualization**: Time-series analysis of fiscal tone

## Project Structure

```
FiscalTone/
├── data/
│   ├── raw/              # Downloaded PDFs (subdirs: editable/, scanned/)
│   ├── input/            # Preprocessed PDFs
│   └── output/           # Final processed data
├── metadata/             # JSON/CSV metadata files
├── data_curation.py      # Main pipeline script
└── llm.ipynb            # LLM scoring & visualization notebook
```

## Key Python Dependencies

Core libraries (Python 3.12):
- **Web scraping**: `requests`, `beautifulsoup4`
- **PDF processing**: `PyMuPDF` (fitz), `pdfplumber`
- **Data manipulation**: `pandas`, `numpy`
- **LLM**: `openai` (GPT-4o via OpenAI API)
- **Visualization**: `matplotlib`

## Running the Pipeline

### 1. Data Curation Pipeline

The main script `data_curation.py` is an **interactive script** (not a CLI tool). It prompts for user input:

```bash
python data_curation.py
```

When prompted for path, press Enter to use current directory (`.`) or specify a path.

**What it does:**
1. Scrapes PDF links from cf.gob.pe (informes & comunicados)
2. Downloads PDFs incrementally (skips already downloaded)
3. Classifies PDFs as editable vs scanned
4. Enriches metadata with document type, number, year, month
5. Extracts text from editable PDFs using font-based filtering

**Key behaviors:**
- **Incremental scraping**: Uses `already_scraped_pages` to avoid re-downloading
- **Incremental JSON updates**: Saves metadata after each PDF download (line data_curation.py:330)
- **Rate limiting**: 1-second delay between downloads (line data_curation.py:333)
- **Fallback mechanisms**: Multiple strategies to find PDF URLs (iframes, embeds, Google Docs viewer)

### 2. LLM Scoring

Use the `llm.ipynb` notebook:

1. Requires `OPENAI_API_KEY` environment variable
2. Loads preprocessed text data (CSV with `text` and `date` columns)
3. Scores each paragraph using GPT-4o (1-5 fiscal risk scale)
4. Saves backups every 10 rows during processing
5. Generates visualizations (stacked area charts, fiscal tone index)

**Environment setup:**
```bash
export OPENAI_API_KEY="your-key-here"  # Unix/macOS
# or
set OPENAI_API_KEY=your-key-here       # Windows cmd
```

## Critical Architecture Details

### PDF Download Strategy

The `pdf_downloader()` function (line data_curation.py:212) implements a robust multi-fallback approach:

1. **Primary**: Direct PDF links from `<a>` tags
2. **Fallback A**: PDF selection heuristic prioritizing "comunicado", "informe" over presentations
3. **Fallback B**: iframe src attributes
4. **Fallback C**: Google Docs viewer URL extraction
5. **Fallback D**: embed/data-pdf-src attributes

Files are filtered to exclude presentations (PPT keywords) automatically.

### Text Extraction Logic

The `extract_text_from_single_pdf()` function (line data_curation.py:593) uses font-based filtering:

- **Font size range**: 11.0–11.9 (configurable via `FONT_MIN`/`FONT_MAX`)
- **Exclude bold**: Optional parameter to skip bold text
- **Paragraph detection**: Vertical spacing threshold (default 10 pixels)
- **Stops at "Anexo"**: Truncates content when appendix sections are detected (line data_curation.py:652)

### Metadata Schema

JSON metadata structure (after enrichment):
```json
{
  "date": "YYYY-MM-DD",
  "year": "YYYY",
  "month": "MM",
  "page_url": "https://...",
  "pdf_url": "https://...",
  "pdf_filename": "...",
  "pdf_type": "editable|scanned",
  "doc_title": "...",
  "doc_type": "Informe|Comunicado",
  "doc_number": 123
}
```

## Testing

VSCode settings indicate unit tests are configured for the `./data` directory:
```bash
python -m unittest discover -v -s ./data -p "*test.py"
```

## Common Tasks

### Re-run PDF Download (Incremental)
```bash
python data_curation.py
# Press Enter when prompted
# Only new PDFs will be downloaded
```

### Extract Text from Single PDF (Testing)
Edit line data_curation.py:688 to specify file path, then:
```bash
python data_curation.py
```

### Add New Source URLs
Modify `cf_urls` list (line data_curation.py:343):
```python
cf_urls = [
    "https://cf.gob.pe/p/informes/",
    "https://cf.gob.pe/p/comunicados/",
    # Add new URLs here
]
```

## Git Workflow

Current branch: `text_preprocessing`
Main branch: `main`

Recent work focuses on:
- Converting metadata CSV to JSON format
- Moving data curation functions to main pipeline script
- Terminal-based Claude integration

## Important Notes

- **DO NOT commit**: CSV, PDF, PNG, JSON files (see .gitignore)
- **Hardcoded path warning**: Line data_curation.py:688 contains an absolute Windows path for testing
- **Interactive input**: The script is not designed for automated/batch execution
- **API costs**: LLM scoring uses GPT-4o with temperature=0, ~1.2s delay between calls

## LLM Scoring Criteria

Fiscal risk scores (1-5):
- **1**: No fiscal concern (consolidation, compliance, transparency)
- **2**: Slight concern (potential risks, extraordinary revenue dependency)
- **3**: Neutral (technical description, no judgment)
- **4**: High concern (non-compliance, fiscal loosening, uncertainty)
- **5**: Fiscal alarm (severe criticism, debt sustainability risk)

Fiscal Tone Index formula: `(3 - avg_risk_score) / 2`
