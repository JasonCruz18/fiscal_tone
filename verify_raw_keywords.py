import json

# Load raw data
with open('data/raw/scanned_pdfs_extracted_text.json', 'r', encoding='utf-8') as f:
    raw = json.load(f)

# Test cases from user
cases = [
    ('Informe_CF_N_006-2016.pdf', 4),
    ('Informe_CF_N_007-2016.pdf', 3),
    ('Informe_CF_N_008-2016.pdf', 5),
    ('INFORME_N_001-2017-CF.pdf', 2)
]

for pdf_name, expected_page in cases:
    print('='*80)
    print(f'{pdf_name} - Keyword should be on page {expected_page}')
    print('='*80)

    pages = [p for p in raw if p['pdf_filename'] == pdf_name]

    # Show all pages
    for page in pages:
        print(f"\nPage {page['page']}:")
        text = page['text']

        # Check for keyword patterns
        if 'Opinión del CF' in text or 'Opinión del Consejo Fiscal' in text or 'Opinión de CF' in text:
            # Find position
            idx = max(text.find('Opinión del CF'), text.find('Opinión del Consejo Fiscal'), text.find('Opinión de CF'))
            if idx >= 0:
                print(f"  [KEYWORD FOUND] at position {idx}")
                # Show context
                start = max(0, idx - 50)
                end = min(len(text), idx + 200)
                print(f"  Context: ...{text[start:end]}...")
        else:
            print(f"  No keyword found")
            # Show first 200 chars
            print(f"  Start: {text[:200]}...")

    print()
