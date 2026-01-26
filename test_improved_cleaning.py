"""
Test script for improved header detection functions
"""
import re


def is_section_header(line: str, max_chars: int = 150, max_words: int = 20) -> bool:
    """Test version of is_section_header"""
    if not line:
        return False

    words = line.split()

    return (
        len(line) > 0 and
        len(line) < max_chars and
        len(words) > 0 and len(words) < max_words and
        line[0].isupper() and
        not line[-1] in '.!?' and
        not re.match(r'Lima,?\s+\d{1,2}\s+de', line)
    )


def is_chart_or_table_label(line: str) -> bool:
    """Test version of is_chart_or_table_label"""
    if not line or not line.strip():
        return False

    line = line.strip()

    # Pattern 1: Gráfico/Tabla/Cuadro/Figura + number
    if re.match(r'^(Gráfico|Tabla|Cuadro|Figura|Gráf|Tab)\s+N?°?\s*\d+', line, re.IGNORECASE):
        return True

    # Pattern 2: Number + colon
    if re.match(r'^\d+\s*:\s*.+', line):
        return True

    # Pattern 3: Roman numeral + period or colon
    if re.match(r'^[IVXLCDM]+\s*[.:]', line):
        return True

    # Pattern 4: Letter + parenthesis
    if re.match(r'^[A-Z]\s*\)\s*.+', line):
        return True

    # Pattern 5: Letter + period at start of short text
    if re.match(r'^[A-Z]\s*\.\s*.+', line) and len(line) < 100:
        return True

    return False


# Test cases from user's examples
test_cases = [
    # Headers that SHOULD be removed
    ("1: Leyes con impacto fiscal adverso (número de leyes)", True, "chart label"),
    ("Opinión del CF sobre las proyecciones contempladas en el IAPM", True, "section header"),
    ("Opinión del CF sobre la situación de las finanzas de los gobiernos subnacionales durante la crisis de la COVID-19", True, "section header"),
    ("Opinión del CF sobre el cumplimiento de la regla macrofiscal del SPNF", True, "section header"),
    ("Opinión del CF sobre operaciones de los gobiernos regionales y locales y el cumplimiento de las reglas fiscales", True, "section header"),
    ("Opinión del Consejo Fiscal acerca de la situación de las finanzas públicas al 2017", True, "section header"),
    ("I. Opinión del CF sobre el proyecto", True, "chart label"),
    ("A) Leyes con impacto fiscal por insistencia y costo fiscal", True, "chart label"),
    ("B) Leyes con impacto fiscal negativo", True, "chart label"),

    # Text that should NOT be removed (has ending period)
    ("El análisis de la DEM-CF también muestra que la producción legislativa reciente ha resultado singularmente nociva en términos fiscales.", False, "complete sentence"),
    ("El CF considera que esta norma, impulsada por el Congreso de la República y promulgada por el Poder Ejecutivo.", False, "complete sentence"),
    ("Solo desde agosto de 2024, las 5 leyes con mayor impacto sobre las finanzas públicas implican un costo fiscal anual cercano a S/ 22 mil millones.", False, "complete sentence"),
]

print("\n" + "="*80)
print("TESTING IMPROVED HEADER DETECTION")
print("="*80)

correct = 0
total = len(test_cases)

for text, should_remove, description in test_cases:
    is_header = is_section_header(text)
    is_label = is_chart_or_table_label(text)
    detected = is_header or is_label

    status = "PASS" if detected == should_remove else "FAIL"

    if detected == should_remove:
        correct += 1

    print(f"\n[{status}] {description}")
    print(f"  Text: '{text[:70]}...' ({len(text)} chars)")
    print(f"  Expected removal: {should_remove}")
    print(f"  Detected as header: {is_header}")
    print(f"  Detected as chart label: {is_label}")
    print(f"  Will be removed: {detected}")

print("\n" + "="*80)
print(f"RESULTS: {correct}/{total} tests passed ({correct/total*100:.1f}%)")
print("="*80 + "\n")
