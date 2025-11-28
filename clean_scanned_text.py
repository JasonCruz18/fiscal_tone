"""
Clean Extracted Text from Scanned PDFs

Enhanced 6-stage cleaning pipeline:
0. Preliminary text normalization (spaces, OCR artifacts)
1. Filter by keywords (remove text before "Opinión del CF") - ROBUST implementation
2. Remove false paragraph breaks (\n\n before lowercase, years, etc.)
3. Remove headers/titles (short text surrounded by \n\n)
4. Remove annexes (truncate after "Anexo")
5. Remove letter pages (delete pages with "Carta")
6. Aggressive noise reduction (remove OCR artifacts, page numbers, etc.)

Output: scanned_pdfs_clean_extracted_text.json
"""

import json
import re
from pathlib import Path
from tqdm import tqdm


def stage0_preliminary_cleaning(data, enabled=True):
    """
    Stage 0: Preliminary text normalization

    Cleans common OCR artifacts and spacing issues:
    - Removes extra spaces before punctuation (" <", " ;", " :", " ?", " !", etc.)
    - Normalizes multiple spaces to single space
    - Removes spaces before/after newlines
    - Removes trailing/leading whitespace per page

    Args:
        data: List of dicts with pdf_filename, page, text
        enabled: Enable this stage

    Returns:
        Cleaned data
    """
    if not enabled:
        return data

    cleaned_data = []
    total_chars_removed = 0

    for entry in data:
        text = entry['text']
        original_length = len(text)

        # Remove spaces before punctuation and special characters
        # Common OCR artifacts: " <", " >", " ;", " :", " ?", " !", " ,", " .", " )", " ]", " }"
        text = re.sub(r' +([<>;:?!,.\)\]\}])', r'\1', text)

        # Remove spaces after opening brackets/parentheses
        text = re.sub(r'([\(\[\{]) +', r'\1', text)

        # Normalize multiple spaces to single space (except in \n\n)
        text = re.sub(r'(?<!\n) {2,}(?!\n)', ' ', text)

        # Remove spaces before/after newlines (but preserve \n\n)
        text = re.sub(r' +\n', '\n', text)  # Space before newline
        text = re.sub(r'\n +', '\n', text)  # Space after newline (except for intentional indentation)

        # Remove trailing/leading whitespace
        text = text.strip()

        entry['text'] = text
        total_chars_removed += (original_length - len(text))
        cleaned_data.append(entry)

    print(f"  Stage 0: Cleaned {total_chars_removed:,} chars (extra spaces, OCR artifacts)")
    return cleaned_data


