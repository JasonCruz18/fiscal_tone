# Tesseract OCR Setup Instructions

## Current Status

✅ **Code is ready** - All extraction logic implemented with OCR best practices
✅ **Folders created** - `footer_inspection/` with 39 debug visualizations
✅ **JSON file created** - `data/raw/scanned_pdfs_extracted_text.json` (empty, needs Tesseract)

⏳ **Tesseract configuration needed** - OCR engine must be accessible

---

## Option 1: Find Existing Tesseract Installation

You may already have Tesseract installed. Common locations:

```bash
# Check these paths:
ls "C:/Program Files/Tesseract-OCR/tesseract.exe"
ls "C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"
ls "C:/Users/$USER/AppData/Local/Programs/Tesseract-OCR/tesseract.exe"
```

**If found**, update line 23 in `scanned_pdf_extractor.py`:
```python
pytesseract.pytesseract.tesseract_cmd = r'C:\CORRECT\PATH\tesseract.exe'
```

---

## Option 2: Install Tesseract OCR

### Windows Installation (Recommended):

1. **Download installer:**
   - Visit: https://github.com/UB-Mannheim/tesseract/wiki
   - Download: `tesseract-ocr-w64-setup-5.3.x.exe` (latest version)

2. **Run installer:**
   - Default location: `C:\Program Files\Tesseract-OCR\`
   - **IMPORTANT:** Check "Add to PATH" during installation

3. **Install Spanish language data:**
   - During installation, select "Additional language data"
   - Check ☑ **Spanish (spa)**

4. **Verify installation:**
   ```bash
   tesseract --version
   ```
   Should output: `tesseract 5.3.x`

### Alternative: Conda Installation

```bash
conda install -c conda-forge tesseract
```

**Note:** Conda installation may not include Spanish language files.

---

## Option 3: Add to System PATH (If Already Installed)

If Tesseract is installed but not found:

1. **Find tesseract.exe location:**
   ```bash
   where tesseract 2>nul || find / -name tesseract.exe 2>/dev/null
   ```

2. **Add to PATH:**
   - Press `Win + R`, type `sysdm.cpl`, press Enter
   - Advanced tab → Environment Variables
   - Under "System variables", find "Path", click Edit
   - Click New, add: `C:\Path\To\Tesseract-OCR`
   - Click OK, **restart terminal**

3. **Verify:**
   ```bash
   tesseract --version
   ```

---

## Option 4: Python-Only Configuration (Quick Test)

If you can't modify system PATH, configure in Python:

**Edit `scanned_pdf_extractor.py` line 23:**
```python
# Replace with actual path after finding tesseract.exe
pytesseract.pytesseract.tesseract_cmd = r'C:\Full\Path\To\tesseract.exe'
```

**Find the path:**
```bash
# Windows
where tesseract

# Git Bash
find /c/ -name "tesseract.exe" 2>/dev/null | head -1
```

---

## Verification Steps

After setup, verify everything works:

### 1. Check Tesseract is accessible:
```bash
tesseract --version
```

Expected output:
```
tesseract 5.3.x
 leptonica-1.x
  libjpeg 9e : libpng 1.6.x : libtiff 4.5.x : zlib 1.2.x
```

### 2. Check Spanish language data:
```bash
tesseract --list-langs
```

Expected output should include:
```
List of available languages (3):
eng
osd
spa  ← Must be present
```

### 3. Test extraction:
```bash
python scanned_pdf_extractor.py
```

If successful, you'll see:
```
[Processing] INFORME_N_001-2017-CF.pdf
  [Page 1] Extracting... (1234 chars)
  [Page 2] Extracting... (2345 chars)
  ...
```

---

## What You Can Do Right Now (Without Tesseract)

Even without OCR, you can **review the detection quality**:

### 1. Review Footer Detection:
```bash
# Open footer_inspection/ folder
# Look at *_footer_analysis.png files
# Verify the red "FOOTER CROP" line is correctly positioned
```

**What to check:**
- ✅ Red crop line should be ABOVE footer content (page numbers, URLs, addresses)
- ✅ Green lines show detected footer separator lines
- ✅ Yellow lines mark the search region (last 3/4 of page)

### 2. Review Binarization Quality:
```bash
# Open test_results/ folder
# Compare binary_otsu.png, binary_adaptive.png, binary_fixed.png
```

**Otsu method should show:**
- Clear black text on white background
- Minimal noise
- Readable characters

### 3. Review Cropped Regions:
```bash
# Check footer_inspection/*_cropped.png files
# These show the exact regions that will be sent to OCR
```

---

## Troubleshooting

### Error: "tesseract is not installed or it's not in your PATH"

**Causes:**
1. Tesseract not installed → **Install** (Option 2)
2. Installed but not in PATH → **Add to PATH** (Option 3)
3. Wrong path in Python code → **Update** (Option 4)

**Quick fix:**
```bash
# Try to find tesseract
where tesseract  # Windows
which tesseract  # Linux/Mac

# If found, copy the path and update scanned_pdf_extractor.py line 23
```

### Error: "Error opening data file spa.traineddata"

**Cause:** Spanish language data not installed

**Fix:**
1. Download `spa.traineddata` from: https://github.com/tesseract-ocr/tessdata
2. Place in: `C:\Program Files\Tesseract-OCR\tessdata\spa.traineddata`

Or reinstall Tesseract and select Spanish during installation.

### Error: "FileNotFoundError: tesseract.exe"

**Cause:** Path in `scanned_pdf_extractor.py` is incorrect

**Fix:**
```bash
# Find correct path:
find /c/ -name "tesseract.exe" 2>/dev/null

# Update line 23 in scanned_pdf_extractor.py with correct path
```

---

## Expected Output After Setup

Once Tesseract is configured, running `python scanned_pdf_extractor.py` will:

1. **Process all 13 PDFs** (~2-5 minutes)
2. **Create `data/raw/scanned_pdfs_extracted_text.json`** with structure:
   ```json
   [
     {
       "filename": "INFORME_N_001-2017-CF.pdf",
       "page": 1,
       "text": "El presente informe contiene la opinión..."
     },
     {
       "filename": "INFORME_N_001-2017-CF.pdf",
       "page": 2,
       "text": "Este evento es la justificación..."
     }
   ]
   ```

3. **Update `footer_inspection/` folder** with all cropped images and analysis

---

## Summary

**Before running OCR extraction, you need:**
1. ✅ **Tesseract OCR installed** (Option 2 recommended)
2. ✅ **Spanish language data** (spa.traineddata)
3. ✅ **Tesseract in PATH** or configured in Python code

**After setup:**
- Run `python scanned_pdf_extractor.py`
- Review `footer_inspection/` folder to verify quality
- Use `data/raw/scanned_pdfs_extracted_text.json` for next steps

**Everything is ready to go once Tesseract is configured!** 🚀
