"""
Merge Unified Paragraphs with CF Metadata

This script merges unified_paragraphs_segmented.json with cf_metadata.json
to create a comprehensive metadata file for statistical analysis and LLM classification.

Output: metadata/cf_comprehensive_metadata.json

Author: Claude Code
Date: 2025-01-28
"""

import json
from pathlib import Path
from typing import List, Dict
import sys
import io

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def load_data(paragraphs_path: str, metadata_path: str) -> tuple:
    """Load paragraphs and metadata from JSON files."""

    print('\n' + '='*80)
    print('LOADING DATA')
    print('='*80)

    with open(paragraphs_path, 'r', encoding='utf-8') as f:
        paragraphs = json.load(f)

    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    print(f'Paragraphs loaded: {len(paragraphs)}')
    print(f'Metadata entries:  {len(metadata)}')

    return paragraphs, metadata


def create_metadata_lookup(metadata: List[Dict]) -> Dict[str, Dict]:
    """Create a lookup dictionary by pdf_filename."""

    lookup = {}
    for entry in metadata:
        pdf_filename = entry['pdf_filename']
        lookup[pdf_filename] = entry

    return lookup


def merge_paragraphs_with_metadata(paragraphs: List[Dict], metadata_lookup: Dict[str, Dict]) -> List[Dict]:
    """
    Merge each paragraph with its corresponding metadata.

    Args:
        paragraphs: List of paragraph dictionaries
        metadata_lookup: Dictionary mapping pdf_filename to metadata

    Returns:
        List of comprehensive dictionaries with paragraphs + metadata
    """

    print('\n' + '='*80)
    print('MERGING PARAGRAPHS WITH METADATA')
    print('='*80)

    comprehensive = []
    matched = 0
    unmatched = 0
    unmatched_files = set()

    for para in paragraphs:
        pdf_filename = para['pdf_filename']

        # Look up metadata
        if pdf_filename in metadata_lookup:
            meta = metadata_lookup[pdf_filename]

            # Create comprehensive entry
            comprehensive_entry = {
                # Paragraph data
                'paragraph_num': para['paragraph_num'],
                'text': para['text'],
                'length': para['length'],
                'page_range': para['page_range'],

                # Document metadata
                'pdf_filename': pdf_filename,
                'doc_title': meta.get('doc_title', ''),
                'doc_type': meta.get('doc_type', ''),
                'doc_number': meta.get('doc_number', None),

                # Date metadata
                'date': meta.get('date', ''),
                'year': meta.get('year', ''),
                'month': meta.get('month', None),

                # Source metadata
                'source_type': para['source_type'],  # scanned or editable
                'pdf_type': meta.get('pdf_type', ''),  # from metadata (may differ)

                # URLs
                'pdf_url': meta.get('pdf_url', ''),
                'page_url': meta.get('page_url', '')
            }

            comprehensive.append(comprehensive_entry)
            matched += 1
        else:
            # No metadata found - still include paragraph with partial info
            comprehensive_entry = {
                'paragraph_num': para['paragraph_num'],
                'text': para['text'],
                'length': para['length'],
                'page_range': para['page_range'],
                'pdf_filename': pdf_filename,
                'doc_title': '',
                'doc_type': '',
                'doc_number': None,
                'date': '',
                'year': '',
                'month': None,
                'source_type': para['source_type'],
                'pdf_type': '',
                'pdf_url': '',
                'page_url': ''
            }

            comprehensive.append(comprehensive_entry)
            unmatched += 1
            unmatched_files.add(pdf_filename)

    print(f'Matched paragraphs:   {matched}')
    print(f'Unmatched paragraphs: {unmatched}')

    if unmatched_files:
        print(f'\nUnmatched PDF files ({len(unmatched_files)}):')
        for filename in sorted(unmatched_files)[:10]:  # Show first 10
            print(f'  - {filename}')
        if len(unmatched_files) > 10:
            print(f'  ... and {len(unmatched_files) - 10} more')

    return comprehensive


def save_comprehensive_metadata(data: List[Dict], output_path: str):
    """Save comprehensive metadata to JSON file."""

    print('\n' + '='*80)
    print('SAVING COMPREHENSIVE METADATA')
    print('='*80)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'Output saved to: {output_file}')
    print(f'Total entries:   {len(data)}')

    # Calculate file size
    file_size = output_file.stat().st_size
    print(f'File size:       {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)')


def print_summary_statistics(data: List[Dict]):
    """Print summary statistics of the comprehensive metadata."""

    print('\n' + '='*80)
    print('SUMMARY STATISTICS')
    print('='*80)

    # Total paragraphs
    print(f'\nTotal paragraphs: {len(data)}')

    # Unique documents
    unique_docs = len(set(p['pdf_filename'] for p in data))
    print(f'Unique documents: {unique_docs}')

    # By document type
    doc_types = {}
    for p in data:
        doc_type = p['doc_type'] or 'Unknown'
        doc_types[doc_type] = doc_types.get(doc_type, 0) + 1

    print(f'\nParagraphs by document type:')
    for doc_type, count in sorted(doc_types.items()):
        print(f'  {doc_type:12s}: {count:4d} paragraphs')

    # By source type
    source_types = {}
    for p in data:
        source_type = p['source_type']
        source_types[source_type] = source_types.get(source_type, 0) + 1

    print(f'\nParagraphs by source type:')
    for source_type, count in sorted(source_types.items()):
        print(f'  {source_type:12s}: {count:4d} paragraphs')

    # By year
    years = {}
    for p in data:
        year = p['year'] or 'Unknown'
        years[year] = years.get(year, 0) + 1

    print(f'\nParagraphs by year:')
    for year in sorted(years.keys()):
        if year != 'Unknown':
            print(f'  {year}: {years[year]:4d} paragraphs')
    if 'Unknown' in years:
        print(f'  Unknown: {years["Unknown"]:4d} paragraphs')


def main():
    """Execute the metadata merge pipeline."""

    print('='*80)
    print('CF COMPREHENSIVE METADATA GENERATION')
    print('='*80)
    print('Merging unified paragraphs with document metadata.')
    print('='*80)

    # Paths
    paragraphs_path = 'data/raw/unified_paragraphs_segmented.json'
    metadata_path = 'metadata/cf_metadata.json'
    output_path = 'metadata/cf_comprehensive_metadata.json'

    # Load data
    paragraphs, metadata = load_data(paragraphs_path, metadata_path)

    # Create metadata lookup
    metadata_lookup = create_metadata_lookup(metadata)
    print(f'\nMetadata lookup created for {len(metadata_lookup)} PDFs')

    # Merge
    comprehensive = merge_paragraphs_with_metadata(paragraphs, metadata_lookup)

    # Save
    save_comprehensive_metadata(comprehensive, output_path)

    # Print statistics
    print_summary_statistics(comprehensive)

    # Final message
    print('\n' + '='*80)
    print('MERGE COMPLETE')
    print('='*80)
    print(f'Comprehensive metadata saved to: {output_path}')
    print('Ready for statistical analysis and visualization!')
    print('='*80)


if __name__ == '__main__':
    main()
