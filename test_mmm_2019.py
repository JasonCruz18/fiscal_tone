"""
Test the "Opinión de CF" pattern fix
"""
import sys
import os

sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

import builtins
builtins.input = lambda *args: "."

from data_curation import extract_text_from_single_pdf_v2

test_file = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\CF-Pronunciamiento-MMM-2019-2022_15_8_2018-enviada-al-MEF-1.pdf"

# Delete old JSON
json_file = test_file.replace('.pdf', '_v2.json')
if os.path.exists(json_file):
    os.remove(json_file)

print("="*80)
print("TESTING: CF-Pronunciamiento-MMM-2019-2022")
print("Expected: 'Opinión de CF' keyword on page 5")
print("="*80)
print()

# Run extraction
extract_text_from_single_pdf_v2(test_file, search_opinion_keyword=True)

# Check results
if os.path.exists(json_file):
    import json
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if data:
        print(f"\n{'='*80}")
        print("RESULT")
        print("="*80)
        print(f"First page: {data[0]['page']} (expected 5)")
        print(f"Total pages: {len(data)}")
        print(f"Total chars: {sum(len(d['text']) for d in data)}")

        if data[0]['page'] == 5:
            print("\n✅ SUCCESS! Extraction started from page 5")
        else:
            print(f"\n❌ FAILED! Started from page {data[0]['page']} instead of 5")
    else:
        print("\n❌ FAILED: Empty JSON")
else:
    print("\n❌ FAILED: No JSON created")
