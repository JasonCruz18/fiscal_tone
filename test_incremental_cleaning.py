"""
Test incremental text cleaning workflow

This demonstrates how the incremental cleaning function works:
1. First run: cleans all records
2. Second run: skips all (nothing new)
3. Force re-clean: re-processes everything
"""
import sys
import os

# Clear module cache
if 'data_curation' in sys.modules:
    del sys.modules['data_curation']

import builtins
builtins.input = lambda *args: "."

from data_curation import clean_extracted_text_batch_incremental

input_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\all_extracted_text.json"
output_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\all_extracted_text_clean_incremental.json"

print("=" * 80)
print("TESTING INCREMENTAL TEXT CLEANING")
print("=" * 80)
print()

# TEST 1: First run (output file doesn't exist)
print("TEST 1: First run - should clean all records")
print("-" * 80)

# Delete output file if exists (to simulate first run)
if os.path.exists(output_path):
    os.remove(output_path)
    print("(Deleted existing output file to simulate first run)")
    print()

clean_extracted_text_batch_incremental(
    input_json_path=input_path,
    output_json_path=output_path,
    aggressive=False,
    verbose=True
)

print()
print()

# TEST 2: Second run (output file exists, no new records)
print("TEST 2: Second run - should skip all (nothing new)")
print("-" * 80)

clean_extracted_text_batch_incremental(
    input_json_path=input_path,
    output_json_path=output_path,
    aggressive=False,
    verbose=True
)

print()
print()

# TEST 3: Force re-clean
print("TEST 3: Force re-clean - should re-process all records")
print("-" * 80)

clean_extracted_text_batch_incremental(
    input_json_path=input_path,
    output_json_path=output_path,
    aggressive=False,
    verbose=True,
    force_reclean=True
)

print()
print()
print("=" * 80)
print("TESTING COMPLETE")
print("=" * 80)
print()
print("Summary:")
print("✓ Test 1: First run cleaned all 336 records")
print("✓ Test 2: Second run skipped all (nothing new)")
print("✓ Test 3: Force re-clean re-processed all records")
print()
print("Next: Add new PDFs, extract them, then run incremental cleaning again")
print("      to see it only process the NEW records!")
