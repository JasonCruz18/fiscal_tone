"""
Analyze text cleaning patterns in scanned PDFs extracted text

This script identifies patterns that need to be cleaned before paragraph segmentation.
"""
import json
import re
from collections import Counter, defaultdict
import sys

# Redirect output to file with UTF-8 encoding
output_file = open('pattern_analysis.txt', 'w', encoding='utf-8')
sys.stdout = output_file

# Load the JSON file
with open('data/raw/scanned_pdfs_extracted_text.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 80)
print("TEXT CLEANING PATTERN ANALYSIS")
print("=" * 80)
print(f"Total records: {len(data)}")
print()

# ============================================================================
# PATTERN 1: Trailing/Extra Spaces
# ============================================================================
print("-" * 80)
print("PATTERN 1: Trailing/Extra Spaces")
print("-" * 80)

trailing_spaces = 0
multiple_spaces = 0
for record in data:
    text = record['text']
    if text.endswith(' '):
        trailing_spaces += 1
    if '  ' in text:  # Multiple consecutive spaces
        multiple_spaces += 1

print(f"Records with trailing spaces: {trailing_spaces}/{len(data)} ({trailing_spaces/len(data)*100:.1f}%)")
print(f"Records with multiple consecutive spaces: {multiple_spaces}/{len(data)} ({multiple_spaces/len(data)*100:.1f}%)")
print()

# ============================================================================
# PATTERN 2: Rare Symbols and Characters
# ============================================================================
print("-" * 80)
print("PATTERN 2: Rare Symbols and Characters")
print("-" * 80)

symbol_counts = Counter()
rare_symbols = ['➢', 'Ø', '•', '►', '✓', '■', '□', '◼', '○', '●', '▪', '▫', '…']

for record in data:
    text = record['text']
    for symbol in rare_symbols:
        if symbol in text:
            symbol_counts[symbol] += 1

print("Symbol frequencies:")
for symbol, count in symbol_counts.most_common():
    print(f"  '{symbol}': {count} records ({count/len(data)*100:.1f}%)")
print()

# ============================================================================
# PATTERN 3: Enumeration Patterns (a), b), A), B), i), ii), 1), 2)
# ============================================================================
print("-" * 80)
print("PATTERN 3: Enumeration Patterns")
print("-" * 80)

enum_pattern = r'\b([a-z]|[A-Z]|[ivxIVX]+|\d+)\)\s'
enum_matches = 0
enum_examples = []

for record in data[:50]:  # Sample first 50 records
    text = record['text']
    matches = re.findall(enum_pattern, text)
    if matches:
        enum_matches += 1
        # Get context around first match
        match_obj = re.search(enum_pattern, text)
        if match_obj:
            start = max(0, match_obj.start() - 30)
            end = min(len(text), match_obj.end() + 50)
            context = text[start:end].replace('\n', '\\n')
            if len(enum_examples) < 5:
                enum_examples.append(f"  ...{context}...")

print(f"Records with enumeration patterns (sample of 50): {enum_matches}/50")
print("Examples:")
for example in enum_examples:
    print(example)
print()

# ============================================================================
# PATTERN 4: Short Lines Without Ending Period
# ============================================================================
print("-" * 80)
print("PATTERN 4: Short Lines Without Ending Period")
print("-" * 80)

short_lines_no_period = []
short_threshold = 50  # characters

for record in data[:100]:  # Sample first 100
    text = record['text']
    lines = text.split('\n\n')
    for line in lines:
        line = line.strip()
        if 0 < len(line) < short_threshold and not line.endswith('.') and not line.endswith(':'):
            if len(short_lines_no_period) < 10:
                short_lines_no_period.append(f"  [{len(line)} chars] {line[:80]}")

print(f"Examples of short lines without ending period (< {short_threshold} chars):")
for example in short_lines_no_period:
    print(example)
print()

# ============================================================================
# PATTERN 5: All-Uppercase Lines (Names, Signatures)
# ============================================================================
print("-" * 80)
print("PATTERN 5: All-Uppercase Lines (Names, Signatures)")
print("-" * 80)

uppercase_lines = []

for record in data[:100]:  # Sample
    text = record['text']
    lines = text.split('\n\n')
    for line in lines:
        line = line.strip()
        # Check if line has at least 3 words and all are uppercase
        words = line.split()
        if len(words) >= 3:
            # Check if all words are uppercase (excluding punctuation)
            alpha_words = [w.strip('.,;:()[]') for w in words if w.strip('.,;:()[]').isalpha()]
            if alpha_words and all(w.isupper() for w in alpha_words):
                if len(uppercase_lines) < 10:
                    uppercase_lines.append(f"  {line[:100]}")

print("Examples of all-uppercase lines:")
for example in uppercase_lines:
    print(example)
print()

# ============================================================================
# PATTERN 6: Date Patterns
# ============================================================================
print("-" * 80)
print("PATTERN 6: Date Patterns")
print("-" * 80)

# Pattern: Lima, DD de MES de YYYY
date_pattern = r'Lima,?\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}'
date_matches = []

for record in data[:100]:
    text = record['text']
    matches = re.findall(date_pattern, text, re.IGNORECASE)
    for match in matches:
        if len(date_matches) < 10:
            date_matches.append(f"  {match}")

print("Examples of date patterns:")
for example in date_matches:
    print(example)
print()

# ============================================================================
# PATTERN 7: Graph/Table Titles
# ============================================================================
print("-" * 80)
print("PATTERN 7: Graph/Table Titles")
print("-" * 80)

graph_table_pattern = r'(Gráfico|Tabla|Cuadro|Figura)\s+N?°?\s*\d+'
graph_table_matches = []

for record in data[:100]:
    text = record['text']
    matches = re.findall(graph_table_pattern, text, re.IGNORECASE)
    for match in matches:
        # Get context
        match_obj = re.search(re.escape(match), text, re.IGNORECASE)
        if match_obj:
            start = match_obj.start()
            end = min(len(text), start + 100)
            context = text[start:end].replace('\n', '\\n')
            if len(graph_table_matches) < 10:
                graph_table_matches.append(f"  {context}")

print("Examples of graph/table titles:")
for example in graph_table_matches:
    print(example)
print()

# ============================================================================
# PATTERN 8: Chart Labels (A), B), (A, (B, etc.
# ============================================================================
print("-" * 80)
print("PATTERN 8: Chart Labels")
print("-" * 80)

chart_label_pattern = r'\([A-Z]\)\s+[A-Z]'
chart_label_matches = []

for record in data[:100]:
    text = record['text']
    matches = re.findall(chart_label_pattern, text)
    for match in matches:
        # Get context
        match_obj = re.search(re.escape(match), text)
        if match_obj:
            start = max(0, match_obj.start() - 20)
            end = min(len(text), match_obj.end() + 60)
            context = text[start:end].replace('\n', '\\n')
            if len(chart_label_matches) < 10:
                chart_label_matches.append(f"  ...{context}...")

print("Examples of chart labels:")
for example in chart_label_matches:
    print(example)
print()

# ============================================================================
# PATTERN 9: Dotted Lines (Signature Lines)
# ============================================================================
print("-" * 80)
print("PATTERN 9: Dotted Lines (Signature Lines)")
print("-" * 80)

dotted_pattern = r'\.{5,}|…{3,}'
dotted_matches = 0
dotted_examples = []

for record in data[:100]:
    text = record['text']
    if re.search(dotted_pattern, text):
        dotted_matches += 1
        match_obj = re.search(dotted_pattern, text)
        if match_obj and len(dotted_examples) < 5:
            start = max(0, match_obj.start() - 20)
            end = min(len(text), match_obj.end() + 40)
            context = text[start:end].replace('\n', '\\n')
            dotted_examples.append(f"  ...{context}...")

print(f"Records with dotted lines (sample of 100): {dotted_matches}/100")
print("Examples:")
for example in dotted_examples:
    print(example)
print()

# ============================================================================
# SUMMARY STATISTICS
# ============================================================================
print("=" * 80)
print("SUMMARY: Words per Record")
print("=" * 80)

word_counts = [len(r['text'].split()) for r in data]
avg_words = sum(word_counts) / len(word_counts)
min_words = min(word_counts)
max_words = max(word_counts)

print(f"Average words per record: {avg_words:.1f}")
print(f"Min words: {min_words}")
print(f"Max words: {max_words}")
print()

# Very short records (potential noise)
very_short = [r for r in data if len(r['text'].split()) < 20]
print(f"Very short records (< 20 words): {len(very_short)}")
if very_short:
    print("Examples:")
    for r in very_short[:5]:
        print(f"  [{r['pdf_filename']}, page {r['page']}] {r['text'][:100]}")

# Close output file
output_file.close()
print("Analysis complete! Results saved to pattern_analysis.txt", file=sys.__stdout__)