def stage1_filter_keywords(data, enabled=True):
    """
    Stage 1: ROBUST keyword filtering - Remove all text before opinion keywords

    Uses regex patterns matching editable PDF strategy:
    - Searches from page 1+ (not just 2+)
    - Patterns: "Opinión del Consejo Fiscal", "Opinión del CF", "Opinión de CF"
    - Supports optional numbering: "I. Opinión...", "1. Opinión...", etc.
    - Searches both at page start AND with \n\n prefix
    - Removes ALL text before FIRST valid occurrence (including previous pages)

    Critical: This ensures ONLY Fiscal Council opinions remain, excluding
    summaries, legal content, and other preliminary text.

    Args:
        data: List of dicts with pdf_filename, page, text
        enabled: Enable this stage

    Returns:
        Filtered data with text before opinion keywords removed
    """
    if not enabled:
        return data

    # Regex patterns matching editable PDF strategy (data_curation.py:1175-1178)
    # Pattern explanation:
    # - (?:(?:\d+|[IVX]+)\.?\s*)? : Optional number (Arabic/Roman) with optional dot and spaces
    # - Opinión del? : "Opinión del" or "Opinión de"
    # - Consejo Fiscal|CF : Either full name or abbreviation
    # - \b : Word boundary (ensures "CF" doesn't match "CFO")
    opinion_patterns = [
        r'(?:(?:\d+|[IVX]+)\.?\s*[—\-]?\s*)?Opinión del? Consejo Fiscal\b',  # "Opinión del Consejo Fiscal", "I. Opinión...", etc.
        r'(?:(?:\d+|[IVX]+)\.?\s*[—\-]?\s*)?Opinión del? CF\b',               # "Opinión del CF", "1. Opinión de CF", etc.
    ]

    cleaned_data = []
    removed_pages = 0
    removed_text_count = 0

    # Group by PDF
    pdf_groups = {}
    for entry in data:
        pdf = entry['pdf_filename']
        if pdf not in pdf_groups:
            pdf_groups[pdf] = []
        pdf_groups[pdf].append(entry)

    # Process each PDF
    for pdf_name, pages in pdf_groups.items():
        # Sort by page number
        pages = sorted(pages, key=lambda x: x['page'])

        # Find FIRST valid opinion keyword across ALL pages
        found_page = None
        found_pos = None
        found_pattern = None

        for entry in pages:
            text = entry['text']

            # Search for keywords in two locations:
            # 1. At page start (after optional whitespace)
            # 2. After \n\n (new paragraph marker)

            for pattern in opinion_patterns:
                # Check at page start
                match_start = re.search(r'^\s*' + pattern, text)
                if match_start:
                    found_page = entry['page']
                    found_pos = match_start.start()
                    found_pattern = pattern
                    break

                # Check after \n\n (new paragraph)
                match_paragraph = re.search(r'\n\n\s*' + pattern, text)
                if match_paragraph:
                    found_page = entry['page']
                    found_pos = match_paragraph.start()
                    found_pattern = pattern
                    break

            if found_page:
                break

        # Apply filtering based on found keyword
        if found_page:
            for entry in pages:
                if entry['page'] < found_page:
                    # Remove entire page (before keyword page)
                    removed_pages += 1
                    removed_text_count += len(entry['text'])
                elif entry['page'] == found_page:
                    # Keep text from keyword onwards (including the paragraph marker)
                    original_text = entry['text']

                    # Re-search to find exact position
                    match_start = re.search(r'^\s*' + found_pattern, original_text)
                    match_para = re.search(r'\n\n\s*' + found_pattern, original_text)

                    if match_start:
                        # Found at start - keep from there
                        entry['text'] = original_text[match_start.start():]
                        removed_text_count += match_start.start()
                    elif match_para:
                        # Found after \n\n - keep from the \n\n onwards
                        entry['text'] = original_text[match_para.start():]
                        removed_text_count += match_para.start()

                    cleaned_data.append(entry)
                else:
                    # Keep entire page (after keyword page)
                    cleaned_data.append(entry)
        else:
            # No keyword found - keep all pages (might be special document format)
            print(f"    ⚠️ WARNING: No opinion keyword found in {pdf_name} - keeping all pages")
            cleaned_data.extend(pages)

    print(f"  Stage 1: Removed {removed_pages} pages, {removed_text_count:,} chars before opinion keywords")
    return cleaned_data


def stage2_remove_false_paragraph_breaks(data, enabled=True):
    """
    Stage 2: Remove false paragraph breaks (\n\n before lowercase/years)

    Identifies and removes erroneous \n\n markers from OCR that indicate
    fake paragraph starts:

    1. \n\n before lowercase letter (continuation of paragraph)
       Example: "...del Consejo Fiscal \n\nque se enfoca en..." → remove \n\n

    2. \n\n before 4-digit years
       Example: "...durante el año \n\n2018" → remove \n\n

    3. \n\n before short connecting words/prepositions
       Example: "...finanzas públicas \n\nde las entidades" → remove \n\n

    Strategy: Replace false \n\n with single space while preserving
    true paragraph breaks (before uppercase letters).

    Args:
        data: List of dicts with pdf_filename, page, text
        enabled: Enable this stage

    Returns:
        Data with false paragraph breaks removed
    """
    if not enabled:
        return data

    cleaned_data = []
    total_breaks_removed = 0

    for entry in data:
        text = entry['text']
        original_count = text.count('\n\n')

        # STEP 1: Remove \n\n in middle of split words (OCR artifact) - MOST SPECIFIC
        # Pattern: word ending + \n\n + word starting with lowercase (likely continuation)
        # Example: "respectiva\n\nprobabilidad" → "respectiva probabilidad"
        # Example: "requerimiento\n\nfinanciero" → "requerimiento financiero"
        # Apply if: previous char is letter AND next word is 3-30 lowercase letters
        text = re.sub(r'([a-záéíóúñü])\n\n([a-záéíóúñü]{3,30})(?=[\s,.\)])', r'\1 \2', text)

        # STEP 2: Remove \n\n before connecting words/articles (common in Spanish)
        # These prepositions/articles/conjunctions never start paragraphs
        connectors = r'(?:de|del|la|el|los|las|un|una|en|con|por|para|que|se|y|o|su|sus|sobre|al|ha|han)'
        text = re.sub(r'\n\n(' + connectors + r'\s)', r' \1', text)

        # STEP 3: Remove \n\n before 4-digit years
        # Pattern: \n\n followed by 4 digits (1900-2099)
        text = re.sub(r'\n\n([12]\d{3})', r' \1', text)

        # NOTE: We do NOT remove all \n\n before lowercase letters because that's too aggressive
        # Some paragraphs legitimately start with lowercase (lists, continuations, etc.)

        new_count = text.count('\n\n')
        breaks_removed = original_count - new_count
        total_breaks_removed += breaks_removed

        entry['text'] = text
        cleaned_data.append(entry)

    print(f"  Stage 2: Removed {total_breaks_removed} false paragraph breaks")
    return cleaned_data


