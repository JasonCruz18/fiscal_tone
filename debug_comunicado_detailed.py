"""
Detailed investigation of Comunicado042024-VF extraction
"""
import sys
import os

sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

import builtins
builtins.input = lambda *args: "."

from data_curation import extract_text_from_single_pdf_v2

test_file = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Comunicado042024-VF.pdf"

# Delete old JSON
json_file = test_file.replace('.pdf', '_v2.json')
if os.path.exists(json_file):
    os.remove(json_file)

print("="*80)
print("DETAILED TEST: Comunicado042024-VF")
print("="*80)
print()

# Run extraction
extract_text_from_single_pdf_v2(test_file, search_opinion_keyword=True)

# Check JSON output
if os.path.exists(json_file):
    import json
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("\n" + "="*80)
    print("JSON ANALYSIS")
    print("="*80)

    if data:
        pages = [r['page'] for r in data]
        print(f"Pages in JSON: {pages}")
        print(f"First page: {pages[0]}")
        print(f"Last page: {pages[-1]}")
        print(f"Total pages: {len(pages)}")

        print(f"\nFirst record text preview:")
        print(f"  Page: {data[0]['page']}")
        print(f"  Text (first 200 chars): {data[0]['text'][:200]}...")

        if pages[0] != 1:
            print(f"\n*** ISSUE CONFIRMED: Started from page {pages[0]} instead of page 1 ***")
        else:
            print(f"\n✓ OK: Started from page 1 as expected")
    else:
        print("JSON is empty!")
else:
    print("JSON file not created!")
