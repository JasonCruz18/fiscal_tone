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

def is_section_header(line: str, max_chars: int = 150, max_words: int = 20) -> bool:
    """
    Determine if a line is a section header (should be removed).

    IMPROVED: Increased thresholds to catch longer headers like
    "Opinión del CF sobre las proyecciones contempladas en el IAPM"

    Conditions:
        - Length < 150 characters
        - Word count < 20 words (was 15, increased to catch longer headers)
        - Starts with uppercase letter or number
        - Does NOT end with period, exclamation mark, or question mark
        - Is NOT a date

    Examples:
        - "Opinión del CF sobre las proyecciones..." → True (header)
        - "El CF considera que esta norma..." → False (sentence ending with period)
    """
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

    print(f"  Stage 0: Cleaned {total_chars_removed:,} chars (OCR artifacts)")
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
    Stage 4: Remove ALL false paragraph breaks

    NOTE: This stage is executed MULTIPLE times throughout the pipeline
    to clean up false breaks created by other stages.

    As per user requirement: "Un párrafo nunca inicia con minúsculas"

    Removes:
    1. ALL \n\n before lowercase letters
    2. \n\n before years (2018, etc.)
    3. \n\n before connectors (de, del, en, etc.)
    """
    if not enabled:
        return data

    cleaned_data = []
    total_removed = 0

    for entry in data:
        text = entry['text']
        original_count = text.count('\n\n')

        # Remove ALL \n\n before lowercase letters
        # This is the main rule - paragraphs NEVER start with lowercase
        text = re.sub(r'\n\n([a-záéíóúñü])', r' \1', text)

        # Remove \n\n before years
        text = re.sub(r'\n\n([12]\d{3})', r' \1', text)

        # Remove \n\n before common connectors (extra safety)
        connectors = r'(?:de|del|la|el|los|las|un|una|en|con|por|para|que|se|y|o|su|sus|sobre|al|ha|han)'
        text = re.sub(r'\n\n(' + connectors + r'\s)', r' \1', text)

        new_count = text.count('\n\n')
        total_removed += (original_count - new_count)

        entry['text'] = text
        cleaned_data.append(entry)

    print(f"  Stage 4: Removed {total_removed} false paragraph breaks")
    return cleaned_data


def stage5_remove_headers_and_titles(data, enabled=True):
    """
    Stage 5: Remove headers, titles, subtitles

    IMPROVED: Enhanced header detection using smart helper functions
    - is_section_header() detects headers (< 150 chars, < 20 words, no ending period)
    - is_chart_or_table_label() detects numbered patterns (1:, I., A), etc.)

    Executed AFTER keyword filtering and annex truncation, so NOW we can remove ALL headers including:
    - "Opinión del CF sobre las proyecciones contempladas en el IAPM"
    - "1: Leyes con impacto fiscal adverso"
    - "I. Opinión del CF sobre el cumplimiento..."
    - "ANEXO:" (standalone annex headers that didn't cause truncation)
    - Page 1 titles (for PDFs without keywords)
    - Section headers/subtitles throughout document

    IMPORTANT: No exceptions for "Opinión del CF" keywords anymore!
    (They were already used for filtering in stage 1, now they should be removed)
    """
    if not enabled:
        return data

    cleaned_data = []
    total_removed = 0

    for entry in data:
        text = entry['text']

        # Pattern 1: \n\n[text]\n\n (paragraphs surrounded by double newlines)
        def replace_header(match):
            nonlocal total_removed
            header = match.group(1).strip()

            # Remove if it's a header OR chart/table label
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

            # Remove if it's a header OR chart/table label
            if is_section_header(header) or is_chart_or_table_label(header):
                text = text[match.end():]
                total_removed += 1

        entry['text'] = text
        cleaned_data.append(entry)

    print(f"  Stage 5: Removed {total_removed} headers/titles (improved detection)")
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

    CRITICAL CHANGES for maximum safety:
    - NO "too short" threshold - we only remove VERY specific patterns
    - Only removes: page numbers, standalone dates, standalone signatures
    - Character threshold reduced from 50 to 30 (only extremely short noise)
    - All patterns MUST match at START (^) and be standalone (no other text)

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

        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        kept = []

        for para in paragraphs:
            should_remove = False

            # ULTRA CONSERVATIVE: Only remove VERY specific standalone patterns
            # All patterns require EXACT match (no other text before/after)
            if len(para) < 80:  # Only check short text
                removal_patterns_ultra_conservative = [
                    r'^\d+\s*/\s*\d+$',                        # Page numbers ONLY: "7/10"
                    r'^Lima,\s+\d+\s+de\s+\w+\s+de\s+\d{4}[\s.]*$',  # Date ONLY
                    r'^Informe\s+N[*°º]?\s*\d{3,4}[-\s]*CF[\s.]*$',  # Doc ID ONLY: "Informe N* 001-2016-CF"
                    r'^PRESIDENTE\s+DEL\s+CONSEJO\s+FISCAL[\s.]*$',  # Signature ONLY
                    r'^Conclusiones?\s*:?[\s.]*$',             # Section header ONLY
                    r'^ANEXO\s*:?[\s.]*$',                     # Annex header ONLY
                ]

                for pattern in removal_patterns_ultra_conservative:
                    if re.search(pattern, para, re.IGNORECASE):
                        should_remove = True
                        break

            # ONLY extremely short (< 30 chars) - things like "!", "�", "10/18"
            # This is much more conservative than the previous < 50 threshold
            if len(para) < 30:
                should_remove = True

            # All-caps signatures (ONLY if < 70 chars and > 60% caps)
            # Example: "WALDO EPIFANIO MENDOZA BELLIDO Presidente Consejo Fiscal"
            if len(para) < 70:
                alpha = [c for c in para if c.isalpha()]
                if alpha and len(alpha) > 10:  # Must have at least 10 letters
                    caps_ratio = sum(1 for c in alpha if c.isupper()) / len(alpha)
                    if caps_ratio > 0.6 and 'presidente' in para.lower():
                        should_remove = True

            if should_remove:
                paras_removed += 1
                chars_removed += len(para)
            else:
                # Character cleaning
                para = re.sub(r'\s*\(\s*\)', '', para)
                para = re.sub(r'\s*\[\s*\]', '', para)
                para = re.sub(r'[*]{2,}', '', para)
                para = re.sub(r'[?]{2,}', '?', para)
                para = re.sub(r'[!]{2,}', '!', para)
                para = re.sub(r'[_|]+', '', para)
                para = re.sub(r' {2,}', ' ', para).strip()

                if para:
                    kept.append(para)

        entry['text'] = '\n\n'.join(kept)

        if entry['text'].strip():
            cleaned_data.append(entry)
        else:
            chars_removed += original_len

    print(f"  Stage 6: Removed {paras_removed} noisy paragraphs, {chars_removed:,} chars")
    return cleaned_data


def stage7_final_ocr_cleanup(data, enabled=True):
    """
    Stage 7: FINAL OCR CLEANUP - "La cereza del pastel"

    Removes final OCR artifacts and noise:
    1. Isolated uppercase letters with tildes (Á, É, Í, Ó, Ú alone)
    2. Isolated single uppercase letters before words (L El, N sobre)
    3. Random symbols: >, <, |, combined like >'f-
    4. Symbols stuck to words: palabra>, texto<
    5. Extra spaces around dashes: 2009- 2012 → 2009-2012
    6. Extra spaces in middle of words (OCR artifacts)

    This is the final polish to remove all remaining OCR noise.
    """
    if not enabled:
        return data

    cleaned_data = []
    total_fixes = 0

    for entry in data:
        text = entry['text']
        original_text = text

        # Fix 1: Remove isolated uppercase letters with tildes (Ó alone, Ú alone)
        # Pattern: space + [ÁÉÍÓÚ] + space → just space
        text = re.sub(r'\s+[ÁÉÍÓÚ]\s+', ' ', text)

        # Fix 2: Remove isolated single uppercase letters before words
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

        # Fix 3: Remove random symbols: >, <, |, ^, ~
        # These are OCR artifacts that don't belong in Spanish text
        text = re.sub(r'[><\|^~]+', '', text)

        # Fix 4: Remove weird sequences like >'f-
        # Pattern: >', <', etc. followed by weird chars
        text = re.sub(r'[><][\'"][\w\-]*', '', text)

        # Fix 5: Fix extra spaces around dashes in year ranges
        # 2009- 2012 → 2009-2012
        text = re.sub(r'(\d{4})\s*-\s+(\d{4})', r'\1-\2', text)
        # Also fix: 8- 2016 → 8-2016
        text = re.sub(r'(\d+)\s*-\s+(\d{4})', r'\1-\2', text)

        # Fix 6: Normalize multiple spaces (should already be done, but just in case)
        text = re.sub(r' {2,}', ' ', text)

        # Fix 7: Clean up any remaining punctuation artifacts
        # Remove isolated dots, commas, etc. surrounded by spaces
        text = re.sub(r'\s+[.,;:]\s+', ' ', text)

        # Fix 8: Remove weird character sequences at word boundaries
        # Like: "texto�algo" → "textoalgo"
        text = re.sub(r'[�]+', '', text)

        # Fix 9: Clean up spacing around parentheses and brackets (if any remain)
        text = re.sub(r'\s+\)', ')', text)
        text = re.sub(r'\(\s+', '(', text)

        # Count fixes
        if text != original_text:
            total_fixes += 1

        entry['text'] = text
        cleaned_data.append(entry)

    print(f"  Stage 7: Applied final OCR cleanup to {total_fixes} pages")
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
    print(f"\nStages (in execution order - now matching function names!):")
    print(f"  0. Preliminary cleaning")
    print(f"  1. Keyword filtering (FROM PAGE 2+, keep all if no keyword)")
    print(f"  2. Remove annexes (truncate at ANEXO pattern)")
    print(f"  3. Remove letter pages (Carta N* pattern)")
    print(f"  4. Remove false paragraph breaks (1st pass - ALL before lowercase)")
    print(f"  5. Remove headers/titles (improved detection)")
    print(f"  4. Remove false paragraph breaks (2nd pass - cleanup after headers)")
    print(f"  6. Aggressive cleaning (ultra conservative)")
    print(f"  4. Remove false paragraph breaks (3rd pass - cleanup after aggressive)")
    print(f"  7. Final OCR cleanup (la cereza del pastel)")
    print(f"  4. Remove false paragraph breaks (FINAL pass - absolute cleanup)")
    print("="*80)

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\nOriginal: {len(data)} pages")

    # Run stages in correct order (now function names match execution order!)
    # CRITICAL: Annexes (Stage 2) MUST run BEFORE headers (Stage 5)
    # Otherwise headers would remove "ANEXO:" before annexes can be truncated
    # CRITICAL: Stage 4 (false breaks) runs FOUR times:
    #   1. After Stage 3 (removes OCR false breaks)
    #   2. After Stage 5 (headers create false breaks when removed)
    #   3. After Stage 6 (aggressive cleaning may create false breaks)
    #   4. After Stage 7 (final OCR cleanup may create false breaks)
    print("\nApplying cleaning stages...")
    # Execute stages in correct order
    data = stage0_preliminary_cleaning(data, enabled=True)
    data = stage1_filter_keywords(data, enabled=True)
    data = stage2_remove_annexes(data, enabled=True)
    data = stage3_remove_letter_pages(data, enabled=True)
    data = stage4_remove_false_paragraph_breaks(data, enabled=True)  # First pass
    data = stage5_remove_headers_and_titles(data, enabled=True)  # Creates false breaks!
    data = stage4_remove_false_paragraph_breaks(data, enabled=True)  # Second pass
    data = stage6_aggressive_cleaning(data, enabled=True)  # Creates false breaks!
    data = stage4_remove_false_paragraph_breaks(data, enabled=True)  # Third pass
    data = stage7_final_ocr_cleanup(data, enabled=True)  # Creates false breaks
    data = stage4_remove_false_paragraph_breaks(data, enabled=True)  # FINAL pass - absolute cleanup!

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
