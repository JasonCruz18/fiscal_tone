import json

# Load cleaned data
with open('data/raw/scanned_pdfs_clean_extracted_text.json', 'r', encoding='utf-8') as f:
    clean = json.load(f)

print("="*80)
print("VERIFICATION OF FINAL CLEANING")
print("="*80)

# Test cases from user
cases = [
    ('Informe_CF_N_006-2016.pdf', 4, 'Opinión de CF sobre las proyecciones'),
    ('Informe_CF_N_007-2016.pdf', 3, 'Opinión de CF sobre el proyecto'),
    ('Informe_CF_N_008-2016.pdf', 5, 'Opinión del CF sobre el nuevo Marco'),
    ('INFORME_N_001-2017-CF.pdf', 2, 'Opinión del Consejo Fiscal'),
]

for pdf_name, expected_page, expected_keyword in cases:
    print(f"\n{'-'*80}")
    print(f"PDF: {pdf_name}")
    print(f"Expected: Start from page {expected_page} with '{expected_keyword}'")
    print('-'*80)

    pages = [p for p in clean if p['pdf_filename'] == pdf_name]

    if not pages:
        print("[FAIL] PDF not found in clean data")
        continue

    # Sort by page
    pages = sorted(pages, key=lambda x: x['page'])

    # Check first page
    first = pages[0]
    print(f"Actual first page: {first['page']}")

    # Check if text starts with keyword
    text = first['text']
    has_keyword = expected_keyword in text[:200]

    if first['page'] == expected_page and has_keyword:
        print(f"[OK] Starts from correct page {expected_page}")
        print(f"[OK] Contains keyword '{expected_keyword}'")
        print(f"\nFirst 300 chars:")
        print(f"  {text[:300]}...")
    else:
        print(f"[FAIL] Problem detected:")
        if first['page'] != expected_page:
            print(f"  - Wrong start page: got {first['page']}, expected {expected_page}")
        if not has_keyword:
            print(f"  - Keyword not found in first 200 chars")
        print(f"\nActual first 300 chars:")
        print(f"  {text[:300]}...")

# Check for false paragraph breaks
print(f"\n{'='*80}")
print("FALSE PARAGRAPH BREAKS CHECK")
print('='*80)

false_breaks = 0
for entry in clean:
    import re
    matches = re.findall(r'\n\n([a-záéíóúñü])', entry['text'])
    if matches:
        false_breaks += len(matches)
        print(f"[WARN] {entry['pdf_filename']} p{entry['page']}: {len(matches)} breaks before lowercase")

if false_breaks == 0:
    print("[OK] No false paragraph breaks before lowercase found")
else:
    print(f"\n[WARN] Total: {false_breaks} false breaks remaining")

print(f"\n{'='*80}")
print(f"SUMMARY")
print('='*80)
print(f"Total pages in clean data: {len(clean)}")
print(f"Total characters: {sum(len(e['text']) for e in clean):,}")
print(f"PDFs processed: {len(set(e['pdf_filename'] for e in clean))}")
print('='*80)
