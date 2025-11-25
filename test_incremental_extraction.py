"""
Test incremental extraction workflow

This demonstrates how the new extract_text_from_editable_pdfs_incremental() function:
1. Only extracts NEW PDFs not already in the JSON file
2. Skips already-extracted PDFs for efficiency
3. Appends new records to existing records
"""
import sys
import os
import json

# Clear cached module to ensure latest code is loaded
if 'data_curation' in sys.modules:
    del sys.modules['data_curation']

sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

import builtins
builtins.input = lambda *args: "."

from data_curation import extract_text_from_editable_pdfs_incremental

# Test configuration
editable_folder = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable"
output_folder = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw"
output_filename = "all_extracted_text.json"
output_path = os.path.join(output_folder, output_filename)

print("=" * 80)
print("TESTING INCREMENTAL EXTRACTION")
print("=" * 80)
print()

# Check if JSON exists
if os.path.exists(output_path):
    with open(output_path, 'r', encoding='utf-8') as f:
        existing_data = json.load(f)
    print(f"✓ Existing JSON found: {len(existing_data)} records")

    # Show already-extracted PDFs
    existing_pdfs = set(r['pdf_filename'] for r in existing_data)
    print(f"✓ Already-extracted PDFs: {len(existing_pdfs)}")
    if existing_pdfs:
        print("\n  Sample of already-extracted PDFs:")
        for pdf in list(existing_pdfs)[:5]:
            print(f"    - {pdf}")
        if len(existing_pdfs) > 5:
            print(f"    ... and {len(existing_pdfs) - 5} more")
else:
    print("⚠ No existing JSON found - will extract all PDFs")

print()
print("=" * 80)
print("RUNNING INCREMENTAL EXTRACTION")
print("=" * 80)
print()

# Run incremental extraction
extract_text_from_editable_pdfs_incremental(
    editable_folder=editable_folder,
    output_folder=output_folder,
    output_filename=output_filename,
    search_opinion_keyword=True,
    FONT_MIN=10.5,
    FONT_MAX=11.9
)

print()
print("=" * 80)
print("VERIFICATION")
print("=" * 80)
print()

# Verify results
if os.path.exists(output_path):
    with open(output_path, 'r', encoding='utf-8') as f:
        final_data = json.load(f)

    print(f"✓ Final JSON has {len(final_data)} records")

    # Show PDFs in final JSON
    final_pdfs = set(r['pdf_filename'] for r in final_data)
    print(f"✓ Total unique PDFs: {len(final_pdfs)}")

    # Count pages per PDF
    from collections import defaultdict
    pdf_pages = defaultdict(list)
    for record in final_data:
        pdf_pages[record['pdf_filename']].append(record['page'])

    print(f"\n  PDFs with extracted pages:")
    for pdf, pages in sorted(pdf_pages.items()):
        page_range = f"{min(pages)}-{max(pages)}" if pages else "none"
        print(f"    - {pdf}: pages {page_range} ({len(pages)} pages)")
else:
    print("✗ JSON file not created!")

print()
print("=" * 80)
print("INCREMENTAL EXTRACTION TEST COMPLETE")
print("=" * 80)
