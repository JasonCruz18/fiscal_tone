"""
Debug Anexo detection issue in Pronunciamiento-FinanzasPublicas2022-vF
"""
import sys
sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

import builtins
builtins.input = lambda *args: "."

from data_curation import extract_text_from_single_pdf_v2
import os

test_file = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Pronunciamiento-FinanzasPublicas2022-vF.pdf"

# Delete old JSON
json_file = test_file.replace('.pdf', '_v2.json')
if os.path.exists(json_file):
    os.remove(json_file)

print("Testing Anexo detection on Pronunciamiento-FinanzasPublicas2022-vF")
print("Expected: Extract until page 12, then STOP (skip pages 13, 14, etc.)")
print("="*80)
print()

extract_text_from_single_pdf_v2(test_file, search_opinion_keyword=True)

# Check which pages were extracted
if os.path.exists(json_file):
    import json
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    pages = [r['page'] for r in data]
    print("\n" + "="*80)
    print("RESULT")
    print("="*80)
    print(f"Pages extracted: {min(pages)}-{max(pages)}")
    print(f"All pages: {pages}")

    if max(pages) > 12:
        print(f"\nISSUE CONFIRMED: Extracted page {max(pages)} after Anexo section!")
    else:
        print(f"\nOK: Stopped at page {max(pages)}")
