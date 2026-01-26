"""
Export all stage6 removals to a JSON file for manual review
"""
import json
import re
from pathlib import Path
from collections import defaultdict

print("\n" + "="*80)
print("EXPORTING STAGE6 REMOVALS TO JSON")
print("="*80)

# Load raw scanned text
input_file = Path('data/raw/scanned_pdfs_extracted_text.json')
with open(input_file, 'r', encoding='utf-8') as f:
    raw_data = json.load(f)

# Collect all removals
removals = []
removal_id = 1

for entry in raw_data:
    text = entry['text']
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

    for para in paragraphs:
        should_remove = False
        reason = ""
        matched_pattern = ""

        # ULTRA CONSERVATIVE rules (same as in clean_scanned_text.py)
        if len(para) < 80:
            removal_patterns = [
                (r'^\d+\s*/\s*\d+$', 'page_number', 'Page number'),
                (r'^Lima,\s+\d+\s+de\s+\w+\s+de\s+\d{4}[\s.]*$', 'date', 'Date'),
                (r'^Informe\s+N[*°º]?\s*\d{3,4}[-\s]*CF[\s.]*$', 'doc_id', 'Document ID'),
                (r'^PRESIDENTE\s+DEL\s+CONSEJO\s+FISCAL[\s.]*$', 'signature', 'Signature line'),
                (r'^Conclusiones?\s*:?[\s.]*$', 'section_header', 'Section header'),
                (r'^ANEXO\s*:?[\s.]*$', 'annex_header', 'Annex header'),
            ]

            for pattern, category, desc in removal_patterns:
                if re.search(pattern, para, re.IGNORECASE):
                    should_remove = True
                    reason = category
                    matched_pattern = pattern
                    break

        # Extremely short
        if len(para) < 30 and not should_remove:
            should_remove = True
            reason = 'too_short'
            matched_pattern = f'Length < 30 chars'

        # All-caps signatures
        if len(para) < 70 and not should_remove:
            alpha = [c for c in para if c.isalpha()]
            if alpha and len(alpha) > 10:
                caps_ratio = sum(1 for c in alpha if c.isupper()) / len(alpha)
                if caps_ratio > 0.6 and 'presidente' in para.lower():
                    should_remove = True
                    reason = 'signature_caps'
                    matched_pattern = f'{caps_ratio:.0%} uppercase + "presidente"'

        if should_remove:
            removals.append({
                'id': removal_id,
                'pdf_filename': entry['pdf_filename'],
                'page': entry['page'],
                'text': para,
                'length': len(para),
                'reason': reason,
                'matched_pattern': matched_pattern,
                'char_count': len(para),
                'word_count': len(para.split())
            })
            removal_id += 1

# Save to JSON
output_file = Path('metadata/stage6_removals.json')
output_file.parent.mkdir(parents=True, exist_ok=True)

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(removals, f, ensure_ascii=False, indent=2)

# Also create a summary
summary = {
    'total_removals': len(removals),
    'total_chars_removed': sum(r['char_count'] for r in removals),
    'by_reason': {},
    'by_pdf': {},
    'longest_removed': max(removals, key=lambda x: x['length']) if removals else None,
    'generation_date': '2025-12-02'
}

# Group by reason
by_reason = defaultdict(lambda: {'count': 0, 'chars': 0, 'examples': []})
for r in removals:
    by_reason[r['reason']]['count'] += 1
    by_reason[r['reason']]['chars'] += r['char_count']
    if len(by_reason[r['reason']]['examples']) < 5:
        by_reason[r['reason']]['examples'].append({
            'text': r['text'],
            'pdf': r['pdf_filename'],
            'page': r['page']
        })

summary['by_reason'] = dict(by_reason)

# Group by PDF
by_pdf = defaultdict(lambda: {'count': 0, 'chars': 0})
for r in removals:
    by_pdf[r['pdf_filename']]['count'] += 1
    by_pdf[r['pdf_filename']]['chars'] += r['char_count']

summary['by_pdf'] = dict(by_pdf)

# Save summary
summary_file = Path('metadata/stage6_removals_summary.json')
with open(summary_file, 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)

# Print results
print(f"\n[SAVED] Full removals list: {output_file}")
print(f"  Total removals: {len(removals)}")
print(f"  Total characters: {sum(r['char_count'] for r in removals):,}")

print(f"\n[SAVED] Summary: {summary_file}")

print("\n" + "-"*80)
print("SUMMARY BY REASON:")
print("-"*80)
for reason, data in sorted(by_reason.items(), key=lambda x: -x[1]['count']):
    print(f"\n{reason}: {data['count']} removals ({data['chars']} chars)")
    print("  Examples:")
    for i, ex in enumerate(data['examples'], 1):
        print(f"    {i}. \"{ex['text'][:60]}...\" ({ex['pdf']}, p.{ex['page']})")

print("\n" + "-"*80)
print("SUMMARY BY PDF:")
print("-"*80)
for pdf, data in sorted(by_pdf.items(), key=lambda x: -x[1]['count'])[:10]:
    print(f"  {pdf}: {data['count']} removals ({data['chars']} chars)")

print("\n" + "="*80)
print("EXPORT COMPLETE")
print("="*80)
print(f"\nYou can now review: {output_file}")
print("Each removal includes: id, pdf, page, text, length, reason, pattern")
print("\nIf you find ANY valid content being removed, please report it!")
print("="*80 + "\n")
