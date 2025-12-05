"""
Clean Extracted Text from Scanned PDFs

7-stage cleaning pipeline optimized for CF opinion extraction:
0. Preliminary text normalization (spaces, OCR artifacts)
1. Filter by keywords ONLY FROM PAGE 2+ (remove text before "Opinión del CF")
2. Remove ALL false paragraph breaks (\n\n before lowercase)
3. Remove headers/titles (short text surrounded by \n\n)
4. Remove annexes (truncate after "Anexo")
5. Remove letter pages (delete pages with "Carta")
6. Aggressive noise reduction (remove OCR artifacts, page numbers, etc.)

Output: scanned_pdfs_clean_extracted_text.json
"""

import json
import re
from pathlib import Path


# ────────────────────────────────────────────────────────────────────────────
# Helper Functions for Header/Title Detection
# ────────────────────────────────────────────────────────────────────────────

def is_section_header(line: str, max_chars: int = 200, max_words: int = 35) -> bool:
    """
    Determine if a line is a section header (should be removed).

    IMPROVED (based on user feedback):
    - Increased thresholds: 200 chars (was 150), 35 words (was 25)
    - More aggressive detection: assumes text without ending period is a header
    - Special patterns for numbered sections: "ll. — Opinión...", "I. Opinión...", etc.
    - Detects headers even when very short (2-3 words)
    - Detects long headers: "Elasticidad de la relación entre..." (31 words)

    Conditions:
        - Length < 200 characters
        - Word count < 35 words (increased to catch longer headers)
        - Starts with uppercase letter, number, or special section marker
        - Is NOT a date
        - Does NOT end with period (strong indicator of header)

    Examples:
        - "Índices de precios de minerales y de hidrocarburos" → True (no period)
        - "Opinión del CF sobre las proyecciones..." → True (header)
        - "Transparencia fiscal" → True (header)
        - "ll. — Opinión de CF sobre el proyecto de DPME" → True (header)
        - "Aspectos generales" → True (2 words, no period)
        - "El CF considera que esta norma es adecuada." → False (ends with period, long)
    """
    if not line:
        return False

    words = line.split()

    # Basic length and word count checks
    if len(line) >= max_chars or len(words) >= max_words:
        return False

    # Must have some content
    if len(words) == 0:
        return False

    # Exclude dates
    if re.match(r'Lima,?\s+\d{1,2}\s+de', line):
        return False

    # CRITICAL: Never consider "El presente informe..." as a header
    # This is the standard opening phrase in CF documents
    if line.startswith('El presente informe'):
        return False

    # Must start with uppercase, number, or special section marker
    # Allow patterns like "ll. —", "I.", "II.", "lll." (OCR corruption), etc.
    first_char_ok = (
        line[0].isupper() or
        line[0].isdigit() or
        re.match(r'^[ivxlcdmh]+\s*[.—\-:]', line, re.IGNORECASE)  # Added 'h' for OCR corruption
    )

    if not first_char_ok:
        return False

    # Get last meaningful character (ignore trailing whitespace)
    last_char = line.rstrip()[-1] if line.rstrip() else ''

    # CRITICAL: If ends with preposition/article/continuation word, it's NOT a complete header
    # (it's likely a partial sentence due to false break)
    # Examples:
    #   - "...responde a la solicitud enviada por el Ministerio de" <- NOT a header!
    #   - "...resultado fiscal del Sector Público No" <- NOT a header!
    last_word = words[-1].lower().rstrip('.,;:!?') if words else ''
    continuation_words = ['de', 'del', 'la', 'el', 'los', 'las', 'un', 'una', 'en', 'con', 'por', 'para', 'sobre', 'al', 'a', 'ante', 'bajo', 'hacia', 'mediante', 'según', 'tras', 'entre', 'sin', 'desde', 'hasta', 'y', 'e', 'o', 'u', 'no']
    if last_word in continuation_words:
        return False

    # AGGRESSIVE RULE: If doesn't end with period, it's likely a header
    # This catches: "Índices de precios de minerales y de hidrocarburos"
    # Also: "Transparencia fiscal", "Aspectos generales", etc.
    if last_char != '.':
        return True

    # If ends with period, only consider it a header if:
    # 1. Very short (< 8 words) - likely a short section header
    # 2. Preceded by weird OCR characters like ".!" or ".?"
    if len(words) < 8:
        return True

    # Check for OCR artifacts before period
    if len(line) > 1 and line[-2] in '!?':
        return True

    # Otherwise, it's likely a sentence (longer text ending with period)
    return False


