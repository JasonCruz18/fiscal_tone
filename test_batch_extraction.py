"""
Test batch extraction from all editable PDFs

This script demonstrates how to use extract_text_from_editable_pdfs()
to process all PDFs in data/raw/editable and save to a consolidated JSON.
"""
#%%
import sys
import os

sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

import builtins
builtins.input = lambda *args: "."

from data_curation import extract_text_from_editable_pdfs

# Run batch extraction with default parameters
print("Starting batch extraction from all editable PDFs...")
print()

extract_text_from_editable_pdfs(
    editable_folder="data/raw/editable",
    output_folder="data/raw",
    output_filename="scanned_pdfs_extracted_text.json",
    search_opinion_keyword=True  # Enable keyword-based filtering
)

print("TEST COMPLETE")
