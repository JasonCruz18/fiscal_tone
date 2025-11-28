import json

with open('data/raw/scanned_pdfs_extracted_text.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print('PATTERNS DE ANEXO:')
print('='*80)
anexo_cases = []
for entry in data:
    text = entry['text']
    page = entry['page']
    pdf = entry['pdf_filename']

    # Buscar Anexo al inicio o como encabezado
    if text.strip().startswith('Anexo'):
        anexo_cases.append(f"{pdf} p{page}: STARTS WITH Anexo")
        print(f"{pdf} p{page}: Text starts with Anexo")
        print(f"  Preview: {text[:150]}")
        print()

    # Buscar \n\nAnexo
    if '\n\nAnexo' in text:
        pos = text.find('\n\nAnexo')
        anexo_cases.append(f"{pdf} p{page}: Contains \\n\\nAnexo at pos {pos}")
        print(f"{pdf} p{page}: Contains \\n\\nAnexo")
        print(f"  Preview: ...{text[max(0,pos-50):pos+100]}...")
        print()

print(f'\nTotal Anexo cases: {len(anexo_cases)}')
print()
print('PATTERNS DE CARTA:')
print('='*80)
carta_cases = []
for entry in data:
    text = entry['text']
    page = entry['page']
    pdf = entry['pdf_filename']

    # Buscar Carta
    if 'Carta' in text or 'carta' in text:
        # Buscar contexto
        for pattern in ['Carta', 'carta']:
            if pattern in text:
                pos = text.find(pattern)
                carta_cases.append(f"{pdf} p{page}")
                print(f"{pdf} p{page}: Contains '{pattern}'")
                print(f"  Preview: ...{text[max(0,pos-30):pos+80]}...")
                print()
                break

print(f'Total Carta cases: {len(carta_cases)}')

# Buscar ruido común
print('\n' + '='*80)
print('RUIDO COMÚN:')
print('='*80)
noise_chars = {}
for entry in data:
    text = entry['text']
    for char in ['*', '!', '?', '(', ')', '[', ']', '{', '}', '|', '_', '~']:
        # Contar paréntesis solitarios
        if char == '(':
            # Buscar ( sin cerrar
            import re
            solo_parens = re.findall(r'\(\s', text)
            if solo_parens:
                if char not in noise_chars:
                    noise_chars[char] = 0
                noise_chars[char] += len(solo_parens)
        else:
            count = text.count(char)
            if count > 0:
                if char not in noise_chars:
                    noise_chars[char] = 0
                noise_chars[char] += count

for char, count in sorted(noise_chars.items(), key=lambda x: x[1], reverse=True):
    print(f"  '{char}': {count} occurrences")
