"""
Test the ACTUAL extract_text_from_single_pdf_v2 function from data_curation.py
"""
#%%
import sys
import os

# Set UTF-8 encoding
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Import the actual function
sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")
from data_curation import extract_text_from_single_pdf_v2

# Test file - MMM PDF that previously failed keyword detection
test_file = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\CF-Informe-MMM2124-cNotaAclaratoria-28-de-agosto-VF-publicada.pdf"

print("\n" + "="*100)
print("TESTING FIXED KEYWORD DETECTION: MMM PDF")
print("="*100)
print(f"\nFile: {os.path.basename(test_file)}")
print("Expected: Should find 'Opinión del CF sobre...' on page 7 and start extraction there")
print("Issue: PDF lacks font metadata → Fixed by using position-based filtering")
print("\n" + "="*100 + "\n")

try:
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
    print("\n✅ Function completed successfully")
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
