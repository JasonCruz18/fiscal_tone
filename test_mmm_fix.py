"""
Test the fix for MMM PDF keyword detection
"""
import sys
import codecs

# Fix UTF-8 encoding for Windows console
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Import the fixed function
from data_curation import extract_text_from_single_pdf_v2

# Test file
test_file = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\CF-Informe-MMM2124-cNotaAclaratoria-28-de-agosto-VF-publicada.pdf"

print("=" * 80)
print("TESTING FIX: MMM PDF Keyword Detection")
print("=" * 80)
print(f"\nFile: {test_file}")
print("Expected: Should find 'Opinión del CF' on page 7")
print("Expected: Should start extraction from page 7")
print("\n" + "=" * 80)
print("RUNNING EXTRACTION...\n")

# Run extraction with keyword search enabled
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
    search_opinion_keyword=True  # Enable keyword search
)

print("\n" + "=" * 80)
print("EXTRACTION COMPLETE")
print("=" * 80)
print("\n✓ Check the generated JSON file to verify:")
print("  1. Keyword was found on page 7")
print("  2. Extraction starts from page 7 (not page 1)")
print("  3. First JSON record has page: 7")
print("  4. First text contains: 'Opinión del CF sobre las proyecciones...'")
