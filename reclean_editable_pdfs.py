"""
Re-clean editable PDFs with improved cleaning pipeline.

This script applies the improved cleaning steps (Step 2 and Step 10) to
editable_pdfs_extracted_text.json, generating a new cleaned version.

Improvements:
- Step 2: Remove ALL Lima date patterns (not just with signatures)
- Step 10: Remove false paragraph breaks before lowercase letters
"""

import json
import re
from pathlib import Path


def clean_editable_extracted_text(text: str) -> dict:
    """
    Execute improved 10-step text cleaning pipeline on extracted PDF text.

    Steps:
        1. Remove dotted signature lines
        2. Remove ALL Lima date patterns (IMPROVED)
        3. Remove standalone uppercase lines
        4. Remove standalone section headers
        5. Remove graph/table titles
        6. Remove chart sub-labels
        7. Replace rare symbols
        8. Normalize whitespace
        9. Remove enumeration (NOT used - aggressive mode disabled)
        10. Remove false paragraph breaks (NEW)
    """
    if not text or not text.strip():
        return {
            'cleaned_text': text,
            'original_length': len(text) if text else 0,
            'cleaned_length': len(text) if text else 0,
            'reduction_pct': 0.0
        }

    original_length = len(text)

    # Step 1: Remove dotted signature lines
    pattern = r'\n*[\.…]{5,}[\s\n]*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+)(?=\n|$)'
    text = re.sub(pattern, '', text)

    # Step 2: Remove ALL Lima date patterns (IMPROVED)
    pattern = r'\n*Lima,?\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\.?[\s\n]*'
    text = re.sub(pattern, '\n\n', text)
    # Also remove uppercase names/organizations that may follow
    pattern_legacy = r'\n\n([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{10,})\n\n'
    text = re.sub(pattern_legacy, '\n\n', text)

    # Step 3: Remove standalone uppercase lines
    pattern = r'\n\n([A-ZÁÉÍÓÚÑ]+(?:\s+[A-ZÁÉÍÓÚÑ]+){2,})\n\n'
    text = re.sub(pattern, '\n\n', text)

    # Step 4: Remove standalone section headers
    paragraphs = text.split('\n\n')
    cleaned_paragraphs = []
    for para in paragraphs:
        para_clean = para.strip()
        if not para_clean:
            continue
        # Skip short headers without ending punctuation
        word_count = len(para_clean.split())
        ends_with_punct = para_clean[-1] in '.,:;!?' if para_clean else False
        if len(para_clean) < 50 and word_count < 8 and not ends_with_punct:
            continue
        cleaned_paragraphs.append(para)
    text = '\n\n'.join(cleaned_paragraphs)

    # Step 5: Remove graph/table titles
    # Pattern: Gráfico/Tabla/Cuadro N° followed by title
    pattern = r'\n+(Gráfico|Tabla|Cuadro)\s+N?°?\s*\d+[^\n]*\n+'
    text = re.sub(pattern, '\n', text, flags=re.IGNORECASE)

    # Step 6: Remove chart sub-labels
    # Pattern 1: Multiple labels with parentheses on same line
    text = re.sub(r'\n+\([A-Z]\)\s[^\n]+\([A-Z]\)\s[^\n]*\n+', '\n', text)
    # Pattern 2: Multiple labels without parentheses on same line
    text = re.sub(r'\n+[A-Z]\)\s[^\n]+[A-Z]\)\s[^\n]*\n+', '\n', text)
    # Pattern 3: Single chart label at start of very short line
    text = re.sub(r'\n+\([A-Z]\)\s[^\n]{1,50}\n+', '\n', text)

    # Step 7: Replace rare symbols
    replacements = {
        '•': ' ', '➢': ' ', '►': ' ', '■': ' ', '▪': ' ',
        '□': ' ', '◼': ' ', '○': ' ', '●': ' ', '▫': ' ',
        'Ø': ' ', '…': '...',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Step 8: Normalize whitespace
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)  # Remove spaces before punctuation
    text = re.sub(r' {2,}', ' ', text)  # Multiple spaces -> single space
    text = re.sub(r'\n{3,}', '\n\n', text)  # 3+ newlines -> 2 newlines
    text = text.strip()

    # Step 9: Remove enumeration - SKIPPED (not in aggressive mode)

    # Step 10: Remove false paragraph breaks (NEW)
    # Remove ALL \n\n before lowercase letters
    text = re.sub(r'\n\n([a-záéíóúñü])', r' \1', text)
    # Remove \n\n before years
    text = re.sub(r'\n\n([12]\d{3})', r' \1', text)
    # Remove \n\n before common connectors
    connectors = r'(?:de|del|la|el|los|las|un|una|en|con|por|para|que|se|y|o|su|sus|sobre|al|ha|han|lo|le)'
    text = re.sub(r'\n\n(' + connectors + r'\s)', r' \1', text)

    cleaned_length = len(text)
    reduction_pct = ((original_length - cleaned_length) / original_length * 100) if original_length > 0 else 0.0

    return {
        'cleaned_text': text,
        'original_length': original_length,
        'cleaned_length': cleaned_length,
        'reduction_pct': reduction_pct
    }


