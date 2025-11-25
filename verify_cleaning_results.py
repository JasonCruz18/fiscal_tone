"""
Verify text cleaning results by comparing before/after examples
"""
import json
import sys

# Load original and cleaned data
with open('data/raw/all_extracted_text.json', 'r', encoding='utf-8') as f:
    original_data = json.load(f)

with open('data/raw/all_extracted_text_clean.json', 'r', encoding='utf-8') as f:
    cleaned_data = json.load(f)

print("=" * 80)
print("TEXT CLEANING VERIFICATION")
print("=" * 80)
print()

# Find records with significant cleaning (>10% reduction)
significant = [r for r in cleaned_data if r['reduction_pct'] > 10]

print(f"Found {len(significant)} records with >10% reduction")
print()

# Show top 3 examples
for i, cleaned_record in enumerate(significant[:3], 1):
    # Find matching original record
    original_record = next(
        (r for r in original_data
         if r['pdf_filename'] == cleaned_record['pdf_filename']
         and r['page'] == cleaned_record['page']),
        None
    )

    if not original_record:
        continue

    print("=" * 80)
    print(f"EXAMPLE {i}: {cleaned_record['pdf_filename']} - Page {cleaned_record['page']}")
    print("=" * 80)
    print(f"Reduction: {cleaned_record['reduction_pct']:.1f}%")
    print(f"Original length: {cleaned_record['original_length']} chars")
    print(f"Cleaned length: {cleaned_record['cleaned_length']} chars")
    print()

    print("-" * 80)
    print("ORIGINAL TEXT (first 500 chars):")
    print("-" * 80)
    print(original_record['text'][:500])
    print()

    print("-" * 80)
    print("CLEANED TEXT (first 500 chars):")
    print("-" * 80)
    print(cleaned_record['text'][:500])
    print()
    print()

# Show statistics summary
print("=" * 80)
print("SUMMARY STATISTICS")
print("=" * 80)
print()

reduction_ranges = {
    '0-1%': 0,
    '1-5%': 0,
    '5-10%': 0,
    '10-20%': 0,
    '>20%': 0
}

for r in cleaned_data:
    pct = r['reduction_pct']
    if pct < 1:
        reduction_ranges['0-1%'] += 1
    elif pct < 5:
        reduction_ranges['1-5%'] += 1
    elif pct < 10:
        reduction_ranges['5-10%'] += 1
    elif pct < 20:
        reduction_ranges['10-20%'] += 1
    else:
        reduction_ranges['>20%'] += 1

print("Reduction distribution:")
for range_name, count in reduction_ranges.items():
    pct = count / len(cleaned_data) * 100
    print(f"  {range_name}: {count} records ({pct:.1f}%)")
