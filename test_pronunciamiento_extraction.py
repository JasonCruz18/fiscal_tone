"""
Test extraction on problematic Pronunciamiento PDFs
"""
import sys
import os

# Set up path
sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

# Mock the input prompt
import builtins
builtins.input = lambda *args: "."

# Import extraction function
from data_curation import extract_text_from_single_pdf_v2

# Test one problematic PDF
test_file = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Pronunciamiento-DCRF-2020-publicar.pdf"

# Delete old JSON
json_file = test_file.replace('.pdf', '_v2.json')
if os.path.exists(json_file):
    os.remove(json_file)
    print(f"Deleted old JSON\n")

print("="*80)
print("TESTING: Pronunciamiento-DCRF-2020-publicar.pdf")
print("Expected: Keyword on page 4, extract from page 4 onwards")
print("="*80)
print()

# Run extraction with ADJUSTED font range to include 10.98pt body text and 12.0-14.0pt headers
extract_text_from_single_pdf_v2(
    test_file,
    FONT_MIN=10.5,  # LOWERED from 11.0 to capture 10.98pt body text
    FONT_MAX=14.5,  # INCREASED from 11.9 to include up to 14.0pt section headers
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
print("CHECKING OUTPUT")
print("="*80)

# Check if JSON was created
if os.path.exists(json_file):
    import json
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if data:
        print(f"SUCCESS: Extracted {len(data)} pages")
        print(f"First page: {data[0]['page']}")
        print(f"Last page: {data[-1]['page']}")
        print(f"First text sample: {data[0]['text'][:150]}...")
    else:
        print("FAILED: JSON is empty")
else:
    print("FAILED: No JSON file created")