def main():
    input_file = Path('data/raw/editable_pdfs_extracted_text.json')
    output_file = Path('data/raw/editable_pdfs_clean_extracted_text.json')

    print('='*80)
    print('RE-CLEANING EDITABLE PDFs WITH IMPROVED PIPELINE')
    print('='*80)
    print(f'Input:  {input_file}')
    print(f'Output: {output_file}')
    print()
    print('Improvements:')
    print('  - Step 2: Remove ALL Lima date patterns (not just with signatures)')
    print('  - Step 10: Remove false paragraph breaks before lowercase (NEW)')
    print('='*80)

    # Load input data
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f'\nProcessing {len(data)} pages...')

    # Clean each page
    cleaned_data = []
    total_original = 0
    total_cleaned = 0
    dates_removed = 0
    false_breaks_removed = 0

    for entry in data:
        text = entry['text']

        # Count dates before cleaning
        dates_before = len(re.findall(r'Lima,?\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}', text))

        # Count false breaks before cleaning
        false_breaks_before = len(re.findall(r'\n\n([a-záéíóúñü])', text))

        # Clean text
        result = clean_editable_extracted_text(text)

        # Count after
        dates_after = len(re.findall(r'Lima,?\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}', result['cleaned_text']))
        false_breaks_after = len(re.findall(r'\n\n([a-záéíóúñü])', result['cleaned_text']))

        dates_removed += (dates_before - dates_after)
        false_breaks_removed += (false_breaks_before - false_breaks_after)

        total_original += result['original_length']
        total_cleaned += result['cleaned_length']

        cleaned_data.append({
            'pdf_filename': entry['pdf_filename'],
            'page': entry['page'],
            'text': result['cleaned_text'],
            'original_length': result['original_length'],
            'cleaned_length': result['cleaned_length'],
            'reduction_pct': result['reduction_pct']
        })

    # Save output
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    # Print statistics
    total_reduction = ((total_original - total_cleaned) / total_original * 100) if total_original > 0 else 0.0

    print()
    print('='*80)
    print('CLEANING COMPLETE')
    print('='*80)
    print(f'Pages processed:      {len(cleaned_data)}')
    print(f'Original characters:  {total_original:,}')
    print(f'Cleaned characters:   {total_cleaned:,}')
    print(f'Reduction:            {total_reduction:.2f}%')
    print()
    print('NEW IMPROVEMENTS:')
    print(f'  Lima dates removed:        {dates_removed}')
    print(f'  False breaks removed:      {false_breaks_removed}')
    print('='*80)
    print(f'\nOutput saved to: {output_file}')


if __name__ == '__main__':
    main()
