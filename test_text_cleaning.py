"""
Test script for text cleaning pipeline

This script tests the cleaning functions on the editable PDFs extracted text.
"""
import sys

# Mock input() to avoid interactive prompts
import builtins
builtins.input = lambda *args: "."

# Clear module cache to ensure fresh import
if 'data_curation' in sys.modules:
    del sys.modules['data_curation']

from data_curation import clean_extracted_text_batch

# Test on editable PDFs extracted text
input_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\all_extracted_text.json"
output_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\all_extracted_text_clean.json"

print("Testing text cleaning pipeline...")
print()

# Run cleaning pipeline (conservative mode - no enumeration removal)
clean_extracted_text_batch(
    input_json_path=input_path,
    output_json_path=output_path,
    aggressive=False,
    verbose=True
)

print()
print("=" * 80)
print("TEST COMPLETE")
print("=" * 80)
print()
print("Next steps:")
print("1. Inspect the output file: all_extracted_text_clean.json")
print("2. Compare a few records before/after cleaning")
print("3. Verify statistics match expectations (~10-15% reduction)")
