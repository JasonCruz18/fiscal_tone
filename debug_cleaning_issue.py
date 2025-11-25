"""
Debug cleaning issue - trace which step is causing truncation
"""
import json
import re
import sys

# Mock input
import builtins
builtins.input = lambda *args: "."

if 'data_curation' in sys.modules:
    del sys.modules['data_curation']

from data_curation import (
    _remove_dotted_signatures,
    _remove_date_signature_blocks,
    _remove_uppercase_lines,
    _remove_section_headers,
    _remove_graph_table_titles,
    _remove_chart_labels,
    _replace_rare_symbols,
    _normalize_whitespace
)

# Load original data
with open('data/raw/all_extracted_text.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# Find the problematic record (2-ComunicadoCF-RetiroAFP-1.pdf, page 1)
record = next(r for r in data if r['pdf_filename'] == '2-ComunicadoCF-RetiroAFP-1.pdf' and r['page'] == 1)

text = record['text']

print("=" * 80)
print("DEBUGGING TEXT CLEANING - STEP BY STEP")
print("=" * 80)
print(f"PDF: {record['pdf_filename']}, Page: {record['page']}")
print(f"Original length: {len(text)}")
print()

print("=" * 80)
print("ORIGINAL TEXT (first 600 chars):")
print("=" * 80)
print(text[:600])
print()

# Step 1
text_step1 = _remove_dotted_signatures(text)
print("-" * 80)
print(f"STEP 1: Remove dotted signatures - Length: {len(text_step1)} (removed: {len(text) - len(text_step1)})")
print("-" * 80)
if len(text_step1) != len(text):
    print("CHANGED! First 600 chars:")
    print(text_step1[:600])
print()

# Step 2
text_step2 = _remove_date_signature_blocks(text_step1)
print("-" * 80)
print(f"STEP 2: Remove date + signature blocks - Length: {len(text_step2)} (removed: {len(text_step1) - len(text_step2)})")
print("-" * 80)
if len(text_step2) != len(text_step1):
    print("CHANGED! First 600 chars:")
    print(text_step2[:600])
print()

# Step 3
text_step3 = _remove_uppercase_lines(text_step2)
print("-" * 80)
print(f"STEP 3: Remove uppercase lines - Length: {len(text_step3)} (removed: {len(text_step2) - len(text_step3)})")
print("-" * 80)
if len(text_step3) != len(text_step2):
    print("CHANGED! First 600 chars:")
    print(text_step3[:600])
print()

# Step 4
text_step4 = _remove_section_headers(text_step3)
print("-" * 80)
print(f"STEP 4: Remove section headers - Length: {len(text_step4)} (removed: {len(text_step3) - len(text_step4)})")
print("-" * 80)
if len(text_step4) != len(text_step3):
    print("CHANGED! First 600 chars:")
    print(text_step4[:600])
    print()
    print("Last 600 chars:")
    print(text_step4[-600:])
print()

# Step 5
text_step5 = _remove_graph_table_titles(text_step4)
print("-" * 80)
print(f"STEP 5: Remove graph/table titles - Length: {len(text_step5)} (removed: {len(text_step4) - len(text_step5)})")
print("-" * 80)
if len(text_step5) != len(text_step4):
    print("CHANGED! First 600 chars:")
    print(text_step5[:600])
print()

# Step 6
text_step6 = _remove_chart_labels(text_step5)
print("-" * 80)
print(f"STEP 6: Remove chart labels - Length: {len(text_step6)} (removed: {len(text_step5) - len(text_step6)})")
print("-" * 80)
if len(text_step6) != len(text_step5):
    print("CHANGED! First 600 chars:")
    print(text_step6[:600])
print()

# Step 7
text_step7 = _replace_rare_symbols(text_step6)
print("-" * 80)
print(f"STEP 7: Replace rare symbols - Length: {len(text_step7)} (removed: {len(text_step6) - len(text_step7)})")
print("-" * 80)
if len(text_step7) != len(text_step6):
    print("CHANGED! First 600 chars:")
    print(text_step7[:600])
print()

# Step 8
text_step8 = _normalize_whitespace(text_step7)
print("-" * 80)
print(f"STEP 8: Normalize whitespace - Length: {len(text_step8)} (removed: {len(text_step7) - len(text_step8)})")
print("-" * 80)
if len(text_step8) != len(text_step7):
    print("CHANGED! First 600 chars:")
    print(text_step8[:600])
print()

print("=" * 80)
print("FINAL TEXT (first 600 chars):")
print("=" * 80)
print(text_step8[:600])
print()
print("FINAL TEXT (last 200 chars):")
print(text_step8[-200:])
