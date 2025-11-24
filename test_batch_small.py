"""
Small test of batch extraction with just 3 PDFs
"""
import sys
import os
import shutil

sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

import builtins
builtins.input = lambda *args: "."

from data_curation import extract_text_from_editable_pdfs

# Create a temporary test folder with just 3 PDFs
test_folder = "data/raw/test_small"
os.makedirs(test_folder, exist_ok=True)

# Copy 3 test PDFs (the ones we already tested)
test_pdfs = [
    "Pronunciamiento-DCRF-2020-publicar.pdf",
    "PronunciamientoDCRF-RFSN-2021-vf.pdf",
    "CF-Pronunciamiento-MMM-2019-2022_15_8_2018-enviada-al-MEF-1.pdf"
]

for pdf in test_pdfs:
    src = f"data/raw/editable/{pdf}"
    dst = f"{test_folder}/{pdf}"
    if os.path.exists(src):
        shutil.copy2(src, dst)
        print(f"Copied: {pdf}")

print("\n" + "="*80)
print("TESTING BATCH EXTRACTION WITH 3 PDFs")
print("="*80)
print()

# Run batch extraction on test folder
extract_text_from_editable_pdfs(
    editable_folder=test_folder,
    output_folder="data/raw",
    output_filename="test_batch_small.json",
    search_opinion_keyword=True
)

# Verify output
output_file = "data/raw/test_batch_small.json"
if os.path.exists(output_file):
    import json
    with open(output_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)

    # Group by PDF
    pdf_groups = {}
    for record in data:
        pdf = record['pdf_filename']
        if pdf not in pdf_groups:
            pdf_groups[pdf] = []
        pdf_groups[pdf].append(record)

    for pdf, records in pdf_groups.items():
        pages = [r['page'] for r in records]
        total_chars = sum(len(r['text']) for r in records)
        print(f"\n{pdf}:")
        print(f"  Pages: {min(pages)}-{max(pages)} ({len(pages)} pages)")
        print(f"  Characters: {total_chars:,}")

    print(f"\nTotal records in JSON: {len(data)}")

# Cleanup
print(f"\nCleaning up test folder: {test_folder}")
shutil.rmtree(test_folder)
