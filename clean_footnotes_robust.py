"""
Robust Footnote Cleaner for Extracted OCR Text

Based on analysis of real extracted text patterns from 93 pages
"""

import re
import json
from pathlib import Path
from tqdm import tqdm


def detect_footnote_start(lines):
    """
    Detect where footnotes begin in the text

    Returns: Index of first footnote line (or len(lines) if no footnotes found)
    """

    # Pattern 1: Lines starting with footnote markers
    # OCR recognizes: !, ?, *, $, or numbers followed by space
    footnote_marker_pattern = r'^\s*[!?*$0-9]+\s+'

    # Pattern 2: Common footnote start phrases
    footnote_phrases = [
        r'^La opinión del Consejo Fiscal',
        r'^En este documento',
        r'^De acuerdo al',
        r'^De acuerdo con',
        r'^El Artículo \d+',
        r'^Para determinar',
        r'^Se considera',
        r'^Por intermedio de',
        r'^Mediante',
        r'^Como el impuesto',
        r'^En el periodo \d+',
        r'^Fuente:',
        r'^Crecimiento promedio',
        r'^\(dem\.',
        r'^Ídem',
        r'^Según el numeral',
        r'^Específicamente',
        r'^La desviación estándar',
        r'^Promedio entre',
        r'^Con cifras preliminares',
    ]

    # Pattern 3: Legal references
    legal_patterns = [
        r'Ley N[*°º]\s*\d+',
        r'Decreto\s+(Supremo|Legislativo)\s+N[*°º]',
        r'Resolución Ministerial',
        r'Artículo \d+',
    ]

    footnote_start = len(lines)

    for i, line in enumerate(lines):
        stripped = line.strip()

        if not stripped:
            continue

        # Check for footnote marker pattern
        if re.match(footnote_marker_pattern, stripped):
            # Additional validation: line should be informative (not just numbers)
            if len(stripped.split()) > 2:  # At least marker + 2 words
                # Remove the footnote marker to check the actual content
                content_without_marker = re.sub(r'^\s*[!?*$0-9]+\s+', '', stripped)

                # Check if it matches common footnote phrases
                for phrase_pattern in footnote_phrases:
                    if re.search(phrase_pattern, content_without_marker):
                        footnote_start = min(footnote_start, i)
                        break

                # Check if it contains legal references
                for legal_pattern in legal_patterns:
                    if re.search(legal_pattern, content_without_marker):
                        footnote_start = min(footnote_start, i)
                        break

        # Also check for lines that are pure footnote phrases
        for phrase_pattern in footnote_phrases:
            if re.match(phrase_pattern, stripped):
                footnote_start = min(footnote_start, i)
                break

    return footnote_start


def remove_page_numbers(text):
    """Remove page numbers at end (e.g., "1/5", "2/5")"""
    # Pattern: X/Y at end of line or by itself
    text = re.sub(r'\n\s*\d+/\d+\s*$', '', text)
    text = re.sub(r'\s+\d+/\d+\s*$', '', text)
    return text


def remove_signature_block(lines):
    """
    Remove signature block at end of document

    Pattern:
    - "Lima, [date]"
    - NAME IN CAPS
    - "PRESIDENTE DEL CONSEJO FISCAL"
    """
    signature_patterns = [
        r'^Lima,\s+\d+\s+de\s+\w+\s+de\s+\d+',
        r'^[A-ZÁÉÍÓÚ\s]+$',  # All caps names
        r'PRESIDENTE\s+DEL\s+CONSEJO\s+FISCAL',
        r'VICEPRESIDENTE',
    ]

    # Scan from end backwards
    cut_index = len(lines)

    for i in range(len(lines) - 1, max(0, len(lines) - 10), -1):
        stripped = lines[i].strip()

        if not stripped:
            continue

        # Check for signature patterns
        for pattern in signature_patterns:
            if re.search(pattern, stripped):
                cut_index = min(cut_index, i)
                break

    return lines[:cut_index]


def remove_urls(text):
    """Remove URLs that appear in footnotes"""
    # Pattern: http_:/_/ or www.
    text = re.sub(r'http[s]?_:/_/[^\s]+', '', text)
    text = re.sub(r'www\.[^\s]+', '', text)
    return text


def clean_text_robust(text, remove_footnotes=True, remove_signature=True):
    """
    Main cleaning function with multiple strategies

    Args:
        text: Raw OCR text
        remove_footnotes: Remove detected footnotes
        remove_signature: Remove signature block at end

    Returns:
        Cleaned text
    """
    lines = text.split('\n')

    # Step 1: Remove signature block
    if remove_signature:
        lines = remove_signature_block(lines)

    # Step 2: Detect and remove footnotes
    if remove_footnotes:
        footnote_start = detect_footnote_start(lines)
        lines = lines[:footnote_start]

    # Reconstruct text
    cleaned = '\n'.join(lines)

    # Step 3: Remove page numbers
    cleaned = remove_page_numbers(cleaned)

    # Step 4: Remove URLs
    cleaned = remove_urls(cleaned)

    # Step 5: Clean up excessive whitespace
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)  # Max 2 consecutive newlines
    cleaned = re.sub(r' {2,}', ' ', cleaned)      # Max 1 space between words

    return cleaned.strip()


