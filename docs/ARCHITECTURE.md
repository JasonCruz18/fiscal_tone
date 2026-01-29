# Architecture Documentation

## System Overview

FiscalTone follows a modular pipeline architecture where each stage is independent and can be run separately.

```
┌─────────────────────────────────────────────────────────────────┐
│                        FiscalTone Pipeline                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ Collect  │───▶│ Classify │───▶│ Extract  │───▶│  Clean   │  │
│  │ (Stage 1)│    │ (Stage 2)│    │ (Stage 3)│    │ (Stage 4)│  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│       │                                               │          │
│       ▼                                               ▼          │
│  ┌──────────┐                                   ┌──────────┐    │
│  │   PDFs   │                                   │  Analyze │    │
│  │ metadata │                                   │ (Stage 5)│    │
│  └──────────┘                                   └──────────┘    │
│                                                       │          │
│                                                       ▼          │
│                                                 ┌──────────┐    │
│                                                 │  Output  │    │
│                                                 │  Scores  │    │
│                                                 └──────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Package Structure

```
fiscal_tone/
├── __init__.py              # Package initialization with lazy imports
├── collectors/
│   ├── __init__.py
│   └── fc_collector.py      # Web scraping and PDF download
├── processors/
│   ├── __init__.py          # Lazy imports for heavy dependencies
│   ├── pdf_classifier.py    # Editable/scanned classification
│   ├── text_extractor.py    # Font-based text extraction
│   └── text_cleaner.py      # Multi-stage text cleaning
├── analyzers/
│   ├── __init__.py
│   ├── prompt_templates.py  # Domain context and prompts
│   └── llm_classifier.py    # Async GPT-4o classification
└── orchestration/
    ├── __init__.py
    └── runners.py           # Pipeline orchestration
```

## Module Details

### Collectors (`fiscal_tone.collectors`)

**fc_collector.py**

Handles web scraping and PDF downloads from cf.gob.pe.

Key functions:
- `scrape_cf(url, already_scraped)` - Scrapes list page for PDF links
- `pdf_downloader(urls, folder, metadata)` - Downloads PDFs with fallbacks
- `run_collection_stage()` - Entry point for collection stage

Design decisions:
- **Incremental scraping**: Tracks processed pages to avoid re-downloading
- **Multi-fallback strategy**: Tries direct links, iframes, Google Docs viewer
- **Rate limiting**: 1-second delay between requests

### Processors (`fiscal_tone.processors`)

**pdf_classifier.py**

Classifies PDFs as editable (text-based) or scanned (image-based).

Key functions:
- `is_editable_pdf(path)` - Checks if PDF has extractable text
- `classify_pdfs_by_type(folder)` - Sorts PDFs into subfolders
- `metadata_enrichment(folder)` - Adds doc_type, doc_number, year

**text_extractor.py**

Extracts text from editable PDFs using font-based filtering.

Key functions:
- `extract_text_from_editable_pdf(path)` - Single PDF extraction
- `extract_text_from_editable_pdfs_batch(folder)` - Batch processing
- `find_opinion_keyword_position(pdf)` - Locates "Opinión del CF" header

Design decisions:
- **Font filtering**: Body text is 11.0-11.9pt, excludes headers/footers
- **Paragraph detection**: Uses vertical spacing threshold (10px)
- **Annex truncation**: Stops at "Anexo" sections

**text_cleaner.py**

Multi-stage text cleaning pipeline.

Stages:
1. `stage0_preliminary_cleaning` - OCR artifact removal
2. `stage1_filter_keywords` - Find opinion section start
3. `stage2_remove_false_breaks` - Fix split paragraphs
4. `stage3_remove_headers` - Remove section titles
5. `stage4_truncate_annexes` - Remove appendices
6. `stage5_remove_letter_pages` - Remove cover letters
7. `stage6_noise_reduction` - Final cleanup

### Analyzers (`fiscal_tone.analyzers`)

**prompt_templates.py**

Contains domain context and prompt templates.

Key components:
- `FISCAL_CONTEXT` - Background on Peruvian fiscal policy
- `CLASSIFICATION_CATEGORIES` - Scoring criteria
- `build_classification_prompt(text)` - Constructs full prompt
- `calculate_fiscal_tone_index(score)` - Computes index

**llm_classifier.py**

Async GPT-4o classification with rate limiting.

Key functions:
- `classify_paragraph(text)` - Single paragraph classification
- `classify_paragraphs_batch(paragraphs)` - Batch with concurrency
- `run_classification_stage()` - Entry point for analysis stage

Design decisions:
- **Async processing**: Uses `asyncio` for concurrent API calls
- **Rate limiting**: 50 RPM via `aiolimiter` (respects TPM limits)
- **Retry logic**: Exponential backoff with `tenacity`
- **Incremental saves**: Backup every 100 paragraphs

### Orchestration (`fiscal_tone.orchestration`)

**runners.py**

Pipeline orchestration and stage management.

Key class:
- `PipelineRunner` - Coordinates stage execution

Methods:
- `run_stage(name)` - Execute single stage
- `run_stages(names)` - Execute multiple stages in sequence
- `run_all()` - Execute complete pipeline

## Data Flow

```
cf.gob.pe
    │
    ▼ (scrape)
metadata/cf_metadata.json
    │
    ▼ (download)
data/raw/*.pdf
    │
    ▼ (classify)
data/raw/editable/*.pdf
data/raw/scanned/*.pdf
    │
    ▼ (extract)
metadata/cf_extracted_text.json
    │
    ▼ (clean)
metadata/cf_cleaned_text.json
    │
    ▼ (analyze)
data/output/llm_output_paragraphs.json
data/output/llm_output_documents.json
```

## Design Principles

### 1. Modularity
Each stage is self-contained and can be developed/tested independently.

### 2. Incremental Processing
All stages save progress and can resume from interruption.

### 3. Lazy Loading
Heavy dependencies (fitz, pdfplumber) are loaded only when needed.

### 4. Configuration Over Code
Key parameters (font sizes, rate limits) are configurable.

### 5. Fail-Safe Design
Multiple fallbacks for web scraping, automatic retries for API calls.

## Extension Points

### Adding a New Processor

1. Create module in `fiscal_tone/processors/`
2. Export from `processors/__init__.py`
3. Add stage to `orchestration/runners.py`
4. Update CLI in `scripts/run_pipeline.py`

### Custom LLM Provider

1. Create new classifier in `fiscal_tone/analyzers/`
2. Implement same interface as `llm_classifier.py`
3. Update `runners.py` to use new classifier

### Adding OCR Support

1. Create `processors/ocr_extractor.py`
2. Integrate with text_extractor pipeline
3. Add stage to orchestration