def is_chart_or_table_label(line: str) -> bool:
    """
    Detect chart/table labels with numbered/lettered patterns.

    Patterns detected:
        - "1: Leyes con impacto fiscal adverso" (number + colon)
        - "I. Opinión del CF sobre..." (Roman numeral + period)
        - "A) Leyes con impacto" (letter + parenthesis)
        - "Gráfico 1:", "Tabla N° 2:" (explicit chart/table references)

    Examples:
        >>> is_chart_or_table_label("1: Leyes con impacto fiscal adverso")
        True
        >>> is_chart_or_table_label("I. Opinión del CF sobre el proyecto")
        True
        >>> is_chart_or_table_label("El CF considera que...")
        False
    """
    if not line or not line.strip():
        return False

    line = line.strip()

    # Pattern 1: Gráfico/Tabla/Cuadro/Figura + number
    if re.match(r'^(Gráfico|Tabla|Cuadro|Figura|Gráf|Tab)\s+N?°?\s*\d+', line, re.IGNORECASE):
        return True

    # Pattern 2: Number + colon (e.g., "1: Title", "2: Subtitle")
    if re.match(r'^\d+\s*:\s*.+', line):
        return True

    # Pattern 3: Roman numeral + period or colon (e.g., "I. Title", "II: Subtitle")
    if re.match(r'^[IVXLCDM]+\s*[.:]', line):
        return True

    # Pattern 4: Letter + parenthesis (e.g., "A) Item", "B) Item")
    if re.match(r'^[A-Z]\s*\)\s*.+', line):
        return True

    # Pattern 5: Letter + period at start of short text (e.g., "A. Item")
    if re.match(r'^[A-Z]\s*\.\s*.+', line) and len(line) < 100:
        return True

    return False


def stage0_preliminary_cleaning(data, enabled=True):
    """
    Stage 0: Preliminary text normalization

    Cleans common OCR artifacts:
    - Removes document IDs at the beginning (e.g., "informe N 001-2018-CF")
    - Removes extra spaces before punctuation (" <", " ;", etc.)
    - Normalizes multiple spaces
    - Removes spaces around newlines
    """
    if not enabled:
        return data

    cleaned_data = []
    total_chars_removed = 0

    for entry in data:
        text = entry['text']
        original_length = len(text)

        # FIRST: Remove document ID at the very beginning
        # Patterns: "informe N 001-2018-CF", "Informe N* 003-2017-CF", etc.
        # These are always at the start, followed by the real content
        text = re.sub(r'^[Ii]nforme\s+N[*°º]?\s*\d{3,4}[-\s]*\d{4}[-\s]*CF\s+', '', text, flags=re.IGNORECASE)

        # Remove spaces before punctuation
        text = re.sub(r' +([<>;:?!,.\)\]\}])', r'\1', text)
        # Remove spaces after opening brackets
        text = re.sub(r'([\(\[\{]) +', r'\1', text)
        # Normalize multiple spaces
        text = re.sub(r'(?<!\n) {2,}(?!\n)', ' ', text)
        # Remove spaces before/after newlines
        text = re.sub(r' +\n', '\n', text)
        text = re.sub(r'\n +', '\n', text)
        # Trim
        text = text.strip()

        entry['text'] = text
        total_chars_removed += (original_length - len(text))
        cleaned_data.append(entry)

    print(f"  Stage 0: Cleaned {total_chars_removed:,} chars (OCR artifacts + document IDs)")
    return cleaned_data


def stage1_filter_keywords(data, enabled=True):
    """
    Stage 1: CRITICAL keyword filtering

    RULES (as specified by user):
    - Search ONLY from page 2+ (page 1 has document titles, not opinions)
    - Look for "Opinión del CF" / "Opinión del Consejo Fiscal" / "Opinión de CF"
    - With optional numbering: "I. Opinión...", "II. Opinión...", etc.
    - Keyword must be a section header (at page start OR after \n\n)
    - Remove ALL text before keyword (including previous pages)
    - PRESERVE the keyword (it's the opinion section header)

    Examples:
    - Page 4: "\n\nOpinión de CF sobre las proyecciones..." → start from page 4
    - Page 3: "\n\nII. — Opinión de CF sobre el proyecto..." → start from page 3
    """
    if not enabled:
        return data

    # Opinion keyword patterns
    patterns = [
        r'Opinión del Consejo Fiscal',
        r'Opinión del CF',
        r'Opinión de CF',
    ]

    cleaned_data = []
    removed_pages = 0
    removed_chars = 0

    # Group by PDF
    pdf_groups = {}
    for entry in data:
        pdf = entry['pdf_filename']
        if pdf not in pdf_groups:
            pdf_groups[pdf] = []
        pdf_groups[pdf].append(entry)

    # Process each PDF
    for pdf_name, pages in pdf_groups.items():
        pages = sorted(pages, key=lambda x: x['page'])

        # Find keyword starting from PAGE 2+ (ignore page 1)
        found_page = None
        found_pos = None

        for page in pages:
            # CRITICAL: Skip page 1
            if page['page'] < 2:
                continue

            text = page['text']

            # Check if any keyword appears as SECTION HEADER
            # Must be: (1) after \n\n AND (2) after significant content (position > 200)
            # This filters out document titles (early in page) and keeps section headers (middle of page)
            for pattern in patterns:
                # Allow optional section numbering: I., II., 1., 2., ll. (OCR errors), etc.
                # OCR often confuses: II → ll, III → lll, IV → lV, etc.
                # So allow any combination of letters/digits followed by optional dot/separator
                # Allow optional punctuation before keyword: ', ", etc.
                full_pattern = r'(?:(?:\d+|[a-zA-Z]+)\.?\s*[—\-]?\s*)?[\'"]?\s*' + pattern

                # ONLY accept keywords AFTER \n\n (section headers)
                match = re.search(r'\n\n\s*' + full_pattern, text)
                if match and match.start() > 200:  # Must be after position 200 (section header, not title)
                    found_page = page['page']
                    found_pos = match.start()
                    break

            if found_page:
                break

        # Apply filtering
        if found_page:
            for page in pages:
                if page['page'] < found_page:
                    # Remove entire page before keyword
                    removed_pages += 1
                    removed_chars += len(page['text'])
                elif page['page'] == found_page:
                    # Remove text before keyword, KEEP keyword
                    text = page['text']

                    # Find keyword position again (ONLY after \n\n)
                    keyword_pos = None
                    for pattern in patterns:
                        full_pattern = r'(?:(?:\d+|[a-zA-Z]+)\.?\s*[—\-]?\s*)?[\'"]?\s*' + pattern

                        # ONLY search after \n\n (section headers)
                        match = re.search(r'\n\n\s*' + full_pattern, text)
                        if match and match.start() > 200:
                            keyword_pos = match.start()
                            break

                    if keyword_pos is not None:
                        removed_chars += keyword_pos
                        page['text'] = text[keyword_pos:]

                    cleaned_data.append(page)
                else:
                    # Keep all pages after keyword page
                    cleaned_data.append(page)
        else:
            # No keyword found - keep ALL pages from page 1
            cleaned_data.extend(pages)

    print(f"  Stage 1: Removed {removed_pages} pages, {removed_chars:,} chars before keywords")
    return cleaned_data


