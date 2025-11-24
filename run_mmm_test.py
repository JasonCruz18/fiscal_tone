"""
Simple test runner for MMM PDF - no complex imports
"""
#%%
import sys
import os

# Set up path
sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

# Mock the input prompt to avoid interactive input
import builtins
builtins.input = lambda *args: "."

# Now import (will run initialization with mocked input)
from data_curation import extract_text_from_single_pdf_v2

# Test file
test_file = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Pronunciamiento-DCRF-2020-publicar.pdf"

# Delete old JSON
json_file = test_file.replace('.pdf', '_v2.json')
if os.path.exists(json_file):
    os.remove(json_file)
    print(f"🗑️ Deleted old JSON: {os.path.basename(json_file)}\n")

print("="*80)
print("RUNNING EXTRACTION ON MMM PDF")
print("="*80)
print(f"File: {os.path.basename(test_file)}")
print("Watch for these lines:")
print("  1. '🔍 Searching for Opinión del keyword...'")
print("  2. '✓ Found keyword on page 7'")
print("  3. '🔍 DEBUG: Keyword search returned start_page=7'")
print("  4. '[SKIPPED] Page 1-6'")
print("="*80)
print()

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

print("\n" + "="*80)
print("CHECKING JSON OUTPUT")
print("="*80)

# Check JSON
if os.path.exists(json_file):
    import json
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"✅ JSON created: {len(data)} pages")
    print(f"\nFirst record:")
    print(f"  Page: {data[0]['page']}")
    print(f"  Text preview: {data[0]['text'][:100]}...")

    if data[0]['page'] == 7:
        print(f"\n✅✅✅ SUCCESS! Extraction started from page 7")
    else:
        print(f"\n❌❌❌ FAILED! Extraction started from page {data[0]['page']} (expected 7)")
else:
    print(f"❌ JSON not found")

# %%
