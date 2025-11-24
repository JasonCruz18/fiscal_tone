"""
Test script for keyword detection and enhanced extraction v2
"""

import sys
import os
# Add parent directory to path to import from data_curation
sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Import necessary functions
from data_curation import extract_text_from_single_pdf_v2

# Test PDFs that should have keywords
test_pdfs = [
    ("CF-Informe-IAPM21-vF.pdf", "Should find keyword on page 2"),
    ("Informe-DCRF2024-vf.pdf", "Should find keyword on page 5"),
    ("Comunicado-Congreso-vf.pdf", "Should NOT find keyword (no opinion header)"),
]

base_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable"

for filename, description in test_pdfs:
    filepath = os.path.join(base_path, filename)

    if not os.path.exists(filepath):
        print(f"\n⚠️ Skipping {filename} (not found)")
        continue

    print("\n" + "="*100)
    print(f"Testing: {filename}")
    print(f"Expected: {description}")
    print("="*100)

    try:
        extract_text_from_single_pdf_v2(
            filepath,
            FONT_MIN=11.0,
            FONT_MAX=11.9,
            exclude_bold=False,
            vertical_threshold=15,
            first_page_header_cutoff=100,
            subsequent_header_cutoff=70,
            footer_cutoff_distance=100,
            last_page_footer_cutoff=120,
            search_opinion_keyword=True
        )
        print("\n✅ Extraction completed successfully")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*100)
    input("\nPress Enter to continue to next PDF...")

print("\n\n✅ All tests complete!")
