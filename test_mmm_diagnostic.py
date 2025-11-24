"""
Diagnostic test for MMM PDF - shows start_page and extraction details
"""
import sys
import codecs
import os

# Fix UTF-8 encoding
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Force module reload to get latest changes
if 'data_curation' in sys.modules:
    del sys.modules['data_curation']

# Import fresh
sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

# Monkey-patch the input to avoid interactive prompt
import builtins
original_input = builtins.input
builtins.input = lambda *args, **kwargs: "."

from data_curation import extract_text_from_single_pdf_v2

# Restore original input
builtins.input = original_input

# Test file
test_file = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\CF-Informe-MMM2124-cNotaAclaratoria-28-de-agosto-VF-publicada.pdf"

print("\n" + "="*100)
print("DIAGNOSTIC TEST: MMM PDF WITH FIXED FONT RANGE (11-15pt)")
print("="*100)
print(f"\nFile: {os.path.basename(test_file)}")
print("Expected: Should find 'Opinión del CF sobre...' on page 7 at 14.0pt")
print("Expected: JSON should start with page 7, not page 1")
print("\n" + "="*100 + "\n")

try:
    # Delete old JSON files to avoid confusion
    json_path = test_file.replace('.pdf', '_v2.json')
    if os.path.exists(json_path):
        os.remove(json_path)
        print(f"🗑️  Deleted old JSON: {os.path.basename(json_path)}\n")

    # Run extraction
    extract_text_from_single_pdf_v2(
        test_file,
        FONT_MIN=11.0,
        FONT_MAX=11.9,
        exclude_bold=False,
        vertical_threshold=15,
        first_page_header_cutoff=100,
        subsequent_header_cutoff=70,
        footer_cutoff_distance=100,
        last_page_footer_cutoff=120,
        left_margin=70,
        right_margin=70,
        exclude_specific_sizes=True,
        search_opinion_keyword=True
    )

    print("\n" + "="*100)
    print("EXTRACTION COMPLETE - CHECK JSON FILE")
    print("="*100)

    # Read and show first record from JSON
    import json
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print(f"\n📄 JSON file: {os.path.basename(json_path)}")
        print(f"   Total records: {len(data)}")

        if data:
            first_record = data[0]
            print(f"\n   ✅ First record:")
            print(f"      Page: {first_record['page']}")
            print(f"      Text (first 100 chars): {first_record['text'][:100]}...")

            if first_record['page'] == 7:
                print(f"\n   ✅ SUCCESS! Extraction started from page 7 (keyword found)")
            else:
                print(f"\n   ❌ FAILED! Extraction started from page {first_record['page']} (expected page 7)")
    else:
        print(f"\n❌ JSON file not found: {json_path}")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
