# Installation Guide

This guide covers multiple installation methods for FiscalTone.

## Table of Contents

- [System Requirements](#system-requirements)
- [Prerequisites](#prerequisites)
- [Installation Methods](#installation-methods)
  - [Method 1: Conda (Recommended)](#method-1-conda-recommended)
  - [Method 2: Pip + Virtual Environment](#method-2-pip--virtual-environment)
  - [Method 3: Development Installation](#method-3-development-installation)
- [Configuration](#configuration)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

## System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Python | 3.10 | 3.12 |
| RAM | 4 GB | 8 GB |
| Storage | 500 MB | 2 GB (with PDFs) |
| OS | Windows 10, macOS 10.15, Ubuntu 20.04 | Latest versions |

## Prerequisites

### 1. Python 3.10+

**Windows:**
Download from [python.org](https://www.python.org/downloads/) or use Anaconda.

**macOS:**
```bash
brew install python@3.12
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv python3-pip
```

### 2. Git

**Windows:**
Download from [git-scm.com](https://git-scm.com/download/win)

**macOS:**
```bash
brew install git
```

**Linux:**
```bash
sudo apt install git
```

### 3. Tesseract OCR (Optional - for scanned PDFs)

**Windows:**
1. Download installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
2. Run installer (default: `C:\Program Files\Tesseract-OCR`)
3. Check "Spanish" language during installation
4. Add to PATH or configure in `config.yaml`

**macOS:**
```bash
brew install tesseract tesseract-lang
```

**Linux:**
```bash
sudo apt install tesseract-ocr tesseract-ocr-spa
```

**Verify installation:**
```bash
tesseract --version
tesseract --list-langs  # Should include 'spa'
```

## Installation Methods

### Method 1: Conda (Recommended)

Conda provides a complete environment with all dependencies.

```bash
# Clone the repository
git clone https://github.com/JasonCruz18/FiscalTone.git
cd FiscalTone

# Create environment from file
conda env create -f environment.yml

# Activate environment
conda activate fiscal_tone

# Verify installation
python scripts/run_pipeline.py --list
```

**Update existing environment:**
```bash
conda env update -f environment.yml --prune
```

### Method 2: Pip + Virtual Environment

Use pip if you don't have Anaconda/Miniconda.

**Linux/macOS:**
```bash
# Clone the repository
git clone https://github.com/JasonCruz18/FiscalTone.git
cd FiscalTone

# Create virtual environment
python3 -m venv venv

# Activate environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Verify installation
python scripts/run_pipeline.py --list
```

**Windows (Command Prompt):**
```cmd
# Clone the repository
git clone https://github.com/JasonCruz18/FiscalTone.git
cd FiscalTone

# Create virtual environment
python -m venv venv

# Activate environment
venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Verify installation
python scripts/run_pipeline.py --list
```

**Windows (PowerShell):**
```powershell
# Clone the repository
git clone https://github.com/JasonCruz18/FiscalTone.git
cd FiscalTone

# Create virtual environment
python -m venv venv

# Activate environment
.\venv\Scripts\Activate.ps1

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Verify installation
python scripts/run_pipeline.py --list
```

### Method 3: Development Installation

For contributors who want to modify the codebase.

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/FiscalTone.git
cd FiscalTone

# Create environment (conda or venv)
conda env create -f environment.yml
conda activate fiscal_tone

# Install in editable mode with dev dependencies
pip install -r requirements-dev.txt
pip install -e .

# Verify
pytest
python scripts/run_pipeline.py --list
```

## Configuration

### 1. Copy Example Configuration

```bash
cp config/config.example.yaml config/config.yaml
```

### 2. Set OpenAI API Key

**Option A: Environment variable (recommended)**

Linux/macOS:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

Windows:
```cmd
set OPENAI_API_KEY=your-api-key-here
```

Add to shell profile for persistence:
```bash
# ~/.bashrc or ~/.zshrc
export OPENAI_API_KEY="your-api-key-here"
```

**Option B: Configuration file**

Edit `config/config.yaml`:
```yaml
openai:
  api_key: "your-api-key-here"  # Not recommended for shared machines
```

### 3. Configure Tesseract Path (Windows only)

If Tesseract is not in PATH, edit `config/config.yaml`:
```yaml
pdf_processing:
  ocr:
    tesseract_cmd: "C:/Program Files/Tesseract-OCR/tesseract.exe"
```

## Verification

### Quick Test

```bash
# List available stages
python scripts/run_pipeline.py --list

# Expected output:
# FiscalTone Pipeline Stages:
# ----------------------------------------
#   1. collect      - Web scraping and PDF download
#   2. classify     - PDF classification + metadata enrichment
#   3. extract      - Text extraction from PDFs
#   4. clean        - Text cleaning and normalization
#   5. analyze      - LLM-based fiscal tone classification
```

### Test Imports

```bash
python -c "from fiscal_tone.collectors import fc_collector; print('Collectors: OK')"
python -c "from fiscal_tone.processors import text_cleaner; print('Processors: OK')"
python -c "from fiscal_tone.analyzers import llm_classifier; print('Analyzers: OK')"
```

### Test PDF Processing

```bash
python -c "import fitz; print(f'PyMuPDF: {fitz.version}')"
python -c "import pdfplumber; print('pdfplumber: OK')"
```

### Test OCR (if installed)

```bash
python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
```

### Run Smoke Test

```bash
# Test clean stage (doesn't require PDFs)
python scripts/run_pipeline.py --stage clean
```

## Troubleshooting

### ImportError: No module named 'fitz'

PyMuPDF is installed as `pymupdf` but imported as `fitz`:
```bash
pip install pymupdf
```

### Tesseract not found

**Windows:**
```python
# In your script or config
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

**Linux/macOS:**
```bash
# Check if installed
which tesseract

# If not found, install
# macOS: brew install tesseract
# Linux: sudo apt install tesseract-ocr
```

### OpenAI API key not found

```bash
# Verify environment variable
echo $OPENAI_API_KEY  # Linux/macOS
echo %OPENAI_API_KEY%  # Windows cmd

# Set if missing
export OPENAI_API_KEY="your-key-here"
```

### Rate limit errors

Reduce rate limit in `config/config.yaml`:
```yaml
openai:
  rate_limit: 30  # Reduce from default 50
```

### PDF download failures

Some PDFs may have changed URLs. Check the metadata:
```bash
python -c "import json; data=json.load(open('metadata/cf_metadata.json', encoding='utf-8')); print([d for d in data if not d.get('pdf_url')])"
```

### Windows encoding errors

The pipeline handles this automatically, but if you see encoding errors:
```python
import sys
import codecs
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'replace')
```

### Conda environment conflicts

```bash
# Remove and recreate
conda deactivate
conda env remove -n fiscal_tone
conda env create -f environment.yml
```

### pip dependency conflicts

```bash
# Use fresh virtual environment
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Next Steps

After installation:

1. See [USAGE.md](USAGE.md) for running the pipeline
2. See [ARCHITECTURE.md](ARCHITECTURE.md) for system design
3. See [CONTRIBUTING.md](CONTRIBUTING.md) for development

## Uninstallation

**Conda:**
```bash
conda deactivate
conda env remove -n fiscal_tone
```

**Pip:**
```bash
deactivate
rm -rf venv
```

**Complete removal:**
```bash
cd ..
rm -rf FiscalTone
```
