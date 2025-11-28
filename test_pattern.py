import re

text1 = 'requerimiento\n\nfinanciero del'
text2 = 'respectiva\n\nprobabilidad de'

pattern = r'([a-záéíóúñü])\n\n([a-záéíóúñü]{3,30}\b)'

r1 = re.sub(pattern, r'\1 \2', text1)
r2 = re.sub(pattern, r'\1 \2', text2)

print(f'Test 1: {repr(text1)}')
print(f'Result: {repr(r1)}')
print(f'Changed: {r1 != text1}')

print(f'\nTest 2: {repr(text2)}')
print(f'Result: {repr(r2)}')
print(f'Changed: {r2 != text2}')

# Test with actual data from file
import json
with open('data/raw/scanned_pdfs_clean_extracted_text.json', 'r', encoding='utf-8') as f:
    clean = json.load(f)

# Get the actual text from the files
pdf1 = [e for e in clean if e['pdf_filename'] == 'Informe-N�-001-2018-CF.pdf' and e['page'] == 2]
if pdf1:
    text = pdf1[0]['text']
    # Find the snippet
    import re
    match = re.search(r'requerimiento\n\nfinanciero', text)
    if match:
        print(f'\nFound in actual file at position {match.start()}')
        snippet = text[match.start()-20:match.end()+20]
        print(f'Snippet: {repr(snippet)}')

        # Try to apply pattern
        result = re.sub(pattern, r'\1 \2', snippet)
        print(f'After pattern: {repr(result)}')
        print(f'Changed: {result != snippet}')
    else:
        print('\nNOT FOUND in actual file')