def stage4_remove_false_paragraph_breaks(data, enabled=True):
    """
    Stage 4: Remove ALL false paragraph breaks (IMPROVED & ROBUST)

    NOTE: This stage is executed MULTIPLE times throughout the pipeline
    to clean up false breaks created by other stages.

    IMPROVEMENTS based on user feedback:
    1. Context-aware detection: checks if previous text ends with sentence punctuation
    2. Removes \n\n before capitalized words mid-sentence (e.g., "de\n\nEconomía")
    3. Removes \n\n before numbers/decimals (e.g., "de\n\n2,0 por ciento")
    4. ALL \n\n before lowercase letters (existing rule)
    5. \n\n before years (existing rule)
    6. \n\n before common connectors (existing rule)

    The key insight: if previous text doesn't end with .!?:, then \n\n is likely a false break
    """
    if not enabled:
        return data

    cleaned_data = []
    total_removed = 0

    for entry in data:
        text = entry['text']
        original_count = text.count('\n\n')

        # RULE 1: Remove ALL \n\n before lowercase letters
        # This is the main rule - paragraphs NEVER start with lowercase
        text = re.sub(r'\n\n([a-záéíóúñü])', r' \1', text)

        # RULE 2: Remove \n\n before years
        text = re.sub(r'\n\n([12]\d{3})', r' \1', text)

        # RULE 3: Remove \n\n before common connectors
        connectors = r'(?:de|del|la|el|los|las|un|una|en|con|por|para|que|se|y|o|su|sus|sobre|al|ha|han|desde|hasta|entre|sin|tras|ante|bajo|hacia|mediante|según|versus|vía|…|\.\.\.|a)'
        text = re.sub(r'\n\n(' + connectors + r'\s)', r' \1', text)

        # RULE 3.5: Remove \n\n before document references (N*, N°, etc.)
        # Example: "...Proyecto de Ley\n\nN* 08-2016-PE"
        text = re.sub(r'\n\n(N[*°\s]?\d)', r' \1', text)

        # RULE 3b (NEW): Remove \n\n before ellipsis (… or ...) specifically
        # Example: "productividad\n\n… y" → "productividad … y"
        text = re.sub(r'\n\n(…|\.\.\.)', r' \1', text)

        # RULE 4 (NEW): Remove \n\n before numbers (decimals, percentages, etc.)
        # Examples: "de\n\n2,0 por ciento", "superávit de\n\n0,5 por ciento"
        text = re.sub(r'\n\n(\d+[,.]?\d*\s*(?:por\s+ciento|%)?)', r' \1', text)

        # RULE 5 (NEW): Remove \n\n when previous text ends with preposition/article/conjunction (without period)
        # Examples: "gasto del\n\nGobierno" → "gasto del Gobierno"
        #           "para la\n\nCooperación" → "para la Cooperación"
        #           "Inversión e\n\nImpuestos" → "Inversión e Impuestos"
        # CRITICAL: Only apply if the text before preposition/article is NOT a header itself
        # CRITICAL: Must handle MULTIPLE consecutive false breaks in same paragraph
        # Bad example: "La situación fiscal\n\nTexto" - DON'T join (first part is a header)
        # Good example: "gasto del\n\nGobierno" - DO join (first part is not a header)

        # Split by \n\n and process with skip index for consumed segments
        segments = text.split('\n\n')
        cleaned_segments = []
        # Words that indicate sentence continuation (never end a complete sentence)
        prepositions_articles = ['de', 'del', 'la', 'el', 'los', 'las', 'un', 'una', 'en', 'con', 'por', 'para', 'sobre', 'al', 'a', 'ante', 'bajo', 'hacia', 'mediante', 'según', 'tras', 'entre', 'sin', 'desde', 'hasta', 'y', 'e', 'o', 'u', 'no']

        i = 0
        while i < len(segments):
            segment = segments[i].strip()
            if not segment:
                i += 1
                continue

            # Accumulate joined text (for multiple consecutive false breaks)
            accumulated_text = segment

            # Check if we should join with next segments
            j = i + 1
            while j < len(segments):
                next_segment = segments[j].strip()
                if not next_segment:
                    j += 1
                    continue

                # Check if current accumulated text ends with prep/article
                last_word = accumulated_text.split()[-1].lower() if accumulated_text.split() else ""

                # Check if next segment starts with capital
                starts_with_capital = next_segment and next_segment[0].isupper()

                if last_word in prepositions_articles and starts_with_capital:
                    # CRITICAL CHECK: Is accumulated text a header by itself?
                    # If so, DON'T join (it's a complete header, not a false break)
                    if is_section_header(accumulated_text):
                        # It's a header - stop joining
                        break
                    else:
                        # It's not a header - join with next (false break)
                        accumulated_text = accumulated_text + ' ' + next_segment
                        total_removed += 1
                        j += 1  # Move to next segment
                else:
                    # Can't join - stop
                    break

            cleaned_segments.append(accumulated_text)
            i = j  # Skip all consumed segments

        text = '\n\n'.join(cleaned_segments)

        # RULE 5 (REMOVED): La lógica "context-aware" era demasiado arriesgada
        # NUNCA eliminamos \n\n antes de texto que empieza con MAYÚSCULA
        # Regla absoluta: "Un párrafo nunca inicia con minúscula"
        # Pero SÍ puede iniciar con mayúscula, incluso si el anterior termina incorrectamente
        # Mejor dejar algunos false breaks que destruir la estructura de párrafos

        entry['text'] = text
        cleaned_data.append(entry)

    print(f"  Stage 4: Removed {total_removed} false paragraph breaks (improved robust detection)")
    return cleaned_data


