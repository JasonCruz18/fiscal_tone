import json

# Load data
with open('data/raw/scanned_pdfs_extracted_text.json', 'r', encoding='utf-8') as f:
    raw = json.load(f)

with open('data/raw/scanned_pdfs_clean_extracted_text.json', 'r', encoding='utf-8') as f:
    clean = json.load(f)

# Test cases from user
test_cases = [
    'Informe_CF_N_006-2016.pdf',
    'Informe_CF_N_007-2016.pdf',
    'Informe_CF_N_008-2016.pdf',
    'INFORME_N_001-2017-CF.pdf',
    'Informe_CF_N_004-2016.pdf'
]

for target in test_cases:
    print('='*80)
    print(f'INSPECTING: {target}')
    print('='*80)

    raw_pages = [p for p in raw if p['pdf_filename'] == target]
    clean_pages = [p for p in clean if p['pdf_filename'] == target]

    print(f'\nRAW: {len(raw_pages)} pages')
    print(f'CLEAN: {len(clean_pages)} pages')

    # Search for keyword patterns in raw
    print('\n--- Searching for KEYWORD patterns in RAW ---')
    for i, page in enumerate(raw_pages, 1):
        text = page['text']
        if 'Opinión del CF' in text or 'Opinión del Consejo Fiscal' in text or 'Opinión de CF' in text:
            print(f'[FOUND] Keyword pattern in RAW page {page["page"]}')
            # Find the exact position
            idx1 = text.find('Opinión del CF')
            idx2 = text.find('Opinión del Consejo Fiscal')
            idx3 = text.find('Opinión de CF')
            idx = max(idx1, idx2, idx3)
            if idx >= 0:
                start = max(0, idx - 50)
                end = min(len(text), idx + 150)
                print(f'  Context: ...{text[start:end]}...')

    # Check what remains in clean
    if clean_pages:
        print(f'\n--- CLEAN first page is: page {clean_pages[0]["page"]} ---')
        print(f'First 300 chars: {clean_pages[0]["text"][:300]}')

    print('\n')
