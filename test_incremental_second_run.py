"""
Test incremental extraction - Second run
This should skip all PDFs since they're already in the JSON
"""
import sys
import os

# Clear cached module
if 'data_curation' in sys.modules:
    del sys.modules['data_curation']

sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

import builtins
builtins.input = lambda *args: "."

from data_curation import extract_text_from_editable_pdfs_incremental

print("=" * 80)
print("TESTING INCREMENTAL EXTRACTION - SECOND RUN")
print("Expected: Should skip all PDFs (already extracted)")
print("=" * 80)
print()

# Run incremental extraction again
extract_text_from_editable_pdfs_incremental(
    editable_folder=r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable",
    output_folder=r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw",
    output_filename="all_extracted_text.json",
    search_opinion_keyword=True
)

print()
print("=" * 80)
print("SECOND RUN COMPLETE")
print("=" * 80)
