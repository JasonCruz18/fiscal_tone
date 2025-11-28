import json
import re
import sys
import io

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

with open('data/raw/editable_pdfs_clean_extracted_text.json', 'r', encoding='utf-8') as f:
    clean = json.load(f)

print('='*80)
print('VERIFICACION DE LIMPIEZA MEJORADA - PDFs EDITABLES')
print('='*80)

# 1. Verificar que NO haya fechas de Lima
print('\n1. FECHAS DE LIMA (deberia ser 0):')
fecha_count = 0
for entry in clean:
    matches = re.finditer(r'Lima,?\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}', entry['text'])
    for m in list(matches)[:2]:
        fecha_count += 1
        start = max(0, m.start() - 30)
        end = min(len(entry['text']), m.end() + 30)
        print(f"  {entry['pdf_filename']} p{entry['page']}: ...{entry['text'][start:end]}...")

if fecha_count == 0:
    print('  OK - Perfecto! No hay fechas de Lima')
else:
    print(f'  Total: {fecha_count} fechas restantes (PROBLEMA)')

# 2. Verificar que NO haya false breaks
print('\n2. FALSE PARAGRAPH BREAKS (deberia ser 0):')
false_count = 0
for entry in clean:
    matches = re.findall(r'\n\n([a-záéíóúñü])', entry['text'])
    if matches:
        false_count += len(matches)
        if false_count <= 3:  # Primeros 3
            m = re.search(r'\n\n([a-záéíóúñü])', entry['text'])
            start = max(0, m.start() - 30)
            end = min(len(entry['text']), m.end() + 30)
            print(f"  {entry['pdf_filename']} p{entry['page']}: ...{entry['text'][start:end]}...")

if false_count == 0:
    print('  OK - Perfecto! No hay false paragraph breaks')
else:
    print(f'  Total: {false_count} false breaks restantes (PROBLEMA)')

# 3. Verificar el ejemplo específico del usuario
print('\n3. VERIFICACION DEL EJEMPLO ESPECIFICO:')
print('   PDF: Pronunciamiento-IAPM25-28-VF.pdf, page 10')
ejemplo = [e for e in clean if e['pdf_filename'] == 'Pronunciamiento-IAPM25-28-VF.pdf' and e['page'] == 10]
if ejemplo:
    text = ejemplo[0]['text']
    # Buscar el fragmento específico
    if 'con\n\nla reciente propuesta' in text:
        print('  X PROBLEMA: Todavia hay false break: "con\\n\\nla reciente propuesta"')
    elif 'con la reciente propuesta' in text:
        print('  OK - CORREGIDO: "con la reciente propuesta" (sin false break)')
    else:
        print('  ? No se encontro el fragmento especifico')
        # Buscar variantes
        if 'la reciente propuesta' in text:
            # Encontrar el contexto
            idx = text.index('la reciente propuesta')
            start = max(0, idx - 50)
            end = min(len(text), idx + 50)
            print(f'  Contexto encontrado: ...{text[start:end]}...')
else:
    print('  PDF/pagina no encontrado')

print('\n' + '='*80)
print('RESUMEN')
print('='*80)

if fecha_count == 0 and false_count == 0:
    print('OK OK OK - PERFECTO! Todos los patrones de ruido han sido eliminados!')
else:
    print(f'Problemas restantes: {fecha_count} fechas, {false_count} false breaks')
print('='*80)
