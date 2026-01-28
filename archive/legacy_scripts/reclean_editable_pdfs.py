"""
Re-clean editable PDFs with improved cleaning pipeline.

This script uses the improved cleaning functions from data_curation.py:
- _is_section_header(): Improved thresholds (150 chars, 20 words)
- _is_chart_or_table_label(): NEW function for numbered labels (1:, I., A), etc.)
- _remove_section_headers(): Uses both helper functions

Improvements:
- Character threshold: 150 (was 50)
- Word threshold: 20 (was 8)
- Chart/table label detection (1:, I., A), etc.)
- Remove ALL Lima date patterns
- Remove false paragraph breaks before lowercase letters
"""

import json
import re
import sys
from pathlib import Path

# Import improved cleaning function from data_curation.py
# Note: We need to be careful because data_curation.py has interactive input at module level
# We'll import only the specific functions we need

# Import the core cleaning function and its dependencies
import importlib.util

# Load data_curation module without executing module-level code
spec = importlib.util.spec_from_file_location("data_curation_funcs", "data_curation.py")
data_curation_module = importlib.util.module_from_spec(spec)

# Redirect stdin to avoid interactive prompts
import io
old_stdin = sys.stdin
sys.stdin = io.StringIO(".\n")  # Provide default input

try:
    spec.loader.exec_module(data_curation_module)
finally:
    sys.stdin = old_stdin

# Now we can use the improved functions from data_curation.py
clean_editable_extracted_text = data_curation_module.clean_editable_extracted_text


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
    print('  - Header detection: 150 chars, 20 words (was 50 chars, 8 words)')
    print('  - Chart/table labels: Detects 1:, I., A), etc.')
    print('  - Remove ALL Lima date patterns')
    print('  - Remove false paragraph breaks before lowercase')
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

        # Clean text (using improved functions from data_curation.py)
        result = clean_editable_extracted_text(text, aggressive=False)

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