def stage5_remove_headers_and_titles(data, enabled=True):
    """
    Stage 5: Remove headers, titles, subtitles

    IMPROVED: Enhanced header detection using smart helper functions
    - is_section_header() detects headers (< 200 chars, < 25 words)
    - is_chart_or_table_label() detects numbered patterns (1:, I., A), etc.)
    - Specific patterns: "Conclusiones", "Riesgos", etc.

    Executed AFTER keyword filtering and annex truncation, so NOW we can remove ALL headers including:
    - "Opinión del CF sobre las proyecciones contempladas en el IAPM"
    - "1: Leyes con impacto fiscal adverso"
    - "I. Opinión del CF sobre el cumplimiento..."
    - "Conclusiones", "Conclusiones y recomendaciones", "III. Conclusiones"
    - "Riesgos", "Antecedentes", etc.
    - "ANEXO:" (standalone annex headers that didn't cause truncation)
    - Page 1 titles (for PDFs without keywords)

    IMPORTANT: No exceptions for "Opinión del CF" keywords anymore!
    (They were already used for filtering in stage 1, now they should be removed)
    """
    if not enabled:
        return data

    cleaned_data = []
    total_removed = 0

    # Specific section header patterns to remove (case-insensitive)
    section_headers = [
        r'^[IVXLH]{1,4}\.?\s*[-—]?\s*Conclusiones?(?:\s+y\s+recomendaciones)?$',
        r'^Conclusiones?(?:\s+y\s+recomendaciones)?$',
        r'^[IVXLH]{1,4}\.?\s*[-—]?\s*Riesgos?$',
        r'^Riesgos?$',
        r'^[IVXLH]{1,4}\.?\s*[-—]?\s*Antecedentes?$',
        r'^Antecedentes?$',
        r'^[IVXLH]{1,4}\.?\s*[-—]?\s*Introducción$',
        r'^Introducción$',
    ]

    for entry in data:
        text = entry['text']

        # FIRST: Remove section headers that are stuck to following text (no \n\n after)
        # Pattern: \n\nConclusiones El texto... → \n\nEl texto...
        for pattern in section_headers:
            # Remove pattern when followed immediately by capital letter (next paragraph)
            text = re.sub(r'\n\n' + pattern + r'(?=\s+[A-ZÁÉÍÓÚÑ])', '\n\n', text, flags=re.IGNORECASE)

        # NOTE: We do NOT try to detect "headers stuck to text" because it's too risky
        # It often mistakes the beginning of valid paragraphs as headers
        # Example: "El Consejo Fiscal coincide con el MEF..." gets mistaken as header
        # Better to leave a few headers than to destroy valid paragraph text!

        # Pattern 1: \n\n[text]\n\n (paragraphs surrounded by double newlines)
        def replace_header(match):
            nonlocal total_removed
            header = match.group(1).strip()

            # Check specific section headers first
            for pattern in section_headers:
                if re.match(pattern, header, re.IGNORECASE):
                    total_removed += 1
                    return '\n\n'

            # Then check general header patterns
            if is_section_header(header) or is_chart_or_table_label(header):
                total_removed += 1
                return '\n\n'
            else:
                return match.group(0)

        text = re.sub(r'\n\n(.+?)\n\n', replace_header, text, flags=re.DOTALL)

        # Pattern 2: ^[text]\n\n (at page start, no \n\n before it)
        match = re.match(r'^(.+?)\n\n', text, flags=re.DOTALL)
        if match:
            header = match.group(1).strip()

            # Check specific section headers first
            should_remove = False
            for pattern in section_headers:
                if re.match(pattern, header, re.IGNORECASE):
                    should_remove = True
                    break

            # Then check general header patterns
            if not should_remove:
                should_remove = is_section_header(header) or is_chart_or_table_label(header)

            if should_remove:
                text = text[match.end():]
                total_removed += 1

        entry['text'] = text
        cleaned_data.append(entry)

    print(f"  Stage 5: Removed {total_removed} headers/titles (improved detection + specific patterns)")
    return cleaned_data