def stage3_remove_headers_and_titles(data, enabled=True):
    """
    Stage 3: Remove headers, titles, and subtitles

    Detects and removes short text blocks that are section headers/titles,
    identified by being surrounded by \n\n markers within a short distance:

    Pattern: \n\n[SHORT TEXT]\n\n

    Examples to remove:
    - "\n\nLos riesgos para la consolidación fiscal\n\n"
    - "Opinión del CF sobre el cumplimiento de las reglas fiscales\n\n"
    - "\n\nÍndices de precios de minerales\n\n"

    Strategy:
    1. Find text between \n\n...\n\n
    2. If length < threshold (default 120 chars ~2-3 lines)
    3. Remove the header but keep ONE \n\n for the following paragraph

    Special case: Headers at page start (no leading \n\n)
    - Pattern: ^[SHORT TEXT]\n\n at beginning of page

    Args:
        data: List of dicts with pdf_filename, page, text
        enabled: Enable this stage
        max_header_length: Maximum character count for text to be considered header

    Returns:
        Data with headers/titles removed
    """
    if not enabled:
        return data

    cleaned_data = []
    total_headers_removed = 0
    max_header_length = 120  # ~2-3 lines of text

    for entry in data:
        text = entry['text']

        # Pattern 1: \n\n[short text]\n\n (headers in middle of text)
        # Use regex to find and remove short blocks between double newlines
        def replace_header(match):
            nonlocal total_headers_removed
            header_text = match.group(1)

            # CRITICAL: DO NOT remove headers containing opinion keywords
            # These mark the start of CF opinions and must be preserved
            if 'Opinión del CF' in header_text or 'Opinión del Consejo Fiscal' in header_text or 'Opinión de CF' in header_text:
                return match.group(0)  # Keep as-is

            # Only remove if short enough to be header
            if len(header_text) <= max_header_length:
                total_headers_removed += 1
                return '\n\n'  # Keep one \n\n for following paragraph
            else:
                return match.group(0)  # Keep as-is if too long

        text = re.sub(r'\n\n(.+?)\n\n', replace_header, text, flags=re.DOTALL)

        # Pattern 2: ^[short text]\n\n (headers at page start)
        # Match from start of string to first \n\n
        match_start_header = re.match(r'^(.+?)\n\n', text, flags=re.DOTALL)
        if match_start_header:
            header_text = match_start_header.group(1)

            # DO NOT remove if contains opinion keywords
            if 'Opinión del CF' in header_text or 'Opinión del Consejo Fiscal' in header_text or 'Opinión de CF' in header_text:
                pass  # Keep as-is
            elif len(header_text) <= max_header_length:
                # Remove header, keep \n\n for following paragraph
                text = text[match_start_header.end(1):]  # Keep the \n\n
                total_headers_removed += 1

        entry['text'] = text
        cleaned_data.append(entry)

    print(f"  Stage 3: Removed {total_headers_removed} headers/titles")
    return cleaned_data