def process_all_extracted_text(input_dir="extracted_text",
                                output_dir="cleaned_text"):
    """
    Clean all extracted text files

    Generates:
    - Individual cleaned text files
    - JSON with all cleaned text
    - Comparison report (before/after statistics)
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get all text files
    text_files = sorted(input_dir.glob("*.txt"))
    # Exclude analysis file
    text_files = [f for f in text_files if 'analysis' not in f.name]

    print(f"\n{'='*80}")
    print(f"CLEANING {len(text_files)} TEXT FILES")
    print('='*80)

    results = {}
    stats = {
        'total_files': 0,
        'total_chars_before': 0,
        'total_chars_after': 0,
        'total_lines_before': 0,
        'total_lines_after': 0,
        'footnotes_removed': 0,
        'signatures_removed': 0,
    }

    for text_file in tqdm(text_files, desc="Cleaning", ncols=80):
        # Read original text
        with open(text_file, 'r', encoding='utf-8') as f:
            original = f.read()

        # Clean text
        cleaned = clean_text_robust(original,
                                    remove_footnotes=True,
                                    remove_signature=True)

        # Save cleaned file
        cleaned_filename = text_file.stem + "_cleaned.txt"
        cleaned_path = output_dir / cleaned_filename
        with open(cleaned_path, 'w', encoding='utf-8') as f:
            f.write(cleaned)

        # Parse filename for JSON structure
        stem = text_file.stem
        parts = stem.rsplit('_page', 1)
        if len(parts) == 2:
            pdf_name = parts[0]
            page_num = parts[1]
        else:
            pdf_name = stem
            page_num = "1"

        if pdf_name not in results:
            results[pdf_name] = {}

        results[pdf_name][int(page_num)] = {
            'original_file': text_file.name,
            'cleaned_file': cleaned_filename,
            'chars_before': len(original),
            'chars_after': len(cleaned),
            'lines_before': len(original.split('\n')),
            'lines_after': len(cleaned.split('\n')),
            'reduction_pct': (1 - len(cleaned) / len(original)) * 100 if len(original) > 0 else 0,
        }

        # Update stats
        stats['total_files'] += 1
        stats['total_chars_before'] += len(original)
        stats['total_chars_after'] += len(cleaned)
        stats['total_lines_before'] += len(original.split('\n'))
        stats['total_lines_after'] += len(cleaned.split('\n'))

        if len(cleaned) < len(original):
            if 'Lima,' in original or 'PRESIDENTE' in original:
                stats['signatures_removed'] += 1
            if re.search(r'[!?*$]\s+[A-Z]', original):  # Footnote marker detected
                stats['footnotes_removed'] += 1

    # Save JSON
    json_path = output_dir / "all_cleaned_text.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Save stats
    stats['avg_reduction_pct'] = (1 - stats['total_chars_after'] / stats['total_chars_before']) * 100

    stats_path = output_dir / "cleaning_stats.json"
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2)

    # Print summary
    print(f"\n{'='*80}")
    print("CLEANING SUMMARY")
    print('='*80)
    print(f"Files processed: {stats['total_files']}")
    print(f"Characters before: {stats['total_chars_before']:,}")
    print(f"Characters after: {stats['total_chars_after']:,}")
    print(f"Reduction: {stats['avg_reduction_pct']:.1f}%")
    print(f"\nLines before: {stats['total_lines_before']:,}")
    print(f"Lines after: {stats['total_lines_after']:,}")
    print(f"\nFiles with footnotes removed: ~{stats['footnotes_removed']}")
    print(f"Files with signatures removed: ~{stats['signatures_removed']}")
    print(f"\nOutputs:")
    print(f"  Cleaned files: {output_dir}/ ({stats['total_files']} files)")
    print(f"  JSON: {json_path}")
    print(f"  Stats: {stats_path}")
    print('='*80)

    return results, stats


if __name__ == "__main__":
    print("\n" + "="*80)
    print("ROBUST FOOTNOTE CLEANER")
    print("="*80)
    print("\nStrategy:")
    print("  1. Detect footnotes by markers (!, ?, *, $, numbers) + common phrases")
    print("  2. Remove signature blocks (Lima, names, PRESIDENTE)")
    print("  3. Remove page numbers (X/Y)")
    print("  4. Remove URLs")
    print("  5. Clean excessive whitespace")
    print("="*80)

    results, stats = process_all_extracted_text()

    print("\n[DONE] Cleaning complete!")
    print("Check 'cleaned_text/' folder for results")
