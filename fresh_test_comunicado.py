"""
Fresh test with clean environment - delete old JSON and re-extract
"""
import sys
import os

# Clear any cached imports
if 'data_curation' in sys.modules:
    del sys.modules['data_curation']

sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

import builtins
builtins.input = lambda *args: "."

# Import fresh
from data_curation import extract_text_from_single_pdf_v2

test_file = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Comunicado042024-VF.pdf"
json_file = test_file.replace('.pdf', '_v2.json')

# Force delete old JSON
if os.path.exists(json_file):
    os.remove(json_file)
    print(f"Deleted old JSON: {json_file}\n")

print("="*80)
print("FRESH EXTRACTION TEST")
print("="*80)
print("PDF: Comunicado042024-VF.pdf")
print("Expected: Extract pages 1-5 (no keyword match)")
print("="*80)
print()

# Extract
extract_text_from_single_pdf_v2(test_file, search_opinion_keyword=True)

# Verify
print("\n" + "="*80)
print("VERIFICATION")
print("="*80)

if os.path.exists(json_file):
    import json
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    pages = [r['page'] for r in data]
    print(f"Pages in JSON: {pages}")

    if pages == [1, 2, 3, 4, 5]:
        print("\nRESULT: CORRECT - Extracted pages 1-5")
        print("The case-sensitive fix is working!")
    elif pages == [4, 5]:
        print("\nRESULT: INCORRECT - Only pages 4-5")
        print("ERROR: The fix is NOT applied or you're using old code!")
    else:
        print(f"\nRESULT: UNEXPECTED - Got pages {pages}")
else:
    print("ERROR: JSON file was not created!")
