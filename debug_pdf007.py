import json
import re

# Load raw data
with open('data/raw/scanned_pdfs_extracted_text.json', 'r', encoding='utf-8') as f:
    raw = json.load(f)

# Get page 2 of PDF 007
p2 = [x for x in raw if x['pdf_filename'] == 'Informe_CF_N_007-2016.pdf' and x['page'] == 2][0]
p3 = [x for x in raw if x['pdf_filename'] == 'Informe_CF_N_007-2016.pdf' and x['page'] == 3][0]

patterns = ['Opinión del Consejo Fiscal', 'Opinión del CF', 'Opinión de CF']

print("="*80)
print("PDF 007 - PAGE 2")
print("="*80)
print(f'Text length: {len(p2["text"])}')
print(f'First 300 chars: {p2["text"][:300]}')

found = False
for pattern in patterns:
    full_pattern = r'(?:(?:\d+|[IVXivx]+)\.?\s*[—\-]?\s*)?[\'"]?\s*' + pattern
    match = re.search(r'\n\n\s*' + full_pattern, p2['text'])
    if match:
        print(f'\n[FOUND] "{pattern}" at position {match.start()}')
        context_start = max(0, match.start() - 50)
        context_end = min(len(p2['text']), match.end() + 100)
        print(f'Context: ...{p2["text"][context_start:context_end]}...')
        if match.start() > 200:
            print(f'[MATCH] Position {match.start()} > 200 - WOULD BE SELECTED')
            found = True
        else:
            print(f'[SKIP] Position {match.start()} <= 200 - ignored')
        break

if not found:
    print('\n[NOT FOUND] No keyword after position 200 on page 2')

print("\n" + "="*80)
print("PDF 007 - PAGE 3")
print("="*80)
print(f'Text length: {len(p3["text"])}')

found = False
for pattern in patterns:
    full_pattern = r'(?:(?:\d+|[IVXivx]+)\.?\s*[—\-]?\s*)?[\'"]?\s*' + pattern
    match = re.search(r'\n\n\s*' + full_pattern, p3['text'])
    if match:
        print(f'\n[FOUND] "{pattern}" at position {match.start()}')
        context_start = max(0, match.start() - 50)
        context_end = min(len(p3['text']), match.end() + 100)
        print(f'Context: ...{p3["text"][context_start:context_end]}...')
        if match.start() > 200:
            print(f'[MATCH] Position {match.start()} > 200 - WOULD BE SELECTED')
            found = True
        else:
            print(f'[SKIP] Position {match.start()} <= 200 - ignored')
        break

if not found:
    print('\n[NOT FOUND] No keyword after position 200 on page 3')