def stage2_remove_annexes(data, enabled=True):
    """
    Stage 2: Remove annexes

    Truncates text at "ANEXO" pattern to remove appendix sections.
    Must run BEFORE stage5 (remove_headers) so that "ANEXO" is found for truncation.
    """
    if not enabled:
        return data

    cleaned_data = []
    removed_pages = 0
    removed_chars = 0

    pdf_groups = {}
    for entry in data:
        pdf = entry['pdf_filename']
        if pdf not in pdf_groups:
            pdf_groups[pdf] = []
        pdf_groups[pdf].append(entry)

    for pdf_name, pages in pdf_groups.items():
        pages = sorted(pages, key=lambda x: x['page'])

        # Find first anexo with robust OCR-tolerant patterns
        # OCR errors: ANEXO → ANEX0 (zero), AN EXO (space), ANExo (mixed case), etc.
        # Use regex for flexibility
        anexo_patterns = [
            r'ANEX[O0O]S?\s*:?',  # ANEXO, ANEXOS, ANEX0, ANEX0S with optional colon
            r'Anex[o0]\s*:?',     # Anexo, Anex0 with optional colon
            r'AN\s*EX[O0]S?\s*:?', # AN EXO, AN EX0 (with space)
        ]

        found_page = None
        found_at_start = False
        found_pattern = None

        for page in pages:
            text = page['text']

            for pattern in anexo_patterns:
                # Check at page start (case insensitive for robustness)
                if re.match(r'^[\s\n]*' + pattern, text, re.IGNORECASE):
                    found_page = page['page']
                    found_at_start = True
                    found_pattern = pattern
                    break

                # Check after \n\n (section header)
                if re.search(r'\n\n\s*' + pattern, text, re.IGNORECASE):
                    found_page = page['page']
                    found_at_start = False
                    found_pattern = pattern
                    break

            if found_page:
                break

        # Remove from anexo onwards
        if found_page:
            for page in pages:
                if page['page'] < found_page:
                    cleaned_data.append(page)
                elif page['page'] == found_page:
                    if found_at_start:
                        # Entire page starts with anexo - remove it
                        removed_pages += 1
                        removed_chars += len(page['text'])
                    else:
                        # Truncate at anexo position
                        text = page['text']
                        truncate_pos = None

                        # Find the anexo position using found_pattern
                        if found_pattern:
                            match = re.search(r'\n\n\s*' + found_pattern, text, re.IGNORECASE)
                            if match:
                                truncate_pos = match.start()

                        if truncate_pos is not None:
                            removed_chars += len(text) - truncate_pos
                            page['text'] = text[:truncate_pos]
                            if page['text'].strip():
                                cleaned_data.append(page)
                            else:
                                removed_pages += 1
                else:
                    removed_pages += 1
                    removed_chars += len(page['text'])
        else:
            cleaned_data.extend(pages)

    print(f"  Stage 2: Removed {removed_pages} pages, {removed_chars:,} chars (annexes)")
    return cleaned_data


def stage3_remove_letter_pages(data, enabled=True):
    """
    Stage 3: Remove letter pages

    Removes entire pages containing 'Carta N*' pattern (official letters).
    """
    if not enabled:
        return data

    cleaned_data = []
    removed = 0

    for entry in data:
        if re.search(r'Carta\s+N[*°º]?\s*\d', entry['text'], re.IGNORECASE):
            removed += 1
        else:
            cleaned_data.append(entry)

    print(f"  Stage 3: Removed {removed} letter pages")
    return cleaned_data


