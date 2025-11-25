"""
Test the improved Anexo detection on Opinion-MMM2023-2026-cNotaAclaratoria
"""
import sys
import os

# Force module reload
if 'data_curation' in sys.modules:
    del sys.modules['data_curation']

sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

import builtins
builtins.input = lambda *args: "."

from data_curation import extract_text_from_single_pdf_v2

test_file = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Opinion-MMM2023-2026-cNotaAclaratoria.pdf"

# Delete old JSON
json_file = test_file.replace('.pdf', '_v2.json')
if os.path.exists(json_file):
    os.remove(json_file)

print("="*80)
print("TESTING IMPROVED ANEXO DETECTION")
print("="*80)
print("PDF: Opinion-MMM2023-2026-cNotaAclaratoria")
print("Expected: Stop BEFORE page 18 (page 18 starts with 'ANEXO')")
print("="*80)
print()

# Run extraction
extract_text_from_single_pdf_v2(test_file, search_opinion_keyword=True)

# Verify
if os.path.exists(json_file):
    import json
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)

    if data:
        pages = [r['page'] for r in data]
        last_page = max(pages)

        print(f"Pages extracted: {min(pages)}-{last_page}")
        print(f"Total pages: {len(pages)}")

        if last_page < 18:
            print(f"\n✓ SUCCESS: Stopped at page {last_page} (before Anexo on page 18)")
        elif last_page == 18:
            print(f"\n✗ FAILED: Included page 18 (should have stopped before)")
        elif last_page > 18:
            print(f"\n✗ FAILED: Included page {last_page} (should have stopped at page 17)")
    else:
        print("JSON is empty!")
else:
    print("JSON file not created!")
