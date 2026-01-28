"""
Merge and Segment Pipeline for CF Opinion Texts

This script:
1. Merges scanned and editable cleaned texts
2. Unifies paragraphs broken across pages
3. Segments by \n\n markers
4. Generates unified_paragraphs_segmented.json

Author: Claude Code
Date: 2025-01-28
"""

import json
import re
from pathlib import Path
from typing import List, Dict
import sys
import io

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def merge_clean_texts(scanned_path: str, editable_path: str) -> List[Dict]:
    """
    Merge scanned and editable cleaned texts into a single unified list.

    Args:
        scanned_path: Path to scanned_pdfs_clean_extracted_text.json
        editable_path: Path to editable_pdfs_clean_extracted_text.json

    Returns:
        List of all pages sorted by pdf_filename and page number
    """
    print('\n' + '='*80)
    print('STEP 1: MERGING SCANNED AND EDITABLE TEXTS')
    print('='*80)

    with open(scanned_path, 'r', encoding='utf-8') as f:
        scanned = json.load(f)

    with open(editable_path, 'r', encoding='utf-8') as f:
        editable = json.load(f)

    print(f'Scanned PDFs:  {len(scanned)} pages from {len(set(e["pdf_filename"] for e in scanned))} PDFs')
    print(f'Editable PDFs: {len(editable)} pages from {len(set(e["pdf_filename"] for e in editable))} PDFs')

    # Add source field to track origin
    for entry in scanned:
        entry['source_type'] = 'scanned'

    for entry in editable:
        entry['source_type'] = 'editable'

    # Merge and sort
    merged = scanned + editable
    merged.sort(key=lambda x: (x['pdf_filename'], x['page']))

    print(f'Total merged:  {len(merged)} pages from {len(set(e["pdf_filename"] for e in merged))} PDFs')

    return merged


def unify_paragraphs_across_pages(pages: List[Dict]) -> List[Dict]:
    """
    Unify paragraphs that are broken across pages.

    Logic:
    - If a page ends WITHOUT \n\n at the end, it continues on the next page
    - If next page starts WITHOUT \n\n, it's a continuation of the previous paragraph
    - Join them into a single page entry

    Args:
        pages: List of page dictionaries sorted by pdf_filename and page

    Returns:
        List of unified page dictionaries
    """
    print('\n' + '='*80)
    print('STEP 2: UNIFYING PARAGRAPHS BROKEN ACROSS PAGES')
    print('='*80)

    unified = []
    pages_joined = 0

    # Group by PDF
    pdfs = {}
    for page in pages:
        pdf_name = page['pdf_filename']
        if pdf_name not in pdfs:
            pdfs[pdf_name] = []
        pdfs[pdf_name].append(page)

    # Process each PDF
    for pdf_name, pdf_pages in pdfs.items():
        # Sort by page number
        pdf_pages.sort(key=lambda x: x['page'])

        i = 0
        while i < len(pdf_pages):
            current_page = pdf_pages[i]
            current_text = current_page['text']

            # Check if we need to join with next page
            if i + 1 < len(pdf_pages):
                next_page = pdf_pages[i + 1]
                next_text = next_page['text']

                # Join if current doesn't end with \n\n or next doesn't start with \n\n
                # OR if current ends mid-sentence (no period before potential newlines)
                current_ends_clean = current_text.rstrip().endswith('\n\n')
                next_starts_clean = next_text.lstrip().startswith('\n\n')

                # Check if last non-whitespace char is a sentence-ending punctuation
                current_stripped = current_text.rstrip()
                ends_with_period = current_stripped and current_stripped[-1] in '.!?'

                # Join if:
                # 1. Current doesn't end with \n\n AND next doesn't start with \n\n
                # 2. OR current doesn't end with sentence punctuation
                should_join = (not current_ends_clean and not next_starts_clean) or not ends_with_period

                if should_join:
                    # Join the texts
                    joined_text = current_text.rstrip() + ' ' + next_text.lstrip()

                    # Create unified entry
                    unified_entry = {
                        'pdf_filename': current_page['pdf_filename'],
                        'page': current_page['page'],
                        'page_range': f"{current_page['page']}-{next_page['page']}",
                        'text': joined_text,
                        'source_type': current_page['source_type']
                    }

                    unified.append(unified_entry)
                    pages_joined += 1

                    # Skip next page as it's been merged
                    i += 2
                    continue

            # No joining needed, add as-is
            unified.append({
                'pdf_filename': current_page['pdf_filename'],
                'page': current_page['page'],
                'page_range': str(current_page['page']),
                'text': current_page['text'],
                'source_type': current_page['source_type']
            })

            i += 1

    print(f'Pages before unification: {len(pages)}')
    print(f'Pages after unification:  {len(unified)}')
    print(f'Pages joined:             {pages_joined}')

    return unified