def stage6_aggressive_cleaning(data, enabled=True):
    """
    Stage 6: ULTRA CONSERVATIVE paragraph-level cleaning

    IMPROVED (based on user feedback):
    - Multi-line date+signature detection: "Lima, DD de mes de YYYY\n\nNOMBRE Presidente..."
    - Better patterns for dates with OCR artifacts: "Lima, 18...?% á? WALDO..."
    - Removes standalone dates, signatures, page numbers
    - Character threshold: < 30 chars (only extremely short noise)
    - All patterns checked carefully to avoid removing valid content

    This ensures we NEVER remove valid paragraph content.
    """
    if not enabled:
        return data

    cleaned_data = []
    paras_removed = 0
    chars_removed = 0

    for entry in data:
        text = entry['text']
        original_len = len(text)

        # FIRST: Remove multi-line date+signature patterns
        # Pattern: "Lima, DD de month de YYYY [OCR garbage] NAME Presidente..."
        # This needs to be done on the full text before splitting into paragraphs

        # Multi-line date followed by name and "Presidente"
        # Example: "Lima, 22 de agosto de 2017 de +\n\nWALDO EPIFANIO MENDOZA BELLIDO Presidente Consejo Fiscal"
        text = re.sub(
            r'Lima,\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}[^A-Z]*\n\n[A-ZÁÉÍÓÚÑ\s]+(?:Presidente|PRESIDENTE)[^\n]*',
            '',
            text,
            flags=re.IGNORECASE
        )

        # Single-line date with name and OCR garbage
        # Example: "Lima, 18 de agosto de 2016?% á? WALDO ZA BELLIDO"
        text = re.sub(
            r'Lima,\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}[^.]*?[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{10,}$',
            '',
            text,
            flags=re.MULTILINE | re.IGNORECASE
        )

        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        kept = []

        for para in paragraphs:
            should_remove = False

            # CRITICAL: Remove signature blocks with addresses (FATAL if not removed!)
            # Pattern: "PRESIDENTE DEL CONSEJO FISCAL 7/10 Av. República de Panamá..."
            if re.search(r'PRESIDENTE\s+DEL\s+CONSEJO\s+FISCAL.*?\d+/\d+.*?Av\.', para, re.IGNORECASE):
                should_remove = True

            # Remove signature blocks with page numbers and addresses
            # Pattern: Any text with "7/10" or page numbers followed by "Av." or addresses
            if re.search(r'\d+/\d+\s+Av\.\s+', para):
                should_remove = True

            # ULTRA CONSERVATIVE: Only remove VERY specific standalone patterns
            # All patterns require EXACT match (no other text before/after)
            if len(para) < 100:  # Only check short text (increased from 80 to catch longer dates)
                removal_patterns_ultra_conservative = [
                    r'^\d+\s*/\s*\d+$',                        # Page numbers ONLY: "7/10"
                    r'^Lima,\s+\d+\s+de\s+\w+\s+de\s+\d{4}.*$',  # Date with any trailing chars
                    r'^Informe\s+N[*°º]?\s*\d{3,4}[-\s]*CF[\s.]*$',  # Doc ID ONLY
                    r'^PRESIDENTE\s+DEL\s+CONSEJO\s+FISCAL[\s.]*$',  # Signature title ONLY
                    r'^Presidente\s+(?:del\s+)?Consejo\s+Fiscal[\s.]*$',  # Signature title (mixed case)
                    r'^Conclusiones?\s*:?[\s.]*$',             # Section header ONLY
                    r'^ANEXO\s*:?[\s.]*$',                     # Annex header ONLY
                ]

                for pattern in removal_patterns_ultra_conservative:
                    if re.search(pattern, para, re.IGNORECASE):
                        should_remove = True
                        break

            # ONLY extremely short (< 30 chars) - things like "!", "�", "10/18"
            if len(para) < 30:
                should_remove = True

            # All-caps names (signatures)
            # Example: "WALDO EPIFANIO MENDOZA BELLIDO", "WALDO ZA BELLIDO"
            if len(para) < 100:
                # Check if it's mostly uppercase letters (name pattern)
                alpha = [c for c in para if c.isalpha()]
                if alpha and len(alpha) > 10:
                    caps_ratio = sum(1 for c in alpha if c.isupper()) / len(alpha)
                    # High caps ratio (> 60%) indicates a name/signature
                    if caps_ratio > 0.6:
                        # Contains signature keywords OR is just a name
                        has_signature_keyword = any(kw in para.lower() for kw in ['presidente', 'consejo', 'fiscal'])
                        # OR looks like a name (mostly caps, few words, no verbs)
                        words = para.split()
                        looks_like_name = len(words) >= 2 and len(words) <= 6 and all(w[0].isupper() or not w[0].isalpha() for w in words if w)

                        if has_signature_keyword or looks_like_name:
                            should_remove = True

            # Remove isolated names with OCR garbage
            # Pattern: NAME followed by weird OCR chars like "?%", "á?", etc.
            if len(para) < 100:
                if re.search(r'^[A-ZÁÉÍÓÚÑ\s]{15,}[\?%<>°º\*\s]*$', para):
                    should_remove = True

            if should_remove:
                paras_removed += 1
                chars_removed += len(para)
            else:
                # Character cleaning - more aggressive on OCR artifacts
                para = re.sub(r'\s*\(\s*\)', '', para)  # Empty parens
                para = re.sub(r'\s*\[\s*\]', '', para)  # Empty brackets
                para = re.sub(r'[*]{2,}', '', para)     # Multiple asterisks
                para = re.sub(r'[?]{2,}', '?', para)    # Multiple question marks → single
                para = re.sub(r'[!]{2,}', '!', para)    # Multiple exclamation → single
                para = re.sub(r'[_|]+', '', para)       # Underscores and pipes
                para = re.sub(r' {2,}', ' ', para).strip()  # Multiple spaces

                if para:
                    kept.append(para)

        entry['text'] = '\n\n'.join(kept)

        if entry['text'].strip():
            cleaned_data.append(entry)
        else:
            chars_removed += original_len

    print(f"  Stage 6: Removed {paras_removed} noisy paragraphs, {chars_removed:,} chars (improved multi-line detection)")
    return cleaned_data


