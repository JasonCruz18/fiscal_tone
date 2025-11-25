"""
Fresh batch extraction test - forces module reload
"""
import sys
import os

# FORCE MODULE RELOAD - clear cached imports
if 'data_curation' in sys.modules:
    del sys.modules['data_curation']
    print("Cleared cached data_curation module")

sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

import builtins
builtins.input = lambda *args: "."

# Import fresh version
from data_curation import extract_text_from_editable_pdfs
print("Imported fresh data_curation module\n")

# Create temp test folder with just Comunicado
import shutil
test_folder = "data/raw/test_comunicado_only"
os.makedirs(test_folder, exist_ok=True)

src = "data/raw/editable/Comunicado042024-VF.pdf"
dst = f"{test_folder}/Comunicado042024-VF.pdf"
if os.path.exists(src):
    shutil.copy2(src, dst)
    print(f"Copied Comunicado042024-VF.pdf to test folder\n")

# Run batch extraction
print("="*80)
print("BATCH EXTRACTION TEST - Comunicado042024-VF")
print("="*80)
print()

extract_text_from_editable_pdfs(
    editable_folder=test_folder,
    output_folder="data/raw",
    output_filename="test_comunicado_batch.json",
    search_opinion_keyword=True
)

# Verify output
output_file = "data/raw/test_comunicado_batch.json"
if os.path.exists(output_file):
    import json
    with open(output_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("\n" + "="*80)
    print("VERIFICATION")
    print("="*80)

    # Filter for Comunicado
    comunicado_records = [r for r in data if "Comunicado042024-VF" in r['pdf_filename']]
    pages = [r['page'] for r in comunicado_records]

    print(f"Comunicado042024-VF pages: {pages}")

    if pages == [1, 2, 3, 4, 5]:
        print("\nRESULT: CORRECT - Extracted pages 1-5")
        print("The case-sensitive fix IS working in batch mode!")
    elif pages == [4, 5]:
        print("\nRESULT: INCORRECT - Only pages 4-5")
        print("ERROR: Case-sensitive fix NOT working in batch mode!")
        print("This suggests the module wasn't reloaded properly.")
    else:
        print(f"\nRESULT: UNEXPECTED - Got pages {pages}")

# Cleanup
shutil.rmtree(test_folder)
print(f"\nCleaned up test folder")
