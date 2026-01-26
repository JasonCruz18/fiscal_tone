# PDF Text Extraction Improvements

## Summary of Changes

This document summarizes the major improvements made to the PDF text extraction pipeline in `data_curation.py`.

---

## 1. Fixed Keyword False Positive (Case-Sensitive Matching)

### Problem
The keyword pattern `r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del? CF\b"` was matching lowercase text mid-sentence (e.g., "opinión del CF, esto revela...") due to the `re.IGNORECASE` flag.

**Example**: `Comunicado042024-VF.pdf` was incorrectly extracting from pages 4-5 instead of 1-5.

### Solution
- **Removed `re.IGNORECASE` flag** from keyword matching (line 972)
- Pattern now only matches title-case "Opinión del..." (section headers)
- Lowercase mid-sentence references are ignored

### Test Result
✅ `Comunicado042024-VF.pdf`: Now correctly extracts pages **1-5**

---

## 2. Fixed Anexo Detection to Stop All Subsequent Pages

### Problem
When "Anexo" was detected on a page, the code truncated content on that page but continued processing subsequent pages.

**Example**: `Pronunciamiento-FinanzasPublicas2022-vF.pdf` had Anexo on page 13, but page 14 was still extracted.

### Solution
- Added `anexo_detected` flag after Anexo pattern match
- Added **`break` statement** to exit page loop immediately (lines 1303, 1532)
- Applies to both single PDF and batch extraction functions

### Test Result
✅ `Pronunciamiento-FinanzasPublicas2022-vF.pdf`: Stops at page **12** (Anexo on page 13 excluded)

---

## 3. Robust Anexo Pattern Matching (Uppercase, Numbered Variants)

### Problem
The Anexo pattern only matched lowercase "Anexo" in body text. Large "ANEXO" titles were filtered out by font-size filtering before pattern matching could detect them.

**Example**: `Opinion-MMM2023-2026-cNotaAclaratoria.pdf` page 18 has "ANEXO" in large font, but was still extracted.

### Solution
Implemented **two-stage Anexo detection**:

#### Stage 1: Early Detection (Before Font Filtering)
- Uses `page.extract_text()` to get raw page text BEFORE font filtering
- Checks if page starts with "ANEXO" using robust pattern:
  ```python
  anexo_start_pattern = r"^\s*ANEXOS?(?:\s+(?:[IVXLCDM]+|\d+))?\s*:?"
  ```
- Handles variations: ANEXO, Anexo, ANEXOS, ANEXO 1, ANEXO I, etc.
- Skips entire page immediately with `break` (lines 1202-1213, 1472-1479)

#### Stage 2: Late Detection (After Font Filtering)
- Checks filtered body text for mid-page Anexo references
- Truncates content where Anexo is found
- Then applies `break` to skip subsequent pages (lines 1282-1303, 1516-1532)

### Anexo Pattern Features
- **Case-insensitive**: Matches ANEXO, Anexo, anexo
- **Plural support**: ANEXO, ANEXOS
- **Numbered variants**: ANEXO 1, ANEXO I, ANEXO II
- **Optional colon**: ANEXO:, ANEXO 1:

### Test Result
✅ `Opinion-MMM2023-2026-cNotaAclaratoria.pdf`: Stops at page **17** (ANEXO on page 18 excluded)

---

## 4. Incremental Extraction Function

### Problem
Re-running `extract_text_from_editable_pdfs()` would re-process ALL PDFs in the folder, even if they were already extracted. This is inefficient when adding new PDFs incrementally.

### Solution
Created new function: **`extract_text_from_editable_pdfs_incremental()`** (lines 1593-1885)

#### Key Features
- **Reads existing JSON** and identifies already-extracted PDF filenames
- **Filters for NEW PDFs** not in the JSON file
- **Processes only NEW PDFs** using same extraction logic
- **Appends new records** to existing records (preserves previous work)
- **`force_reextract` parameter** allows re-processing all PDFs after code changes

#### Workflow
1. Load existing JSON file (if exists)
2. Extract set of already-extracted PDF filenames
3. Compare against files in `editable` folder
4. Identify NEW PDFs not in JSON
5. Extract only NEW PDFs
6. Combine existing + new records
7. Save updated JSON

#### Performance
- **First run**: Extracts all 64 PDFs (~2-3 minutes)
- **Second run**: Skips all PDFs (<1 second) ⚡
- **Adding 5 new PDFs**: Only extracts 5 new PDFs (~15 seconds)

### Usage Example

```python
from data_curation import extract_text_from_editable_pdfs_incremental

# Normal incremental extraction (skip already-extracted PDFs)
extract_text_from_editable_pdfs_incremental(
    editable_folder="data/raw/editable",
    output_folder="data/raw",
    output_filename="all_extracted_text.json",
    search_opinion_keyword=True
)

# Force re-extraction after code changes
extract_text_from_editable_pdfs_incremental(
    editable_folder="data/raw/editable",
    output_folder="data/raw",
    output_filename="all_extracted_text.json",
    search_opinion_keyword=True,
    force_reextract=True  # Re-process all PDFs
)
```

---

## Test Scripts

Several test scripts were created to verify the improvements:

- **`test_incremental_extraction.py`**: Tests first run of incremental extraction
- **`test_incremental_second_run.py`**: Verifies second run skips all PDFs
- **`test_anexo_fix.py`**: Tests improved Anexo detection on Opinion-MMM2023-2026
- **`test_batch_extraction.py`**: Tests batch extraction with module cache clearing
- **`debug_anexo_pattern.py`**: Tests Anexo pattern matching variations
- **`debug_page18_detailed.py`**: Analyzes why page 18 "ANEXO" wasn't detected

---

## Verification Results

All three key test cases passed:

| PDF | Expected | Actual | Status |
|-----|----------|--------|--------|
| `Comunicado042024-VF.pdf` | Pages 1-5 | Pages 1-5 | ✅ PASS |
| `Pronunciamiento-FinanzasPublicas2022-vF.pdf` | Stop at page 12 | Stop at page 12 | ✅ PASS |
| `Opinion-MMM2023-2026-cNotaAclaratoria.pdf` | Stop at page 17 | Stop at page 17 | ✅ PASS |

---

## Module Caching Issue

### Problem
Python caches imported modules in `sys.modules`. When code is updated during development, test scripts would use the OLD cached version instead of the NEW code.

### Solution
Added module cache clearing to all test scripts:

```python
# Clear cached module to ensure latest code is loaded
if 'data_curation' in sys.modules:
    del sys.modules['data_curation']

# Import fresh version
from data_curation import extract_text_from_editable_pdfs_incremental
```

---

## Summary

These improvements provide:

✅ **Accurate keyword matching** - No false positives from mid-sentence text
✅ **Complete Anexo exclusion** - Stops processing at Anexo sections
✅ **Robust pattern detection** - Handles uppercase, plural, numbered variants
✅ **Efficient incremental processing** - Only extracts new PDFs
✅ **Safe re-extraction** - `force_reextract` parameter for code updates

The pipeline is now production-ready for continuous incremental updates!
