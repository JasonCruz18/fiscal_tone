"""
Final Paragraph Cleaning - Remove Segmentation Artifacts

Filters out problematic paragraphs that result from page-break splitting:
- Paragraphs starting with lowercase (mid-sentence fragments)
- Paragraphs not ending with proper punctuation (truncated)
- Very short paragraphs (< 100 chars after normalization)
- Single character or symbol-only paragraphs

Author: Claude Code
Date: 2025-01-28
"""

import json
import re
from pathlib import Path

print("="*80)
print(" FINAL PARAGRAPH CLEANING ".center(80, "="))
print("="*80)

# Load normalized paragraphs
input_file = "metadata/cf_normalized_paragraphs.json"
output_file = "metadata/cf_normalized_paragraphs_cleaned.json"

print(f"\n[LOADING] Reading: {input_file}")

with open(input_file, 'r', encoding='utf-8') as f:
    paragraphs = json.load(f)

print(f"[OK] Loaded {len(paragraphs):,} paragraphs")

# ============================================================================
# CLEANING CRITERIA
# ============================================================================

def is_valid_paragraph(para):
    """
    Check if paragraph meets quality criteria.

    Returns:
        (bool, str): (is_valid, reason_for_rejection)
    """
    text = para['text'].strip()

    # 1. Minimum length (100 chars minimum for substantive content)
    if len(text) < 100:
        return False, f"too_short ({len(text)} chars)"

    # 2. Must start with capital letter or number
    if text and not (text[0].isupper() or text[0].isdigit()):
        return False, "starts_lowercase"

    # 3. Must end with proper sentence-ending punctuation
    # Valid endings: . ! ? ) ] " (for quotes/citations)
    valid_endings = ['.', '!', '?', ')', ']', '"', '%', ':']
    if not any(text.endswith(ending) for ending in valid_endings):
        return False, "no_ending_punctuation"

    # 4. Not just symbols or numbers
    # Must contain at least some alphabetic characters (at least 50% of text)
    alpha_chars = sum(c.isalpha() for c in text)
    if alpha_chars < len(text) * 0.5:
        return False, "insufficient_text_content"

    # 5. Not a single character or symbol
    if len(text) <= 2:
        return False, "single_character"

    # 6. Not just a list marker or bullet
    if re.match(r'^[•\-\*\d]+\.?\s*$', text):
        return False, "just_list_marker"

    return True, "valid"


# ============================================================================
# APPLY FILTERING
# ============================================================================

print("\n[PROCESSING] Applying cleaning filters...")

valid_paragraphs = []
rejected_paragraphs = []
rejection_reasons = {}

for para in paragraphs:
    is_valid, reason = is_valid_paragraph(para)

    if is_valid:
        valid_paragraphs.append(para)
    else:
        rejected_paragraphs.append(para)
        rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1

# ============================================================================
# RENUMBER PARAGRAPHS
# ============================================================================

print("\n[PROCESSING] Renumbering valid paragraphs...")

for idx, para in enumerate(valid_paragraphs, start=1):
    para['paragraph_num'] = idx

# ============================================================================
# SAVE RESULTS
# ============================================================================

print("\n[SAVING] Writing cleaned data...")

with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(valid_paragraphs, f, ensure_ascii=False, indent=2)

# Save rejected paragraphs for inspection
rejected_file = "metadata/cf_rejected_paragraphs.json"
with open(rejected_file, 'w', encoding='utf-8') as f:
    json.dump(rejected_paragraphs, f, ensure_ascii=False, indent=2)

# ============================================================================
# REPORT
# ============================================================================

print("\n" + "="*80)
print("CLEANING REPORT")
print("="*80)

print(f"\nInput:     {len(paragraphs):,} paragraphs")
print(f"Valid:     {len(valid_paragraphs):,} paragraphs ({len(valid_paragraphs) / len(paragraphs) * 100:.1f}%)")
print(f"Rejected:  {len(rejected_paragraphs):,} paragraphs ({len(rejected_paragraphs) / len(paragraphs) * 100:.1f}%)")

print(f"\nRejection reasons:")
for reason, count in sorted(rejection_reasons.items(), key=lambda x: x[1], reverse=True):
    pct = count / len(rejected_paragraphs) * 100
    print(f"  - {reason:<30} {count:>4,} ({pct:>5.1f}%)")

# Show examples of rejected paragraphs
print(f"\nExamples of rejected paragraphs:")
print("-"*80)

for reason in list(rejection_reasons.keys())[:3]:
    examples = [p for p in rejected_paragraphs if is_valid_paragraph(p)[1] == reason]
    if examples:
        example = examples[0]
        print(f"\nReason: {reason}")
        print(f"  Document: {example['pdf_filename']}")
        print(f"  Length: {example['length']} chars")
        print(f"  Text: {example['text'][:100]}...")

# Statistics on valid paragraphs
print("\n" + "="*80)
print("VALID PARAGRAPHS STATISTICS")
print("="*80)

lengths = [p['length'] for p in valid_paragraphs]
print(f"\nLength distribution:")
print(f"  Mean:   {sum(lengths) / len(lengths):.0f} chars")
print(f"  Median: {sorted(lengths)[len(lengths)//2]:.0f} chars")
print(f"  Min:    {min(lengths):.0f} chars")
print(f"  Max:    {max(lengths):.0f} chars")

# Documents represented
docs = set(p['pdf_filename'] for p in valid_paragraphs)
print(f"\nDocuments:")
print(f"  Total unique documents: {len(docs)}")

# Source types
source_types = {}
for p in valid_paragraphs:
    st = p.get('source_type', 'unknown')
    source_types[st] = source_types.get(st, 0) + 1

print(f"\nSource types:")
for st, count in sorted(source_types.items(), key=lambda x: x[1], reverse=True):
    pct = count / len(valid_paragraphs) * 100
    print(f"  - {st}: {count:,} ({pct:.1f}%)")

print("\n" + "="*80)
print("OUTPUT FILES")
print("="*80)
print(f"\n[SAVED] Cleaned paragraphs: {output_file}")
print(f"        ({len(valid_paragraphs):,} paragraphs, {Path(output_file).stat().st_size / 1024 / 1024:.2f} MB)")
print(f"\n[SAVED] Rejected paragraphs: {rejected_file}")
print(f"        ({len(rejected_paragraphs):,} paragraphs, {Path(rejected_file).stat().st_size / 1024 / 1024:.2f} MB)")
print("\n" + "="*80)
print("[SUCCESS] Data is ready for LLM classification with context!")
print("="*80)
