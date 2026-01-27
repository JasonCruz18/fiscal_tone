# Installation Guide

## System Requirements

- **Python**: 3.12 or higher
- **Operating System**: Windows, macOS, or Linux
- **Memory**: 4GB RAM minimum (8GB recommended for large PDF batches)
- **Disk Space**: ~500MB for dependencies + space for PDFs

## Step 1: Clone Repository

```bash
git clone https://github.com/JasonCruz18/FiscalTone.git
cd FiscalTone
```

## Step 2: Create Virtual Environment

### Linux/macOS
```bash
python3 -m venv venv
source venv/bin/activate
```

### Windows (Command Prompt)
```cmd
python -m venv venv
venv\Scripts\activate
```

### Windows (PowerShell)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

## Step 3: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Core Dependencies

| Package | Purpose |
|---------|---------|
| `requests` | HTTP requests for web scraping |
| `beautifulsoup4` | HTML parsing |
| `PyMuPDF` (fitz) | PDF text extraction |
| `pdfplumber` | Advanced PDF processing |
| `pytesseract` | OCR interface |
| `pdf2image` | PDF to image conversion |
| `Pillow` | Image processing |
| `pandas` | Data manipulation |
| `openai` | GPT-4o API client |
| `aiolimiter` | Async rate limiting |
| `tenacity` | Retry logic |

## Step 4: Install Tesseract OCR (For Scanned PDFs)

Tesseract is required for processing scanned PDFs.

### Windows

1. Download installer from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
2. Run installer (default path: `C:\Program Files\Tesseract-OCR`)
3. Add to PATH or set in environment:
   ```cmd
   set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
   ```
4. Install Spanish language pack during installation

### macOS

```bash
brew install tesseract tesseract-lang
```

### Linux (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-spa
```

### Verify Installation

```bash
tesseract --version
tesseract --list-langs  # Should include 'spa'
```

## Step 5: Configure OpenAI API Key

The LLM classification stage requires an OpenAI API key.

### Linux/macOS
```bash
export OPENAI_API_KEY="your-api-key-here"
```

### Windows (Command Prompt)
```cmd
set OPENAI_API_KEY=your-api-key-here
```

### Windows (PowerShell)
```powershell
$env:OPENAI_API_KEY="your-api-key-here"
```

### Persistent Configuration

Add to your shell profile (`~/.bashrc`, `~/.zshrc`, or Windows environment variables).

## Step 6: Verify Installation

```bash
# Check Python version
python --version

# Test imports
python -c "from fiscal_tone.collectors import fc_collector; print('Collectors: OK')"
python -c "from fiscal_tone.processors import text_cleaner; print('Processors: OK')"
python -c "from fiscal_tone.analyzers import llm_classifier; print('Analyzers: OK')"

# List pipeline stages
python scripts/run_pipeline.py --list
```

## Troubleshooting

### ImportError: No module named 'fitz'

PyMuPDF is installed as `pymupdf` but imported as `fitz`:
```bash
pip install pymupdf
```

### Tesseract not found

Ensure Tesseract is in PATH or set explicitly:
```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

### OpenAI API rate limits

The pipeline uses rate limiting (50 RPM by default). If you hit limits:
- Check your API tier at https://platform.openai.com/account/limits
- Adjust rate limit in `fiscal_tone/analyzers/llm_classifier.py`

### PDF download failures

Some PDFs may be behind authentication or have changed URLs. The pipeline:
- Implements multiple fallback strategies
- Saves progress incrementally
- Can resume from interruptions

## Next Steps

See [USAGE.md](USAGE.md) for how to run the pipeline.
