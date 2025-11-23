"""
Test script for scanned PDF text extraction using OCR.

This script tests the extract_text_from_scanned_pdf() function on a single PDF file
and provides detailed validation feedback.

Usage:
    python test_scanned_pdf.py

Before running:
    1. Install dependencies: pip install pytesseract pdf2image Pillow
    2. Install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki
    3. Ensure scanned PDFs exist in data/raw/scanned/

Note: This script imports only the OCR functions without triggering the main pipeline.
"""

import os
import json
import re
from pathlib import Path
from time import time as timer

# Check for OCR dependencies
try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image, ImageEnhance, ImageFilter
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    print("Run: pip install pytesseract pdf2image Pillow")
    print("Also install Tesseract OCR: https://github.com/UB-Mannheim/tesseract/wiki")
    exit(1)

# Import OCR functions by executing only the relevant section
import sys
sys.path.insert(0, str(Path(__file__).parent))

# Since data_curation.py has interactive input, we'll import the functions dynamically
# by loading only the function definitions we need

# Prepare globals for exec (provide all necessary imports)
exec_globals = {
    'os': os,
    'json': json,
    're': re,
    'timer': timer,
    'pytesseract': pytesseract,
    'convert_from_path': convert_from_path,
    'Image': Image,
    'ImageEnhance': ImageEnhance,
    'ImageFilter': ImageFilter,
    '__name__': '__main__',
}
exec_locals = {}

# Read the data_curation.py file and extract only the OCR section
curation_file = Path(__file__).parent / "data_curation.py"
with open(curation_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Extract only section 7 (OCR functions)
# Find the start and end of section 7
section_7_start = content.find("# 7. TEXT EXTRACTION FROM SCANNED PDFS (OCR)")
if section_7_start == -1:
    print("❌ Could not find OCR section in data_curation.py")
    exit(1)

# Extract from section 7 to end of pipeline
section_7_end = content.find("# END OF PIPELINE", section_7_start)
ocr_code = content[section_7_start:section_7_end]

# Execute only the OCR code to get the functions
exec(ocr_code, exec_globals, exec_locals)

# Extract the functions we need
extract_text_from_scanned_pdf = exec_locals['extract_text_from_scanned_pdf']
validate_extraction = exec_locals['validate_extraction']
batch_extract_scanned_pdfs = exec_locals.get('batch_extract_scanned_pdfs')


def test_single_pdf(pdf_path, output_json_path=None, dpi=300):
    """
    Tests OCR extraction on a single scanned PDF.

    Args:
        pdf_path: str, path to PDF file to test
        output_json_path: str, optional path to save results (default: same folder as PDF)
        dpi: int, resolution for OCR (default 300)
    """
    print("="*80)
    print("SCANNED PDF EXTRACTION TEST")
    print("="*80)
    print(f"\nTest file: {pdf_path}")
    print(f"DPI: {dpi}\n")

    # Check if file exists
    if not os.path.exists(pdf_path):
        print(f"❌ Error: File not found: {pdf_path}")
        return

    # Extract paragraphs
    paragraphs = extract_text_from_scanned_pdf(pdf_path, dpi=dpi)

    # Validate extraction
    print("\n" + "="*80)
    print("VALIDATION RESULTS")
    print("="*80)

    validation = validate_extraction(paragraphs)

    if validation['passed']:
        print("✅ VALIDATION PASSED")
    else:
        print("⚠️  VALIDATION FAILED")

    if validation['issues']:
        print("\n❌ Issues found:")
        for issue in validation['issues']:
            print(f"   - {issue}")

    if validation['warnings']:
        print("\n⚡ Warnings:")
        for warning in validation['warnings']:
            print(f"   - {warning}")

    # Print paragraph preview
    print("\n" + "="*80)
    print("EXTRACTED PARAGRAPHS PREVIEW")
    print("="*80)

    for i, para in enumerate(paragraphs[:5], start=1):  # Show first 5 paragraphs
        print(f"\n[Paragraph {i}] (Page {para['page']})")
        print("-"*80)
        preview = para['text'][:200] + "..." if len(para['text']) > 200 else para['text']
        print(preview)

    if len(paragraphs) > 5:
        print(f"\n... and {len(paragraphs) - 5} more paragraphs")

    # Save to JSON
    if output_json_path is None:
        # Save in same directory as PDF
        output_json_path = pdf_path.replace('.pdf', '_extracted.json')

    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(paragraphs, f, ensure_ascii=False, indent=2)

    print("\n" + "="*80)
    print("OUTPUT")
    print("="*80)
    print(f"Total paragraphs extracted: {len(paragraphs)}")
    print(f"Results saved to: {output_json_path}")


def test_batch_scanned_folder(scanned_folder, output_json_path):
    """
    Tests batch extraction on all scanned PDFs in a folder.

    Args:
        scanned_folder: str, path to folder containing scanned PDFs
        output_json_path: str, path to save combined results
    """
    print("="*80)
    print("BATCH SCANNED PDF EXTRACTION TEST")
    print("="*80)
    print(f"\nScanned folder: {scanned_folder}")
    print(f"Output: {output_json_path}\n")

    if not os.path.exists(scanned_folder):
        print(f"❌ Error: Folder not found: {scanned_folder}")
        return

    # Run batch extraction
    results = batch_extract_scanned_pdfs(scanned_folder, output_json_path)

    print(f"\n✅ Batch extraction complete!")
    print(f"Total paragraphs: {len(results)}")


if __name__ == "__main__":
    # Configuration
    PROJECT_ROOT = Path(__file__).parent
    SCANNED_FOLDER = PROJECT_ROOT / "data" / "raw" / "scanned"

    # Test options
    TEST_MODE = "single"  # Options: "single" or "batch"

    if TEST_MODE == "single":
        # Test single PDF extraction
        # Find first PDF in scanned folder
        pdf_files = list(SCANNED_FOLDER.glob("*.pdf"))

        if not pdf_files:
            print("❌ No PDF files found in data/raw/scanned/")
            print(f"   Searched in: {SCANNED_FOLDER}")
        else:
            # Test with first PDF found
            test_pdf = pdf_files[0]
            test_single_pdf(
                pdf_path=str(test_pdf),
                dpi=300
            )

            print("\n" + "="*80)
            print("💡 TIP: To test other PDFs, modify the pdf_path in this script.")
            print("="*80)

    elif TEST_MODE == "batch":
        # Test batch extraction on all scanned PDFs
        output_path = PROJECT_ROOT / "data" / "output" / "scanned_pdfs_extracted.json"
        test_batch_scanned_folder(
            scanned_folder=str(SCANNED_FOLDER),
            output_json_path=str(output_path)
        )

    else:
        print(f"❌ Invalid TEST_MODE: {TEST_MODE}")
        print("   Options: 'single' or 'batch'")
