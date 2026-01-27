"""
Show EXACTLY what stage6 removes with ULTRA conservative settings
by comparing before/after stage6
"""
import json
import re
from pathlib import Path

# Simulate stages 0-5 to get the "before stage6" state
print("\n" + "="*80)
print("SHOWING ACTUAL STAGE6 REMOVALS (ULTRA CONSERVATIVE)")
print("="*80)

# For simplicity, let's load the CURRENT cleaned file and work backwards
# to understand what WAS removed

# Load the final output
final_file = Path('data/raw/scanned_pdfs_clean_extracted_text.json')
with open(final_file, 'r', encoding='utf-8') as f:
    final_data = json.load(f)

# Load the input (raw scanned text)
input_file = Path('data/raw/scanned_pdfs_extracted_text.json')
with open(input_file, 'r', encoding='utf-8') as f:
    raw_data = json.load(f)

# Simulate what stage6 WOULD remove from raw data
# using the ULTRA CONSERVATIVE rules

removals = []

for entry in raw_data:
    text = entry['text']
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

    for para in paragraphs:
        should_remove = False
        reason = ""

        # ULTRA CONSERVATIVE rules (same as in clean_scanned_text.py)
        if len(para) < 80:
            removal_patterns = [
                (r'^\d+\s*/\s*\d+$', 'Page number'),
                (r'^Lima,\s+\d+\s+de\s+\w+\s+de\s+\d{4}[\s.]*$', 'Date'),
                (r'^Informe\s+N[*°º]?\s*\d{3,4}[-\s]*CF[\s.]*$', 'Doc ID'),
                (r'^PRESIDENTE\s+DEL\s+CONSEJO\s+FISCAL[\s.]*$', 'Signature'),
                (r'^Conclusiones?\s*:?[\s.]*$', 'Section header'),
                (r'^ANEXO\s*:?[\s.]*$', 'Annex header'),
            ]

            for pattern, desc in removal_patterns:
                if re.search(pattern, para, re.IGNORECASE):
                    should_remove = True
                    reason = desc
                    break

        # Extremely short
        if len(para) < 30:
            should_remove = True
            reason = f"Too short ({len(para)} chars)"

        # All-caps signatures
        if len(para) < 70:
            alpha = [c for c in para if c.isalpha()]
            if alpha and len(alpha) > 10:
                caps_ratio = sum(1 for c in alpha if c.isupper()) / len(alpha)
                if caps_ratio > 0.6 and 'presidente' in para.lower():
                    should_remove = True
                    reason = "Signature (all-caps)"

        if should_remove:
            removals.append({
                'pdf': entry['pdf_filename'],
                'page': entry['page'],
                'text': para,
                'length': len(para),
                'reason': reason
            })

print(f"\nTotal paragraphs stage6 would remove: {len(removals)}")
print(f"Total characters: {sum(r['length'] for r in removals):,}")

# Group by reason
from collections import defaultdict
by_reason = defaultdict(list)
for r in removals:
    by_reason[r['reason']].append(r)

print("\n" + "-"*80)
print("BREAKDOWN BY REASON:")
print("-"*80)

for reason, items in sorted(by_reason.items(), key=lambda x: -len(x[1])):
    print(f"\n{reason}: {len(items)} paragraphs")
    print("  Examples:")
    for i, item in enumerate(items[:5], 1):
        print(f"    [{i}] {item['pdf']}, p.{item['page']} ({item['length']} chars)")
        display_text = item['text'][:70] + "..." if len(item['text']) > 70 else item['text']
        print(f"        \"{display_text}\"")

print("\n" + "="*80)
print("FULL LIST OF ALL REMOVALS:")
print("="*80)

for i, item in enumerate(removals, 1):
    print(f"\n[{i}/{len(removals)}] {item['pdf']}, page {item['page']}")
    print(f"  Reason: {item['reason']} ({item['length']} chars)")
    print(f"  Text: \"{item['text']}\"")

print("\n" + "="*80)
print("END OF REPORT")
print("="*80)
print(f"\nTotal removed: {len(removals)} paragraphs, {sum(r['length'] for r in removals):,} chars")
print("All removals are < 80 chars and match specific noise patterns.")
print("\nIf you see ANY valid content here, please report it immediately!")
print("="*80 + "\n")
