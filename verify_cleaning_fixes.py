"""
Verify that all cleaning issues have been fixed
"""

import json
import re

# Load cleaned data
with open('data/raw/scanned_pdfs_clean_extracted_text.json', 'r', encoding='utf-8') as f:
    clean = json.load(f)

print("="*80)
print("VERIFICATION OF CLEANING FIXES")
print("="*80)

# Test 1: Keyword filtering - verify no text before "Opinión del CF"
print("\n1. KEYWORD FILTERING TEST")
print("-"*80)

test_pdfs = [
    'Informe_CF_N_006-2016.pdf',
    'Informe_CF_N_007-2016.pdf',
    'Informe_CF_N_008-2016.pdf',
    'INFORME_N_001-2017-CF.pdf'
]

for pdf_name in test_pdfs:
    pages = [p for p in clean if p['pdf_filename'] == pdf_name]
    if not pages:
        print(f"  [FAIL] {pdf_name}: NOT FOUND IN CLEAN DATA")
        continue

    # Check first page
    first_page = pages[0]
    text = first_page['text']

    # Check that text starts with opinion keyword
    opinion_patterns = [
        r'^\s*(?:(?:\d+|[IVX]+)\.?\s*[—\-]?\s*)?Opinión del? Consejo Fiscal',
        r'^\s*(?:(?:\d+|[IVX]+)\.?\s*[—\-]?\s*)?Opinión del? CF'
    ]

    starts_with_opinion = any(re.search(pattern, text) for pattern in opinion_patterns)

    if starts_with_opinion:
        print(f"  [OK] {pdf_name}: First page starts with opinion keyword")
        print(f"    First 100 chars: {text[:100]}...")
    else:
        print(f"  [FAIL] {pdf_name}: PROBLEM - doesn't start with opinion keyword")
        print(f"    First 200 chars: {text[:200]}...")

# Test 2: False paragraph breaks before lowercase
print("\n2. FALSE PARAGRAPH BREAKS (before lowercase)")
print("-"*80)

false_breaks_lowercase = 0
for entry in clean:
    text = entry['text']
    # Check for \n\n followed by lowercase
    matches = re.findall(r'\n\n([a-záéíóúñü])', text)
    if matches:
        false_breaks_lowercase += len(matches)
        print(f"  [FAIL] {entry['pdf_filename']} p{entry['page']}: Found {len(matches)} breaks before lowercase")
        for match in matches[:3]:  # Show first 3
            idx = text.find(f'\n\n{match}')
            context = text[max(0, idx-30):min(len(text), idx+50)]
            print(f"    Context: ...{context}...")

if false_breaks_lowercase == 0:
    print("  [OK] No false paragraph breaks before lowercase found")

# Test 3: False paragraph breaks before years
print("\n3. FALSE PARAGRAPH BREAKS (before years)")
print("-"*80)

false_breaks_years = 0
for entry in clean:
    text = entry['text']
    # Check for \n\n followed by 4-digit year
    matches = re.findall(r'\n\n([12]\d{3})', text)
    if matches:
        false_breaks_years += len(matches)
        print(f"  [FAIL] {entry['pdf_filename']} p{entry['page']}: Found {len(matches)} breaks before years")
        for match in matches[:3]:  # Show first 3
            idx = text.find(f'\n\n{match}')
            context = text[max(0, idx-30):min(len(text), idx+50)]
            print(f"    Context: ...{context}...")

if false_breaks_years == 0:
    print("  [OK] No false paragraph breaks before years found")

# Test 4: Extra spaces before special characters
print("\n4. EXTRA SPACES BEFORE SPECIAL CHARS")
print("-"*80)

space_patterns = [
    (r' <', '  space before <'),
    (r' ;', '  space before ;'),
    (r' :', '  space before :'),
    (r' \?', '  space before ?'),
    (r' !', '  space before !'),
]

total_space_issues = 0
for pattern, desc in space_patterns:
    count = 0
    for entry in clean:
        text = entry['text']
        matches = re.findall(pattern, text)
        if matches:
            count += len(matches)
            if count <= 3:  # Show first 3 examples
                for match in matches[:1]:
                    idx = text.find(match)
                    context = text[max(0, idx-20):min(len(text), idx+30)]
                    print(f"  [FAIL] {entry['pdf_filename']} p{entry['page']}: {desc}")
                    print(f"    Context: ...{context}...")
    total_space_issues += count

if total_space_issues == 0:
    print("  [OK] No extra spaces before special characters found")

# Test 5: Short headers not removed (surrounded by \n\n)
print("\n5. SHORT HEADERS (should be removed)")
print("-"*80)

headers_remaining = 0
for entry in clean:
    text = entry['text']
    # Find text between \n\n that is short (<120 chars)
    matches = re.findall(r'\n\n(.{1,120}?)\n\n', text, re.DOTALL)
    if matches:
        for match in matches:
            # Only report if it looks like a header (no paragraph-like content)
            if len(match) < 120 and '\n' not in match:  # Single line, short
                headers_remaining += 1
                if headers_remaining <= 5:  # Show first 5
                    print(f"  [WARN] {entry['pdf_filename']} p{entry['page']}: Possible header ({len(match)} chars)")
                    print(f"    Text: '{match[:80]}...'")

if headers_remaining == 0:
    print("  [OK] No obvious short headers found")
else:
    print(f"  Note: {headers_remaining} potential headers found (may be legitimate short paragraphs)")

# Test 6: Specific problematic PDF - Informe_CF_N_004-2016.pdf page 1
print("\n6. SPECIFIC PROBLEMATIC PDF: Informe_CF_N_004-2016.pdf")
print("-"*80)

target = 'Informe_CF_N_004-2016.pdf'
pages = [p for p in clean if p['pdf_filename'] == target]
if pages:
    first_page = pages[0]
    text = first_page['text']

    print(f"  Total pages for {target}: {len(pages)}")
    print(f"  First page number: {first_page['page']}")
    print(f"  First 500 chars:")
    print(f"  {text[:500]}")

    # Count paragraph breaks
    para_count = text.count('\n\n')
    print(f"\n  Paragraph breaks (\n\n): {para_count}")

    # Check for false positives
    false_lower = len(re.findall(r'\n\n([a-záéíóúñü])', text))
    false_years = len(re.findall(r'\n\n([12]\d{3})', text))
    print(f"  False breaks (lowercase): {false_lower}")
    print(f"  False breaks (years): {false_years}")
else:
    print(f"  [FAIL] {target} not found in clean data")

# Summary
print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Total pages in clean data: {len(clean)}")
print(f"Total characters: {sum(len(e['text']) for e in clean):,}")
print(f"\nIssues found:")
print(f"  - False breaks (lowercase): {false_breaks_lowercase}")
print(f"  - False breaks (years): {false_breaks_years}")
print(f"  - Extra spaces: {total_space_issues}")
print(f"  - Potential headers: {headers_remaining}")
print("="*80 + "\n")
