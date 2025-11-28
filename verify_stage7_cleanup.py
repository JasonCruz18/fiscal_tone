import json
import re
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('data/raw/scanned_pdfs_clean_extracted_text.json', 'r', encoding='utf-8') as f:
    clean = json.load(f)

print('VERIFICACIÓN DE LIMPIEZA - STAGE 7')
print('='*80)

# 1. Letras solitarias mayúsculas
print('\n1. LETRAS SOLITARIAS MAYUSCULAS (debería ser 0):')
count = 0
for entry in clean:
    matches = re.findall(r'\n\n([A-ZÁÉÍÓÚÑ])\s+([a-záéíóúñ]\w+)', entry['text'])
    # Excluir números romanos válidos
    valid_romans = ['I', 'V', 'X']
    matches = [m for m in matches if m[0] not in valid_romans]
    if matches:
        count += len(matches)
        print(f"  {entry['pdf_filename']} p{entry['page']}: '{matches[0][0]} {matches[0][1]}'")

print(f'  Total: {count} casos')

# 2. Caracteres especiales >, <, |
print('\n2. CARACTERES ESPECIALES >, <, | (debería ser 0):')
count = 0
for entry in clean:
    if re.search(r'[><\|]', entry['text']):
        matches = list(re.finditer(r'.{20}[><\|].{20}', entry['text']))
        if matches:
            count += 1
            snippet = matches[0].group(0)
            print(f"  {entry['pdf_filename']} p{entry['page']}: ...{snippet}...")

print(f'  Total: {count} casos')

# 3. Espacios extras en rangos de años
print('\n3. ESPACIOS EXTRAS EN RANGOS (debería ser 0):')
count = 0
for entry in clean:
    # Buscar: número - espacio(s) - año
    matches = re.findall(r'\d+\s+-\s+\d{4}', entry['text'])
    if matches:
        count += len(matches)
        print(f"  {entry['pdf_filename']} p{entry['page']}: '{matches[0]}'")

print(f'  Total: {count} casos')

# 4. Secuencias raras combinadas
print('\n4. SECUENCIAS RARAS COMBINADAS (debería ser 0):')
count = 0
for entry in clean:
    # Buscar combinaciones raras de símbolos y letras
    if re.search(r"[><]['\"]\w", entry['text']):
        count += 1
        m = re.search(r".{20}[><]['\"]\\w.{20}", entry['text'])
        if m:
            print(f"  {entry['pdf_filename']} p{entry['page']}: ...{m.group(0)}...")

print(f'  Total: {count} casos')

# 5. Mayúsculas con tilde aisladas (Ó, Ú, etc.)
print('\n5. MAYUSCULAS CON TILDE AISLADAS (debería ser 0):')
count = 0
for entry in clean:
    matches = re.findall(r'\s([ÁÉÍÓÚ])\s', entry['text'])
    if matches:
        count += len(matches)
        print(f"  {entry['pdf_filename']} p{entry['page']}: letra '{matches[0]}' aislada")

print(f'  Total: {count} casos')

print('\n' + '='*80)
print('RESUMEN DE LIMPIEZA FINAL')
print('='*80)

total_issues = 0
total_issues_dict = {
    'Letras solitarias': 0,
    'Símbolos <, >, |': 0,
    'Espacios en rangos': 0,
    'Secuencias raras': 0,
    'Tildes aisladas': 0
}

# Recount all
for entry in clean:
    # Letras solitarias
    matches = re.findall(r'\n\n([A-ZÁÉÍÓÚÑ])\s+([a-záéíóúñ]\w+)', entry['text'])
    valid_romans = ['I', 'V', 'X']
    matches = [m for m in matches if m[0] not in valid_romans]
    total_issues_dict['Letras solitarias'] += len(matches)

    # Símbolos
    if re.search(r'[><\|]', entry['text']):
        total_issues_dict['Símbolos <, >, |'] += 1

    # Espacios en rangos
    matches = re.findall(r'\d+\s+-\s+\d{4}', entry['text'])
    total_issues_dict['Espacios en rangos'] += len(matches)

    # Secuencias raras
    if re.search(r"[><]['\"]\\w", entry['text']):
        total_issues_dict['Secuencias raras'] += 1

    # Tildes aisladas
    matches = re.findall(r'\s([ÁÉÍÓÚ])\s', entry['text'])
    total_issues_dict['Tildes aisladas'] += len(matches)

for issue_type, count in total_issues_dict.items():
    status = '✓' if count == 0 else '✗'
    print(f'{status} {issue_type}: {count} casos')
    total_issues += count

print('='*80)
if total_issues == 0:
    print('✓✓✓ PERFECTO! Todos los patrones de ruido OCR han sido eliminados!')
else:
    print(f'Total de problemas restantes: {total_issues}')
print('='*80)