def segment_by_paragraph_markers(unified_pages: List[Dict]) -> List[Dict]:
    """
    Segment unified pages by \n\n markers into individual paragraphs.

    Args:
        unified_pages: List of unified page dictionaries

    Returns:
        List of paragraph dictionaries with paragraph_num
    """
    print('\n' + '='*80)
    print('STEP 3: SEGMENTING BY \\n\\n MARKERS')
    print('='*80)

    paragraphs = []
    global_para_num = 1

    for page_entry in unified_pages:
        text = page_entry['text']

        # Split by \n\n
        raw_paragraphs = text.split('\n\n')

        # Clean and filter
        for para_text in raw_paragraphs:
            para_clean = para_text.strip()

            # Skip empty paragraphs
            if not para_clean:
                continue

            # Skip very short paragraphs (likely artifacts)
            if len(para_clean) < 20:
                continue

            # Create paragraph entry
            para_entry = {
                'pdf_filename': page_entry['pdf_filename'],
                'page_range': page_entry['page_range'],
                'paragraph_num': global_para_num,
                'text': para_clean,
                'length': len(para_clean),
                'source_type': page_entry['source_type']
            }

            paragraphs.append(para_entry)
            global_para_num += 1

    print(f'Total paragraphs extracted: {len(paragraphs)}')

    # Calculate statistics
    lengths = [p['length'] for p in paragraphs]
    if lengths:
        print(f'Paragraph length statistics:')
        print(f'  Min:     {min(lengths):,} chars')
        print(f'  Max:     {max(lengths):,} chars')
        print(f'  Mean:    {sum(lengths) / len(lengths):,.0f} chars')
        print(f'  Median:  {sorted(lengths)[len(lengths)//2]:,} chars')

    return paragraphs


def main():
    """Execute the complete merge and segmentation pipeline."""

    print('='*80)
    print('CF OPINION TEXTS - MERGE AND SEGMENTATION PIPELINE')
    print('='*80)
    print('This script merges cleaned texts and segments them into paragraphs.')
    print('='*80)

    # Paths
    scanned_path = 'data/raw/scanned_pdfs_clean_extracted_text.json'
    editable_path = 'data/raw/editable_pdfs_clean_extracted_text.json'
    output_path = 'data/raw/unified_paragraphs_segmented.json'

    # Step 1: Merge
    merged_pages = merge_clean_texts(scanned_path, editable_path)

    # Step 2: Unify paragraphs across pages
    unified_pages = unify_paragraphs_across_pages(merged_pages)

    # Step 3: Segment by \n\n
    paragraphs = segment_by_paragraph_markers(unified_pages)

    # Save output
    print('\n' + '='*80)
    print('SAVING OUTPUT')
    print('='*80)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(paragraphs, f, ensure_ascii=False, indent=2)

    print(f'Output saved to: {output_file}')
    print(f'Total paragraphs: {len(paragraphs)}')

    # Final summary
    print('\n' + '='*80)
    print('PIPELINE COMPLETE')
    print('='*80)
    print(f'Unified paragraphs saved to: {output_path}')
    print(f'Ready for metadata merge and LLM classification!')
    print('='*80)


if __name__ == '__main__':
    main()
