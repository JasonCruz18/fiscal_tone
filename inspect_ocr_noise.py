import json
import re
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('data/raw/scanned_pdfs_clean_extracted_text.json', 'r', encoding='utf-8') as f:
    clean = json.load(f)

# Pattern 4: Letras mayúsculas con tilde aisladas
print('4. LETRAS MAYUSCULAS CON TILDE AISLADAS:')
tilde_count = 0
for entry in clean:
    # Buscar Á, É, Í, Ó, Ú solas (no parte de una palabra)
    matches = re.finditer(r'\s([ÁÉÍÓÚ])\s', entry['text'])
    for m in list(matches)[:3]:
        start = max(0, m.start() - 25)
        end = min(len(entry['text']), m.end() + 25)
        print(f"  {entry['pdf_filename']} p{entry['page']}: ...{entry['text'][start:end]}...")
        tilde_count += 1

print(f'  Total: {tilde_count} casos\n')

# Pattern 5: Secuencias extrañas con caracter especial
print('5. SECUENCIAS CON CARACTERES ESPECIALES RAROS:')
punct_count = 0
for entry in clean:
    matches = re.finditer(r'[�]+', entry['text'])
    for m in list(matches)[:3]:
        start = max(0, m.start() - 25)
        end = min(len(entry['text']), m.end() + 25)
        print(f"  {entry['pdf_filename']} p{entry['page']}: ...{entry['text'][start:end]}...")
        punct_count += 1

print(f'  Total: {punct_count} casos\n')

# Pattern 6: Múltiples espacios consecutivos
print('6. MÚLTIPLES ESPACIOS CONSECUTIVOS:')
space_count = 0
for entry in clean:
    matches = re.finditer(r' {2,}', entry['text'])
    for m in list(matches)[:3]:
        start = max(0, m.start() - 25)
        end = min(len(entry['text']), m.end() + 25)
        print(f"  {entry['pdf_filename']} p{entry['page']}: ...{repr(entry['text'][start:end])}...")
        space_count += 1

print(f'  Total: {space_count} casos\n')

# Pattern 7: Números con espacios raros
print('7. NÚMEROS CON FORMATO RARO:')
num_count = 0
for entry in clean:
    # Buscar números con espacios en medio: 1 234, 12 345, etc.
    matches = re.finditer(r'\d+\s+\d+', entry['text'])
    for m in list(matches)[:3]:
        # Verificar que no sea rango de años válido
        if not re.match(r'\d{4}\s+\d{4}', m.group(0)):
            start = max(0, m.start() - 25)
            end = min(len(entry['text']), m.end() + 25)
            print(f"  {entry['pdf_filename']} p{entry['page']}: ...{entry['text'][start:end]}...")
            num_count += 1

print(f'  Total: {num_count} casos\n')

# Pattern 8: Secuencias de símbolos raros al final de palabras
print('8. SÍMBOLOS RAROS PEGADOS A PALABRAS:')
symbol_count = 0
for entry in clean:
    # Buscar palabras seguidas de símbolos raros
    matches = re.finditer(r'\w+[>\<\|�]+[\s,.]', entry['text'])
    for m in list(matches)[:3]:
        start = max(0, m.start() - 20)
        end = min(len(entry['text']), m.end() + 20)
        print(f"  {entry['pdf_filename']} p{entry['page']}: ...{entry['text'][start:end]}...")
        symbol_count += 1

print(f'  Total: {symbol_count} casos\n')