def stage4_remove_annexes(data, enabled=True):
    """
    Stage 4: Truncate text after "Anexo" or "ANEXO"

    Searches for variations: Anexo, ANEXO, ANEXO:, Anexo:, ANEXOS
    Removes all text after first occurrence within each PDF.

    Args:
        data: List of dicts with pdf_filename, page, text
        enabled: Enable this stage

    Returns:
        Filtered data
    """
    if not enabled:
        return data

    cleaned_data = []
    removed_pages = 0
    removed_text_count = 0

    # Group by PDF
    pdf_groups = {}
    for entry in data:
        pdf = entry['pdf_filename']
        if pdf not in pdf_groups:
            pdf_groups[pdf] = []
        pdf_groups[pdf].append(entry)

    # Process each PDF
    for pdf_name, pages in pdf_groups.items():
        # Sort by page number
        pages = sorted(pages, key=lambda x: x['page'])

        # Find first annexe occurrence
        anexo_patterns = ['ANEXO:', 'ANEXOS', 'ANEXO', 'Anexo:', 'Anexos', 'Anexo']
        found_page = None
        found_at_start = False

        for entry in pages:
            text = entry['text']

            # Check if page STARTS with anexo pattern (after optional whitespace/newlines)
            for pattern in anexo_patterns:
                if re.match(r'^[\s\n]*' + re.escape(pattern), text):
                    found_page = entry['page']
                    found_at_start = True
                    break

                # Check for \n\n + pattern (anexo as new section)
                if f'\n\n{pattern}' in text:
                    found_page = entry['page']
                    found_at_start = False
                    break

            if found_page:
                break

        # Filter based on anexo occurrence
        if found_page:
            for entry in pages:
                if entry['page'] < found_page:
                    cleaned_data.append(entry)
                elif entry['page'] == found_page:
                    if found_at_start:
                        # Entire page is anexo - remove it
                        removed_pages += 1
                        removed_text_count += len(entry['text'])
                    else:
                        # Truncate at anexo position
                        text = entry['text']
                        truncate_pos = None
                        for pattern in anexo_patterns:
                            pos = text.find(f'\n\n{pattern}')
                            if pos != -1:
                                truncate_pos = pos
                                break

                        if truncate_pos:
                            removed_text_count += len(text) - truncate_pos
                            entry['text'] = text[:truncate_pos]
                            if entry['text'].strip():  # Only keep if not empty
                                cleaned_data.append(entry)
                            else:
                                removed_pages += 1
                else:
                    # Remove all pages after anexo
                    removed_pages += 1
                    removed_text_count += len(entry['text'])
        else:
            # No anexo found - keep all
            cleaned_data.extend(pages)

    print(f"  Stage 4: Removed {removed_pages} pages, {removed_text_count:,} chars (annexes)")
    return cleaned_data


def stage5_remove_letter_pages(data, enabled=True):
    """
    Stage 5: Remove pages containing "Carta N*" pattern

    Args:
        data: List of dicts with pdf_filename, page, text
        enabled: Enable this stage

    Returns:
        Filtered data
    """
    if not enabled:
        return data

    cleaned_data = []
    removed_pages = 0
    removed_text_count = 0

    for entry in data:
        text = entry['text']

        # Check for "Carta" pattern (case insensitive)
        if re.search(r'Carta\s+N[*°º]?\s*\d', text, re.IGNORECASE):
            removed_pages += 1
            removed_text_count += len(text)
        else:
            cleaned_data.append(entry)

    print(f"  Stage 5: Removed {removed_pages} letter pages ({removed_text_count:,} chars)")
    return cleaned_data