def stage7_final_ocr_cleanup(data, enabled=True):
    """
    Stage 7: FINAL OCR CLEANUP - "La cereza del pastel"

    IMPROVED (based on user feedback):
    Removes final OCR artifacts and noise:
    1. Footnote numbers attached to words: "claves?78" → "claves"
    2. Multiple question marks: "fiscal??" → "fiscal"
    3. OCR garbage symbols: "g<º£", "hi", ""º0¿—s"
    4. Isolated uppercase letters with tildes (Á, É, Í, Ó, Ú alone)
    5. Isolated single uppercase letters before words (L El, N sobre)
    6. Random symbols: >, <, |, combined like >'f-
    7. Symbols stuck to words: palabra>, texto<
    8. Extra spaces around dashes: 2009- 2012 → 2009-2012
    9. Extra spaces in middle of words (OCR artifacts)

    This is the final polish to remove all remaining OCR noise.
    """
    if not enabled:
        return data

    cleaned_data = []
    total_fixes = 0

    for entry in data:
        text = entry['text']
        original_text = text

        # Fix 1 (NEW): Remove footnote numbers attached to words
        # Pattern: word followed by ?XX (like ?78, ?27, etc.)
        # Example: "claves?78" → "claves"
        text = re.sub(r'([a-záéíóúñ]+)\?\d+', r'\1', text, flags=re.IGNORECASE)

        # Fix 2 (NEW): Remove multiple question marks attached to words
        # Pattern: word followed by ?? or ???
        # Example: "fiscal??" → "fiscal"
        text = re.sub(r'([a-záéíóúñ]+)\?{2,}', r'\1', text, flags=re.IGNORECASE)

        # Fix 2b (NEW): Remove single question mark attached to words (OCR artifacts)
        # This is aggressive but safe - Spanish questions use ¿?, so lone ? is always OCR noise
        # Pattern: word? followed by non-letter (space, punctuation, etc.) - but NOT at sentence end
        # Examples: "financiero? de" → "financiero de", "público?\"" → "público\"", "economía?-" → "economía-"
        # BUT preserve legitimate questions that end sentences (though rare in this corpus)

        # Remove ? when followed by lowercase letter (mid-sentence)
        text = re.sub(r'([a-záéíóúñ]+)\?(?=\s+[a-záéíóúñ])', r'\1', text, flags=re.IGNORECASE)
        # Remove ? when followed by common OCR punctuation artifacts (", -, *, etc.)
        text = re.sub(r'([a-záéíóúñ]+)\?(?=["\'\-\*,.:;])', r'\1', text, flags=re.IGNORECASE)
        # Remove ? when followed by newline or end of text (but not if preceded by ¿)
        text = re.sub(r'(?<!¿)([a-záéíóúñ]+)\?(?=\s*[\n])', r'\1', text, flags=re.IGNORECASE)
        # Remove ? followed by superscript numbers or other weird chars
        text = re.sub(r'([a-záéíóúñ]+)\?(?=[°º\*"\'\-\s]+[a-záéíóúñA-ZÁÉÍÓÚÑ])', r'\1', text, flags=re.IGNORECASE)
        # Remove ? followed by single letters (like "?s", "?n") - these are always OCR errors
        text = re.sub(r'([a-záéíóúñ]+)\?([a-záéíóúñ])\b', r'\1\2', text, flags=re.IGNORECASE)
        # Remove ? in footnote-like patterns: word?"., word?", word?" (common OCR footnote artifacts)
        # Handle both straight quotes (") and curly quotes (" " ' ')
        text = re.sub(r'([a-záéíóúñ]+)\?(?=[""\'\'\"])', r'\1', text, flags=re.IGNORECASE)
        # Remove ? before dash-number patterns: word?-16
        text = re.sub(r'([a-záéíóúñ]+)\?(?=-)', r'\1', text, flags=re.IGNORECASE)

        # Fix 3 (NEW): Remove OCR garbage symbols attached to words
        # Pattern: word followed by weird character combos: <º, °£, ¿—, etc.
        # Example: "texto<º£" → "texto", "palabra"º0¿—s" → "palabra"
        text = re.sub(r'([a-záéíóúñ]+)[<>°º£¿\-—\s]*[<>°º£¿\-—]+', r'\1', text, flags=re.IGNORECASE)

        # Fix 4 (NEW): Remove isolated weird character sequences
        # Pattern: standalone symbols like "g<º£", "hi" (single letters), ""º0¿—s"
        # These appear as OCR artifacts between words
        text = re.sub(r'\s+[<>°º£¿\-—]{2,}\s+', ' ', text)

        # Fix 5 (NEW): Remove single weird characters stuck to words
        # Example: "palabra%" → "palabra", "texto?" → "texto" (but preserve valid punctuation)
        text = re.sub(r'([a-záéíóúñ]+)[%<>°º£¿*]+(?=\s|$)', r'\1', text, flags=re.IGNORECASE)

        # Fix 6: Remove isolated uppercase letters with tildes (Ó alone, Ú alone)
        # Pattern: space + [ÁÉÍÓÚ] + space → just space
        text = re.sub(r'\s+[ÁÉÍÓÚ]\s+', ' ', text)

        # Fix 7: Remove isolated single uppercase letters before words
        # Pattern: \n\n[A-Z] word → \n\nword (except valid Roman numerals I, V, X)
        # Preserve: I, II, III, IV, V, VI, VII, VIII, IX, X
        def remove_isolated_letter(match):
            letter = match.group(1)
            word = match.group(2)
            # Keep Roman numerals
            if letter in ['I', 'V', 'X']:
                return match.group(0)
            # Remove other isolated letters
            return f'\n\n{word}'

        text = re.sub(r'\n\n([A-ZÁÉÍÓÚÑ])\s+([a-záéíóúñ]\w+)', remove_isolated_letter, text)

        # Fix 8: Remove random symbols: >, <, |, ^, ~
        # These are OCR artifacts that don't belong in Spanish text
        text = re.sub(r'[><\|^~]+', '', text)

        # Fix 9: Remove weird sequences like >'f-
        # Pattern: >', <', etc. followed by weird chars
        text = re.sub(r'[><][\'"][\w\-]*', '', text)

        # Fix 10: Fix extra spaces around dashes in year ranges
        # 2009- 2012 → 2009-2012
        text = re.sub(r'(\d{4})\s*-\s+(\d{4})', r'\1-\2', text)
        # Also fix: 8- 2016 → 8-2016
        text = re.sub(r'(\d+)\s*-\s+(\d{4})', r'\1-\2', text)

        # Fix 11: Normalize multiple spaces (should already be done, but just in case)
        text = re.sub(r' {2,}', ' ', text)

        # Fix 12: Clean up any remaining punctuation artifacts
        # Remove isolated dots, commas, etc. surrounded by spaces
        text = re.sub(r'\s+[.,;:]\s+', ' ', text)

        # Fix 13: Remove weird character sequences at word boundaries
        # Like: "texto�algo" → "textoalgo"
        text = re.sub(r'[�]+', '', text)

        # Fix 14: Clean up spacing around parentheses and brackets (if any remain)
        text = re.sub(r'\s+\)', ')', text)
        text = re.sub(r'\(\s+', '(', text)

        # Fix 15 (NEW): Remove trailing weird punctuation at end of paragraphs
        # Like "texto.!" → "texto."
        text = re.sub(r'\.([!?]+)(?=\n\n|$)', '.', text)

        # Count fixes
        if text != original_text:
            total_fixes += 1

        entry['text'] = text
        cleaned_data.append(entry)

    print(f"  Stage 7: Applied final OCR cleanup to {total_fixes} pages (enhanced footnote removal)")
    return cleaned_data


