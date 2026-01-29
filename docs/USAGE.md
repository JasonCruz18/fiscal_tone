# Usage Guide

## Pipeline Overview

FiscalTone provides a modular pipeline that can be run as a whole or stage-by-stage.

## Command Line Interface

### List Available Stages

```bash
python scripts/run_pipeline.py --list
```

Output:
```
Available stages:
  collect   - Scrape and download PDFs from cf.gob.pe
  classify  - Classify PDFs as editable/scanned
  extract   - Extract text from editable PDFs
  clean     - Clean and normalize extracted text
  analyze   - Classify fiscal tone using GPT-4o
```

### Run All Stages

```bash
python scripts/run_pipeline.py --all
```

### Run Specific Stages

```bash
# Run single stage
python scripts/run_pipeline.py --stage collect

# Run multiple stages in sequence
python scripts/run_pipeline.py --stages collect classify extract
```

## Stage Details

### Stage 1: Collect (`collect`)

Scrapes PDF links from cf.gob.pe and downloads PDFs.

**Input**: None (scrapes from web)
**Output**:
- `data/raw/*.pdf` - Downloaded PDF files
- `metadata/cf_metadata.json` - PDF metadata

**Features**:
- Incremental scraping (skips already downloaded)
- Multiple fallback strategies for PDF URLs
- Rate limiting (1 second between downloads)

```bash
python scripts/run_pipeline.py --stage collect
```

### Stage 2: Classify (`classify`)

Classifies PDFs as editable (text-based) or scanned (image-based).

**Input**: `data/raw/*.pdf`
**Output**:
- `data/raw/editable/*.pdf`
- `data/raw/scanned/*.pdf`
- Updated `metadata/cf_metadata.json` with `pdf_type` field

```bash
python scripts/run_pipeline.py --stage classify
```

### Stage 3: Extract (`extract`)

Extracts text from editable PDFs using font-based filtering.

**Input**: `data/raw/editable/*.pdf`
**Output**: `metadata/cf_extracted_text.json`

**Features**:
- Font size filtering (11.0-11.9pt body text)
- Paragraph detection via vertical spacing
- Stops at "Anexo" sections

```bash
python scripts/run_pipeline.py --stage extract
```

### Stage 4: Clean (`clean`)

Cleans and normalizes extracted text.

**Input**: `metadata/cf_extracted_text.json`
**Output**: `metadata/cf_cleaned_text.json`

**Cleaning stages**:
1. Preliminary normalization (OCR artifacts)
2. Keyword filtering (find "Opinión del CF")
3. False paragraph break removal
4. Header/title removal
5. Annex truncation
6. Letter page removal
7. Noise reduction

```bash
python scripts/run_pipeline.py --stage clean
```

### Stage 5: Analyze (`analyze`)

Classifies fiscal tone using GPT-4o.

**Input**: `metadata/cf_cleaned_text.json`
**Output**:
- `data/output/llm_output_paragraphs.json`
- `data/output/llm_output_documents.json`

**Requirements**: `OPENAI_API_KEY` environment variable

```bash
export OPENAI_API_KEY="your-key"
python scripts/run_pipeline.py --stage analyze
```

## Common Workflows

### Fresh Start (Full Pipeline)

```bash
# Ensure API key is set
export OPENAI_API_KEY="your-key"

# Run complete pipeline
python scripts/run_pipeline.py --all
```

### Update with New Reports

```bash
# Only collect and process new PDFs
python scripts/run_pipeline.py --stages collect classify extract clean
```

### Re-run LLM Classification

```bash
# Re-analyze with updated prompts
python scripts/run_pipeline.py --stage analyze
```

### Process Only Editable PDFs

```bash
python scripts/run_pipeline.py --stages extract clean
```

## Output Files

### Paragraph-Level Results

`data/output/llm_output_paragraphs.json`:
```json
[
  {
    "pdf_filename": "Informe-001-2020-CF.pdf",
    "page": 3,
    "paragraph_num": 1,
    "text": "El CF considera que...",
    "fiscal_risk_score": 4,
    "risk_index": -0.5,
    "date": "2020-03-15",
    "doc_type": "Informe"
  }
]
```

### Document-Level Results

`data/output/llm_output_documents.json`:
```json
[
  {
    "pdf_filename": "Informe-001-2020-CF.pdf",
    "date": "2020-03-15",
    "avg_risk_score": 3.5,
    "fiscal_tone_index": -0.25,
    "n_paragraphs": 12,
    "score_1": 1,
    "score_2": 2,
    "score_3": 4,
    "score_4": 4,
    "score_5": 1
  }
]
```

## Configuration

### Rate Limiting

Edit `fiscal_tone/analyzers/llm_classifier.py`:
```python
rate_limiter = aiolimiter.AsyncLimiter(max_rate=50, time_period=60)
```

### Font Filtering

Edit `fiscal_tone/processors/text_extractor.py`:
```python
FONT_MIN = 11.0
FONT_MAX = 11.9
```

## Error Handling

### Resume from Interruption

The pipeline saves progress incrementally. Simply re-run the same command to continue.

### API Rate Limit Errors

- Wait a few minutes and retry
- Reduce `max_rate` in rate limiter
- Check your OpenAI API tier

### PDF Download Failures

Check `metadata/cf_metadata.json` for entries with `pdf_url: null` and investigate manually.