def stage6_aggressive_cleaning(data, enabled=True, min_paragraph_length=50):
    """
    Stage 6: Aggressive paragraph-level noise reduction

    Processes each paragraph (split by \n\n) and removes:
    1. Titles/headers containing document names (Informe N*, CF-, etc.)
    2. Dates (Lima, dd de mes de año)
    3. All-caps names (>50% uppercase - likely names like WALDO MENDOZA)
    4. Page numbers (X/Y format)
    5. Very short paragraphs (<min_paragraph_length chars)
    6. Section headers (Conclusiones, Esquema fiscal, etc.)
    7. Signatures (Presidente Consejo Fiscal, etc.)

    Character-level cleaning:
    - Remove solitary parentheses/brackets
    - Clean excessive special characters (*, ?, !, etc.)
    - Remove underscores and pipes

    Args:
        data: List of dicts with pdf_filename, page, text
        enabled: Enable this stage
        min_paragraph_length: Minimum characters for valid paragraph

    Returns:
        Cleaned data
    """
    if not enabled:
        return data

    cleaned_data = []
    paragraphs_removed = 0
    chars_removed = 0

    # Removal patterns (case-insensitive)
    removal_patterns = [
        r'Informe\s+N[*°º]?\s*\d',  # Informe N* 001-2018
        r'CF[-\s]*\d',               # CF-2018, CF 001
        r'Lima,\s+\d+\s+de\s+\w+\s+de\s+\d{4}',  # Lima, 24 de enero de 2018
        r'\d+\s*/\s*\d+',            # Page numbers: 5/10
        r'Presidente.*Consejo Fiscal',  # Signatures
        r'Conclusiones?\s*:?$',      # Section headers
        r'Esquema\s+[Ff]iscal',
        r'Consejo\s+Fiscal\s*:?$',
    ]

    for entry in data:
        text = entry['text']
        original_len = len(text)

        # Split into paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        kept_paragraphs = []
        for para in paragraphs:
            # Check removal conditions
            should_remove = False

            # 1. Check against removal patterns
            for pattern in removal_patterns:
                if re.search(pattern, para, re.IGNORECASE):
                    should_remove = True
                    break

            # 2. Too short
            if len(para) < min_paragraph_length:
                should_remove = True

            # 3. All-caps names (>50% uppercase letters)
            alpha_chars = [c for c in para if c.isalpha()]
            if alpha_chars:
                uppercase_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
                if uppercase_ratio > 0.5 and len(para) < 100:  # Short all-caps text
                    should_remove = True

            if should_remove:
                paragraphs_removed += 1
                chars_removed += len(para)
            else:
                # Character-level cleaning
                para_clean = para

                # Remove solitary parentheses/brackets
                para_clean = re.sub(r'\s*\(\s*\)', '', para_clean)
                para_clean = re.sub(r'\s*\[\s*\]', '', para_clean)

                # Clean excessive special characters
                para_clean = re.sub(r'[*]{2,}', '', para_clean)
                para_clean = re.sub(r'[?]{2,}', '?', para_clean)
                para_clean = re.sub(r'[!]{2,}', '!', para_clean)

                # Remove underscores and pipes
                para_clean = re.sub(r'[_|]+', '', para_clean)

                # Normalize spaces after cleaning
                para_clean = re.sub(r' {2,}', ' ', para_clean).strip()

                if para_clean:  # Only keep non-empty
                    kept_paragraphs.append(para_clean)

        # Rejoin paragraphs
        entry['text'] = '\n\n'.join(kept_paragraphs)

        # Only keep entry if text remains
        if entry['text'].strip():
            cleaned_data.append(entry)
        else:
            # Entire page was noise
            chars_removed += original_len

    print(f"  Stage 6: Removed {paragraphs_removed} noisy paragraphs, {chars_removed:,} chars")
    return cleaned_data


def main():
    """Run complete cleaning pipeline"""

    # Paths
    input_file = Path("data/raw/scanned_pdfs_extracted_text.json")
    output_file = Path("data/raw/scanned_pdfs_clean_extracted_text.json")

    # Load data
    print("\n" + "="*80)
    print("CLEANING SCANNED PDF EXTRACTED TEXT")
    print("="*80)
    print(f"Input:  {input_file}")
    print(f"Output: {output_file}")
    print(f"\nStages:")
    print(f"  0. Preliminary cleaning: True")
    print(f"  1. Keyword filtering: True")
    print(f"  2. False paragraph breaks: True")
    print(f"  3. Headers/titles: True")
    print(f"  4. Annexes: True")
    print(f"  5. Letter pages: True")
    print(f"  6. Aggressive cleaning: True")
    print("="*80)

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\nOriginal: {len(data)} pages")

    # Run stages
    print("\nApplying cleaning stages...")
    data = stage0_preliminary_cleaning(data, enabled=True)
    data = stage1_filter_keywords(data, enabled=True)
    data = stage2_remove_false_paragraph_breaks(data, enabled=True)
    data = stage3_remove_headers_and_titles(data, enabled=True)
    data = stage4_remove_annexes(data, enabled=True)
    data = stage5_remove_letter_pages(data, enabled=True)
    data = stage6_aggressive_cleaning(data, enabled=True)

    # Save results
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Final stats
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