def main():
    """Run complete cleaning pipeline"""

    input_file = Path("data/raw/scanned_pdfs_extracted_text.json")
    output_file = Path("data/raw/scanned_pdfs_clean_extracted_text.json")

    print("\n" + "="*80)
    print("CLEANING SCANNED PDF EXTRACTED TEXT")
    print("="*80)
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    print(f"\nStages (in execution order - FALSE BREAKS FIRST, then HEADERS!):")
    print(f"  0. Preliminary cleaning (document IDs, OCR artifacts)")
    print(f"  1. Keyword filtering (FROM PAGE 2+, keep all if no keyword)")
    print(f"  2. Remove annexes (truncate at ANEXO pattern)")
    print(f"  3. Remove letter pages (Carta N* pattern)")
    print(f"  4. Remove false paragraph breaks (1st - BEFORE headers)")
    print(f"  5. Remove headers/titles (1st pass - improved detection)")
    print(f"  4. Remove false paragraph breaks (2nd - cleanup after headers)")
    print(f"  6. Aggressive cleaning (ultra conservative)")
    print(f"  4. Remove false paragraph breaks (3rd - cleanup after aggressive)")
    print(f"  7. Final OCR cleanup (la cereza del pastel)")
    print(f"  4. Remove false paragraph breaks (4th - cleanup after OCR)")
    print(f"  5. Remove headers/titles (REFUERZO - catch remaining headers)")
    print(f"  4. Remove false paragraph breaks (FINAL - absolute cleanup)")
    print("="*80)

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\nOriginal: {len(data)} pages")

    # Run stages in correct order (now function names match execution order!)
    # CRITICAL: Annexes (Stage 2) MUST run BEFORE headers (Stage 5)
    # Otherwise headers would remove "ANEXO:" before annexes can be truncated
    # CRITICAL: Stage 4 (false breaks) MUST run BEFORE Stage 5 (headers)
    # Otherwise text fragments like "situación actual\n\nde las finanzas" get mistaken as headers
    # CRITICAL: Stage 5 runs TWICE (once before aggressive cleaning, once after as REFUERZO)
    # This catches headers that were initially stuck to text but got separated after cleaning
    print("\nApplying cleaning stages...")
    # Execute stages in correct order
    data = stage0_preliminary_cleaning(data, enabled=True)
    data = stage1_filter_keywords(data, enabled=True)
    data = stage2_remove_annexes(data, enabled=True)
    data = stage3_remove_letter_pages(data, enabled=True)
    data = stage4_remove_false_paragraph_breaks(data, enabled=True)  # FIRST - join obvious false breaks
    data = stage5_remove_headers_and_titles(data, enabled=True)  # Remove headers (now well-formed)
    data = stage4_remove_false_paragraph_breaks(data, enabled=True)  # Clean up after header removal
    data = stage6_aggressive_cleaning(data, enabled=True)  # Remove noise paragraphs
    data = stage4_remove_false_paragraph_breaks(data, enabled=True)  # Clean up after aggressive
    data = stage7_final_ocr_cleanup(data, enabled=True)  # Final OCR cleanup
    data = stage4_remove_false_paragraph_breaks(data, enabled=True)  # Clean up after OCR
    data = stage5_remove_headers_and_titles(data, enabled=True)  # REFUERZO - catch remaining headers
    data = stage4_remove_false_paragraph_breaks(data, enabled=True)  # FINAL cleanup

    # Save
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Stats
    total_chars = sum(len(entry['text']) for entry in data)
    print("\n" + "="*80)
    print("CLEANING COMPLETE")
    print("="*80)
    print(f"Final: {len(data)} pages")
    print(f"Total characters: {total_chars:,}")
    print(f"\nOutput saved to: {output_file}")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
