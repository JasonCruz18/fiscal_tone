"""
Clean Extracted Text from Scanned PDFs

4-stage cleaning pipeline:
1. Filter by keywords (remove text before "Opinión del CF")
2. Remove annexes (truncate after "Anexo")
3. Remove letter pages (delete pages with "Carta")
4. Noise reduction (remove OCR artifacts)

Output: scanned_pdfs_clean_extracted_text.json
"""

import json
import re
from pathlib import Path
from tqdm import tqdm


def stage1_filter_keywords(data, enabled=True):
    """
    Stage 1: Remove all text before opinion keywords

    Searches from page 2+ for opinion keywords starting new paragraphs.
    When found, removes:
    - All text before the keyword in that page
    - All previous pages

    Args:
        data: List of dicts with pdf_filename, page, text
        enabled: Enable this stage

    Returns:
        Filtered data
    """
    if not enabled:
        return data

    # Opinion keywords to search for (as new paragraphs)
    opinion_keywords = [
        # Exact patterns found
        'Opinión del CF sobre el cumplimiento de las reglas fiscales',
        'Opinión del Consejo Fiscal sobre el Marco Macroeconómico',
        'Opinión de CF sobre las proyecciones contempladas',
        'Opinión de CF sobre el proyecto de DPME',
        'Opinión del CF sobre el nuevo Marco',

        # Generic patterns
        'Opinión del Consejo Fiscal',
        'Opinión del CF',
        'Opinión de CF',
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

        # Find first occurrence of opinion keyword (from page 2+)
        found_page = None
        found_pos = None
        found_keyword = None

        for entry in pages:
            if entry['page'] < 2:
                continue

            text = entry['text']

            # Search for keywords as new paragraphs
            for keyword in opinion_keywords:
                # Pattern: \n\n followed by keyword
                pattern = f'\n\n{keyword}'
                if pattern in text:
                    found_page = entry['page']
                    found_pos = text.find(pattern)
                    found_keyword = keyword
                    break

            if found_page:
                break

        # If found, filter pages
        if found_page:
            for entry in pages:
                if entry['page'] < found_page:
                    # Remove entire page
                    removed_pages += 1
                    removed_text_count += len(entry['text'])
                elif entry['page'] == found_page:
                    # Keep text from keyword onwards
                    original_text = entry['text']
                    pattern = f'\n\n{found_keyword}'
                    pos = original_text.find(pattern)

                    if pos != -1:
                        # Keep from keyword onwards (including the \n\n)
                        entry['text'] = original_text[pos:]
                        removed_text_count += pos

                    cleaned_data.append(entry)
                else:
                    # Keep entire page
                    cleaned_data.append(entry)
        else:
            # No keyword found, keep all pages
            cleaned_data.extend(pages)

    print(f"  Stage 1: Removed {removed_pages} pages, {removed_text_count:,} chars before opinion keywords")
    return cleaned_data


def stage2_remove_annexes(data, enabled=True):
    """
    Stage 2: Truncate text after "Anexo" or "ANEXO"

    Searches for variations: Anexo, ANEXO, ANEXO:, etc.
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

        # Find first occurrence of Anexo (case insensitive)
        found_page = None
        found_pos = None

        anexo_patterns = ['Anexo', 'ANEXO', 'ANEXO:', 'Anexo:', 'ANEXOS']

        for entry in pages:
            text = entry['text']

            # Check if starts with any Anexo pattern
            for pattern in anexo_patterns:
                if text.strip().startswith(pattern):
                    found_page = entry['page']
                    found_pos = 0
                    break

            if found_page:
                break

            # Check for \n\n + Anexo pattern
            for pattern in anexo_patterns:
                search_pattern = f'\n\n{pattern}'
                if search_pattern in text:
                    found_page = entry['page']
                    found_pos = text.find(search_pattern)
                    break

            if found_page:
                break

        # If found, truncate
        if found_page:
            for entry in pages:
                if entry['page'] < found_page:
                    # Keep entire page
                    cleaned_data.append(entry)
                elif entry['page'] == found_page:
                    # Truncate at Anexo
                    if found_pos == 0:
                        # Entire page is anexo, remove it
                        removed_pages += 1
                        removed_text_count += len(entry['text'])
                    else:
                        # Keep text before Anexo
                        original_text = entry['text']
                        entry['text'] = original_text[:found_pos].rstrip()
                        removed_text_count += len(original_text) - found_pos
                        cleaned_data.append(entry)
                else:
                    # Remove subsequent pages
                    removed_pages += 1
                    removed_text_count += len(entry['text'])
        else:
            # No anexo found, keep all
            cleaned_data.extend(pages)

    print(f"  Stage 2: Removed {removed_pages} pages after Anexo, {removed_text_count:,} chars truncated")
    return cleaned_data


def stage3_remove_letter_pages(data, enabled=True):
    """
    Stage 3: Remove pages containing "Carta"

    Searches for pattern like "Carta N* 015-2016-CF".
    Removes ONLY the page containing the letter.

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

    # Carta patterns (as new paragraph)
    carta_patterns = [
        r'\n\nCarta N[*°º]\s*\d+-\d+-CF',  # \n\nCarta N* 015-2016-CF
        r'\n\nCarta del Consejo Fiscal',
    ]

    for entry in data:
        text = entry['text']

        # Check if page contains carta pattern
        contains_carta = False
        for pattern in carta_patterns:
            if re.search(pattern, text):
                contains_carta = True
                break

        if contains_carta:
            # Remove this page
            removed_pages += 1
            removed_text_count += len(text)
        else:
            # Keep page
            cleaned_data.append(entry)

    print(f"  Stage 3: Removed {removed_pages} letter pages, {removed_text_count:,} chars")
    return cleaned_data


def stage4_aggressive_cleaning(data, enabled=True, min_paragraph_length=50):
    """
    Stage 4: Aggressive cleaning - Keep ONLY opinion paragraphs

    Removes:
    - Titles/headers (short lines with "Informe", "Opinión" at start)
    - Dates (Lima, dd de mes de año)
    - All-caps names/titles (WALDO MENDOZA, CONSEJO FISCAL)
    - Page numbers (1/2, 10/18, 1/, etc.)
    - Very short paragraphs (<min_paragraph_length chars)
    - Section headers (Conclusiones, Esquema fiscal, etc.)
    - Signatures (Presidente Consejo Fiscal, etc.)
    - OCR noise (solitary *, ?, !, parentheses, etc.)

    Strategy: Process paragraph by paragraph (split by \n\n), remove non-opinion paragraphs.

    Args:
        data: List of dicts with pdf_filename, page, text
        enabled: Enable this stage
        min_paragraph_length: Minimum chars for valid paragraph

    Returns:
        Aggressively cleaned data
    """
    if not enabled:
        return data

    total_chars_removed = 0
    total_paragraphs_removed = 0

    for entry in data:
        original_text = entry['text']

        # Split into paragraphs
        paragraphs = original_text.split('\n\n')
        cleaned_paragraphs = []

        for para in paragraphs:
            para = para.strip()

            if not para:
                continue

            # === REMOVAL RULES ===

            # Rule 1: Remove titles/headers (short, contains doc identifiers)
            if len(para) < 100:
                if any(keyword in para for keyword in ['Informe N*', 'Informe N°', 'INFORME', 'CF-', 'N*', 'N°']):
                    total_paragraphs_removed += 1
                    continue

            # Rule 2: Remove dates
            if re.search(r'Lima,\s+\d+\s+de\s+\w+\s+de\s+\d+', para):
                total_paragraphs_removed += 1
                continue

            # Rule 3: Remove all-caps names/titles (>50% uppercase letters)
            alpha_chars = [c for c in para if c.isalpha()]
            if alpha_chars:
                upper_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
                if upper_ratio > 0.5 and len(para) < 150:
                    total_paragraphs_removed += 1
                    continue

            # Rule 4: Remove page numbers (X/Y format)
            if re.fullmatch(r'\d+/\d+', para) or re.fullmatch(r'\d+/', para):
                total_paragraphs_removed += 1
                continue

            # Rule 5: Remove very short paragraphs (likely noise)
            if len(para) < min_paragraph_length:
                total_paragraphs_removed += 1
                continue

            # Rule 6: Remove section headers (short, title case, common keywords)
            if len(para) < 150:
                section_keywords = [
                    'Conclusiones', 'Conclusión', 'Introducción',
                    'Esquema fiscal', 'Marco', 'Contexto',
                    'Riesgos', 'Tendencias', 'Resumen',
                    'Antecedentes', 'Considerando'
                ]
                if any(para.strip().startswith(kw) for kw in section_keywords):
                    # Only remove if it's just the header (no content)
                    if len(para) < 100:
                        total_paragraphs_removed += 1
                        continue

            # Rule 7: Remove signatures/positions
            signature_keywords = [
                'Presidente Consejo Fiscal',
                'Presidente del Consejo Fiscal',
                'Vicepresidente',
                'PRESIDENTE DEL CONSEJO',
                'CONSEJO FISCAL DEL PERÚ'
            ]
            if any(kw in para for kw in signature_keywords) and len(para) < 100:
                total_paragraphs_removed += 1
                continue

            # === CLEANING (character-level) ===

            # Clean solitary parentheses
            para = re.sub(r'\(\s+', ' ', para)
            para = re.sub(r'\s+\)', ' ', para)

            # Clean excessive special chars
            para = re.sub(r'\s+\*\s+', ' ', para)
            para = re.sub(r'\*{2,}', '', para)
            para = re.sub(r'\?\s+([a-záéíóúñA-ZÁÉÍÓÚÑ])', r' \1', para)
            para = re.sub(r'!\s+([a-záéíóúñA-ZÁÉÍÓÚÑ])', r' \1', para)

            # Clean underscores and pipes
            para = re.sub(r'(?<!http)(?<!www)_+', ' ', para)
            para = re.sub(r'\|', '', para)

            # Clean standalone brackets
            para = re.sub(r'\[\s+', ' ', para)
            para = re.sub(r'\s+\]', ' ', para)

            # Clean excessive whitespace within paragraph
            para = re.sub(r' {2,}', ' ', para)
            para = para.strip()

            # Add to cleaned paragraphs if not empty after cleaning
            if para and len(para) >= min_paragraph_length:
                cleaned_paragraphs.append(para)
            else:
                total_paragraphs_removed += 1

        # Reconstruct text
        cleaned_text = '\n\n'.join(cleaned_paragraphs)

        total_chars_removed += len(original_text) - len(cleaned_text)
        entry['text'] = cleaned_text

    print(f"  Stage 4: Removed {total_paragraphs_removed} paragraphs, {total_chars_removed:,} chars")
    return data


def clean_scanned_text(input_json="data/raw/scanned_pdfs_extracted_text.json",
                       output_json="data/raw/scanned_pdfs_clean_extracted_text.json",
                       filter_keywords=True,
                       remove_annexes=True,
                       remove_letters=True,
                       reduce_noise=True):
    """
    Clean extracted text from scanned PDFs

    4-stage pipeline:
    1. Filter by keywords (remove before "Opinión del CF")
    2. Remove annexes (truncate after "Anexo")
    3. Remove letter pages (delete pages with "Carta")
    4. Noise reduction (remove OCR artifacts)

    Args:
        input_json: Input JSON file path
        output_json: Output JSON file path
        filter_keywords: Enable stage 1
        remove_annexes: Enable stage 2
        remove_letters: Enable stage 3
        reduce_noise: Enable stage 4

    Returns:
        Cleaned data with statistics
    """
    input_json = Path(input_json)
    output_json = Path(output_json)

    print(f"\n{'='*80}")
    print("CLEANING SCANNED TEXT")
    print('='*80)
    print(f"Input: {input_json}")
    print(f"Output: {output_json}")
    print(f"\nStages enabled:")
    print(f"  1. Filter keywords: {filter_keywords}")
    print(f"  2. Remove annexes: {remove_annexes}")
    print(f"  3. Remove letters: {remove_letters}")
    print(f"  4. Reduce noise: {reduce_noise}")
    print('='*80)

    # Load data
    with open(input_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\nOriginal data: {len(data)} pages")
    original_chars = sum(len(entry['text']) for entry in data)
    print(f"Original characters: {original_chars:,}")
    print()

    # Apply stages
    print("Applying cleaning stages...")
    data = stage1_filter_keywords(data, enabled=filter_keywords)
    data = stage2_remove_annexes(data, enabled=remove_annexes)
    data = stage3_remove_letter_pages(data, enabled=remove_letters)
    data = stage4_aggressive_cleaning(data, enabled=reduce_noise, min_paragraph_length=50)

    # Add statistics
    for entry in data:
        entry['original_length'] = original_chars // len(data)  # Approximation
        entry['cleaned_length'] = len(entry['text'])
        if entry['original_length'] > 0:
            entry['reduction_pct'] = (1 - entry['cleaned_length'] / entry['original_length']) * 100
        else:
            entry['reduction_pct'] = 0.0

    # Recalculate accurate original lengths
    # (This is approximate since we lost original data during filtering)
    with open(input_json, 'r', encoding='utf-8') as f:
        original_data = json.load(f)

    original_map = {(e['pdf_filename'], e['page']): len(e['text']) for e in original_data}

    for entry in data:
        key = (entry['pdf_filename'], entry['page'])
        if key in original_map:
            entry['original_length'] = original_map[key]
            if entry['original_length'] > 0:
                entry['reduction_pct'] = (1 - entry['cleaned_length'] / entry['original_length']) * 100
            else:
                entry['reduction_pct'] = 0.0

    # Save cleaned data
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n{'='*80}")
    print("CLEANING COMPLETE")
    print('='*80)
    print(f"Final data: {len(data)} pages")
    final_chars = sum(len(entry['text']) for entry in data)
    print(f"Final characters: {final_chars:,}")
    print(f"Total reduction: {original_chars - final_chars:,} chars ({(1 - final_chars/original_chars)*100:.1f}%)")

    # Count PDFs
    unique_pdfs = len(set(e['pdf_filename'] for e in data))
    print(f"Unique PDFs: {unique_pdfs}")

    print(f"\nOutput saved to: {output_json}")
    print('='*80)

    return data


if __name__ == "__main__":
    clean_scanned_text(
        input_json="data/raw/scanned_pdfs_extracted_text.json",
        output_json="data/raw/scanned_pdfs_clean_extracted_text.json",
        filter_keywords=True,
        remove_annexes=True,
        remove_letters=True,
        reduce_noise=True
    )
