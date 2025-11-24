"""
Test all 4 problematic Pronunciamiento PDFs with the new font range fix
"""
import sys
import os

sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

import builtins
builtins.input = lambda *args: "."

from data_curation import extract_text_from_single_pdf_v2

base_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable"

test_cases = [
    ("Pronunciamiento-DCRF-2020-publicar.pdf", 4),
    ("PronunciamientoDCRF-RFSN-2021-vf.pdf", 5),
    ("Pronunciamiento-DU-031-subnacionalvf.pdf", 2),
    ("Pronunciamiento-MMM2022-vf.pdf", 3),
]

print("="*80)
print("TESTING 4 PROBLEMATIC PRONUNCIAMIENTO PDFs")
print("="*80)

results = []

for pdf_filename, expected_start_page in test_cases:
    pdf_path = f"{base_path}\\{pdf_filename}"
    json_file = pdf_path.replace('.pdf', '_v2.json')

    # Delete old JSON
    if os.path.exists(json_file):
        os.remove(json_file)

    print(f"\n{'='*80}")
    print(f"Testing: {pdf_filename}")
    print(f"Expected start page: {expected_start_page}")
    print('='*80)

    # Run extraction with NEW defaults (FONT_MIN=10.5, FONT_MAX=14.5)
    extract_text_from_single_pdf_v2(
        pdf_path,
        search_opinion_keyword=True
    )

    # Check results
    if os.path.exists(json_file):
        import json
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if data:
            first_page = data[0]['page']
            last_page = data[-1]['page']
            total_chars = sum(len(d['text']) for d in data)

            success = (first_page == expected_start_page)
            results.append({
                'file': pdf_filename,
                'expected': expected_start_page,
                'actual': first_page,
                'pages': len(data),
                'chars': total_chars,
                'success': success
            })

            status = "SUCCESS" if success else "FAILED"
            print(f"\n{status}: Started from page {first_page} (expected {expected_start_page})")
            print(f"Extracted {len(data)} pages ({total_chars} chars)")
        else:
            results.append({
                'file': pdf_filename,
                'expected': expected_start_page,
                'actual': None,
                'success': False
            })
            print(f"\nFAILED: Empty JSON")
    else:
        results.append({
            'file': pdf_filename,
            'expected': expected_start_page,
            'actual': None,
            'success': False
        })
        print(f"\nFAILED: No JSON created")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)

for r in results:
    status = "PASS" if r['success'] else "FAIL"
    actual_str = str(r['actual']) if r['actual'] else "N/A"
    print(f"[{status}] {r['file'][:40]:<40} | Start: {r['expected']} -> {actual_str}")

success_count = sum(1 for r in results if r['success'])
print(f"\nTotal: {success_count}/{len(results)} passed")
