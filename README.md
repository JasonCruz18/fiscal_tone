# FiscalTone

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Fiscal Policy Sentiment Analysis for Peru's Fiscal Council**

FiscalTone is a research project that constructs a "Fiscal Tone Index" by analyzing official communications from Peru's Fiscal Council (Consejo Fiscal). The pipeline scrapes, processes, and classifies PDF documents using LLM-based sentiment analysis.

## Quick Start

### Option A: Conda (Recommended)

```bash
# Clone the repository
git clone https://github.com/JasonCruz18/FiscalTone.git
cd FiscalTone

# Create and activate environment
conda env create -f environment.yml
conda activate fiscal_tone

# Copy example config
cp config/config.example.yaml config/config.yaml

# Run the pipeline
python scripts/run_pipeline.py --list
```

### Option B: Pip + Virtual Environment

```bash
# Clone the repository
git clone https://github.com/JasonCruz18/FiscalTone.git
cd FiscalTone

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy example config
cp config/config.example.yaml config/config.yaml

# Run the pipeline
python scripts/run_pipeline.py --list
```

> **Note:** For scanned PDF processing, install [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) separately.

## Project Structure

```
FiscalTone/
├── fiscal_tone/              # Main package
│   ├── collectors/           # Web scraping and PDF download
│   ├── processors/           # PDF classification, text extraction, cleaning
│   ├── analyzers/            # LLM-based classification
│   └── orchestration/        # Pipeline coordination
├── scripts/
│   └── run_pipeline.py       # CLI entry point
├── config/
│   ├── config.example.yaml   # Configuration template
│   └── config.yaml           # Your local config (gitignored)
├── data/
│   ├── raw/                  # Downloaded PDFs (editable/, scanned/)
│   ├── input/                # Preprocessed data
│   └── output/               # Final results
├── metadata/                 # JSON metadata files
├── docs/                     # Documentation
├── tests/                    # Test suite
├── notebooks/                # Jupyter notebooks
└── dashboard/                # Visualization dashboard
```

## Pipeline Stages

| Stage | Command | Description |
|-------|---------|-------------|
| **collect** | `--stage collect` | Scrape and download PDFs from cf.gob.pe |
| **classify** | `--stage classify` | Classify PDFs as editable/scanned + enrich metadata |
| **extract** | `--stage extract` | Extract text from PDFs (font-based + OCR) |
| **clean** | `--stage clean` | Clean and normalize extracted text |
| **analyze** | `--stage analyze` | Classify fiscal tone using GPT-4o |

### Usage Examples

```bash
# List available stages
python scripts/run_pipeline.py --list

# Run single stage
python scripts/run_pipeline.py --stage collect

# Run multiple stages
python scripts/run_pipeline.py --stages collect classify extract

# Run complete pipeline
python scripts/run_pipeline.py --all
```

## Fiscal Tone Scoring

Paragraphs are classified on a 1-5 scale measuring fiscal concern:

| Score | Level | Description |
|-------|-------|-------------|
| 1 | No concern | Fiscal consolidation, compliance, transparency |
| 2 | Slight concern | Potential risks, extraordinary revenue dependency |
| 3 | Neutral | Technical description, no value judgment |
| 4 | High concern | Non-compliance, fiscal loosening, uncertainty |
| 5 | Alarm | Severe criticism, debt sustainability risk |

**Fiscal Tone Index** = (3 - avg_risk_score) / 2 → ranges from -1 (alarm) to +1 (positive)

## Output Datasets

| File | Description |
|------|-------------|
| `llm_output_paragraphs.json` | Paragraph-level scores with metadata |
| `llm_output_documents.json` | Document-level aggregated scores |
| `cf_metadata.json` | PDF metadata (URLs, dates, types) |
| `cf_cleaned_text.json` | Cleaned text ready for analysis |

## Configuration

Copy the example configuration and customize:

```bash
cp config/config.example.yaml config/config.yaml
```

Key settings:
- `openai.api_key`: Your OpenAI API key (or use `OPENAI_API_KEY` env var)
- `openai.model`: Model to use (default: `gpt-4o`)
- `openai.rate_limit`: Requests per minute (default: 50)
- `paths.*`: Data directory locations

## Requirements

### System Requirements

- Python 3.10 or higher
- 4GB RAM minimum (8GB recommended)
- Internet connection for PDF downloads and LLM API

### External Dependencies

- **Tesseract OCR** (for scanned PDFs):
  - Windows: [UB Mannheim installer](https://github.com/UB-Mannheim/tesseract/wiki)
  - Linux: `sudo apt-get install tesseract-ocr tesseract-ocr-spa`
  - macOS: `brew install tesseract tesseract-lang`

- **OpenAI API Key** (for LLM classification):
  ```bash
  export OPENAI_API_KEY="your-key-here"
  ```

## Documentation

| Document | Description |
|----------|-------------|
| [INSTALLATION.md](docs/INSTALLATION.md) | Detailed setup instructions |
| [USAGE.md](docs/USAGE.md) | Pipeline usage guide |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design documentation |
| [METHODOLOGY.md](docs/METHODOLOGY.md) | Research methodology |
| [DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md) | Data field definitions |
| [CONTRIBUTING.md](docs/CONTRIBUTING.md) | Contribution guidelines |

## Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Install package in editable mode
pip install -e .

# Run tests
pytest

# Format code
black fiscal_tone scripts
isort fiscal_tone scripts

# Check code quality
flake8 fiscal_tone scripts
mypy fiscal_tone
```

### Code Standards

- **Formatter**: [Black](https://github.com/psf/black) (100 char line length)
- **Import sorting**: [isort](https://pycqa.github.io/isort/) (black profile)
- **Linting**: [flake8](https://flake8.pycqa.org/)
- **Type checking**: [mypy](https://mypy.readthedocs.io/)
- **Docstrings**: Google style

## Data Sources

- **Source**: Peru's Fiscal Council ([cf.gob.pe](https://cf.gob.pe))
- **Documents**: Informes and Comunicados (2016-present)
- **Coverage**: 75+ official fiscal policy communications

## Research Context

This project supports research on fiscal policy communication and sentiment analysis in Peru. The Fiscal Tone Index measures the degree of concern expressed in Fiscal Council communications regarding fiscal discipline, sustainability, and governance.

### Citation

If you use this software in your research, please cite:

```bibtex
@software{fiscaltone2025,
  author = {Cruz, Jason},
  title = {FiscalTone: Fiscal Policy Sentiment Analysis for Peru},
  year = {2025},
  url = {https://github.com/JasonCruz18/FiscalTone}
}
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Peru's Fiscal Council (Consejo Fiscal) for publishing fiscal policy reports
- OpenAI for GPT-4o API
- Centro de Investigación de la Universidad del Pacífico (CIUP)

## Contact

- **Author**: Jason Cruz
- **Email**: jj.cruza@up.edu.pe
- **Issues**: [GitHub Issues](https://github.com/JasonCruz18/FiscalTone/issues)
