"""
Test both fixes:
1. Case-sensitive keyword matching (Comunicado042024-VF)
2. Anexo detection stops all subsequent pages (Pronunciamiento-FinanzasPublicas2022-vF)
"""
import sys
import os

sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

import builtins
builtins.input = lambda *args: "."

from data_curation import extract_text_from_single_pdf_v2

base_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable"

# Test cases
test_cases = [
    {
        "file": "Comunicado042024-VF.pdf",
        "expected_start": 1,  # Should NOT match lowercase "opinión del CF, esto..."
        "issue": "False positive keyword match (lowercase)"
    },
    {
        "file": "Pronunciamiento-FinanzasPublicas2022-vF.pdf",
        "expected_last": 12,  # Should stop at page 12 when Anexo is detected
        "issue": "Anexo not stopping subsequent pages"
    }
]

print("="*80)
print("TESTING BOTH FIXES")
print("="*80)
print()

results = []

for test in test_cases:
    pdf_path = os.path.join(base_path, test["file"])
    json_file = pdf_path.replace('.pdf', '_v2.json')

    # Delete old JSON
    if os.path.exists(json_file):
        os.remove(json_file)

    print(f"\n{'='*80}")
    print(f"Testing: {test['file']}")
    print(f"Issue: {test['issue']}")
    print('='*80)

    # Run extraction
    extract_text_from_single_pdf_v2(pdf_path, search_opinion_keyword=True)

    # Check results
    if os.path.exists(json_file):
        import json
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if data:
            pages = [r['page'] for r in data]
            first_page = min(pages)
            last_page = max(pages)

            # Check expectations
            if "expected_start" in test:
                success = (first_page == test["expected_start"])
                results.append({
                    "file": test["file"],
                    "test": "keyword",
                    "expected": f"start={test['expected_start']}",
                    "actual": f"start={first_page}",
                    "success": success
                })
                status = "PASS" if success else "FAIL"
                print(f"\n{status}: Started from page {first_page} (expected {test['expected_start']})")

            if "expected_last" in test:
                success = (last_page == test["expected_last"])
                results.append({
                    "file": test["file"],
                    "test": "anexo",
                    "expected": f"last={test['expected_last']}",
                    "actual": f"last={last_page}",
                    "success": success
                })
                status = "PASS" if success else "FAIL"
                print(f"\n{status}: Stopped at page {last_page} (expected {test['expected_last']})")

            print(f"Pages: {pages}")
        else:
            print(f"\nFAILED: Empty JSON")
            results.append({"file": test["file"], "success": False})
    else:
        print(f"\nFAILED: No JSON created")
        results.append({"file": test["file"], "success": False})

print("\n" + "="*80)
print("SUMMARY")
print("="*80)

for r in results:
    status = "PASS" if r["success"] else "FAIL"
    print(f"[{status}] {r['file'][:40]:<40} | {r.get('test', 'N/A')}: {r.get('expected', 'N/A')} -> {r.get('actual', 'N/A')}")

success_count = sum(1 for r in results if r["success"])
print(f"\nTotal: {success_count}/{len(results)} passed")
