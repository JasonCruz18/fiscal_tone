# FiscalTone

**Fiscal Policy Sentiment Analysis for Peru's Fiscal Council**

FiscalTone is a research project that analyzes fiscal policy communications from Peru's Fiscal Council (Consejo Fiscal). The pipeline scrapes, processes, and analyzes PDF documents to extract fiscal tone sentiment using LLM-based classification.

## Overview

The project constructs a "Fiscal Tone Index" by:
1. Collecting 75+ reports from Peru's Fiscal Council (2016-2025)
2. Processing both digital PDFs and scanned documents (via OCR)
3. Classifying fiscal concern levels using GPT-4o (1-5 scale)
4. Aggregating paragraph-level scores into document-level metrics

## Project Structure

```
FiscalTone/
├── fiscal_tone/              # Main package
│   ├── collectors/           # Web scraping and PDF download
│   ├── processors/           # PDF classification, text extraction, cleaning
│   ├── analyzers/            # LLM classification
│   └── orchestration/        # Pipeline runner
├── scripts/                  # CLI entry points
│   └── run_pipeline.py       # Main pipeline CLI
├── data/
│   ├── raw/                  # Downloaded PDFs (editable/, scanned/)
│   ├── input/                # Preprocessed data
│   └── output/               # Final processed data
├── metadata/                 # JSON metadata files
├── archive/                  # Legacy scripts (reference)
└── dashboard/                # Visualization dashboard
```

## Quick Start

### Prerequisites

- Python 3.12+
- Tesseract OCR (for scanned PDFs)
- OpenAI API key (for LLM classification)

### Installation

```bash
# Clone repository
git clone https://github.com/JasonCruz18/FiscalTone.git
cd FiscalTone

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

See [INSTALLATION.md](docs/INSTALLATION.md) for detailed setup instructions.

### Usage

```bash
# List available pipeline stages
python scripts/run_pipeline.py --list

# Run specific stages
python scripts/run_pipeline.py --stages collect classify

# Run entire pipeline
python scripts/run_pipeline.py --all
```

See [USAGE.md](docs/USAGE.md) for detailed usage instructions.

## Pipeline Stages

| Stage | Module | Description |
|-------|--------|-------------|
| `collect` | `collectors.fc_collector` | Scrape and download PDFs from cf.gob.pe |
| `classify` | `processors.pdf_classifier` | Classify PDFs as editable/scanned |
| `extract` | `processors.text_extractor` | Extract text from editable PDFs |
| `clean` | `processors.text_cleaner` | Clean and normalize extracted text |
| `analyze` | `analyzers.llm_classifier` | Classify fiscal tone using GPT-4o |

## Fiscal Tone Scoring

Paragraphs are scored on a 1-5 scale:

| Score | Level | Description |
|-------|-------|-------------|
| 1 | No concern | Fiscal consolidation, compliance, transparency |
| 2 | Slight concern | Potential risks, extraordinary revenue dependency |
| 3 | Neutral | Technical description, no value judgment |
| 4 | High concern | Non-compliance, fiscal loosening, uncertainty |
| 5 | Alarm | Severe criticism, debt sustainability risk |

**Fiscal Tone Index** = (3 - avg_risk_score) / 2

## Documentation

- [INSTALLATION.md](docs/INSTALLATION.md) - Detailed installation guide
- [USAGE.md](docs/USAGE.md) - Usage instructions and examples
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System architecture
- [METHODOLOGY.md](docs/METHODOLOGY.md) - Research methodology
- [DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) - Data field definitions

## License

MIT License - See [LICENSE](LICENSE) for details.

## Author

Jason Cruz

## Acknowledgments

- Peru's Fiscal Council (Consejo Fiscal) for public fiscal reports
- OpenAI for GPT-4o API
