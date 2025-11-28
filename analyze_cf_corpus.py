"""
Comprehensive Statistical Analysis and Visualization of CF Opinion Corpus

This script provides detailed statistics and visualizations for the Consejo Fiscal
opinion corpus, analyzing document metadata, paragraph characteristics, and
temporal patterns.

Author: Claude Code
Date: 2025-01-28
"""

import json
import sys
import io
from pathlib import Path
from collections import Counter
from typing import List, Dict
import statistics

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from datetime import datetime

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Set matplotlib style
plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams['figure.figsize'] = (12, 6)
plt.rcParams['font.size'] = 10


def load_comprehensive_metadata(path: str) -> List[Dict]:
    """Load comprehensive metadata JSON file."""

    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data


def print_header(title: str):
    """Print a formatted section header."""
    print('\n' + '='*80)
    print(title.center(80))
    print('='*80)


def calculate_general_statistics(data: List[Dict]):
    """Calculate and print general corpus statistics."""

    print_header('GENERAL CORPUS STATISTICS')

    # Total counts
    total_paragraphs = len(data)
    unique_docs = len(set(p['pdf_filename'] for p in data))

    print(f'\n📊 OVERVIEW')
    print(f'  Total paragraphs:     {total_paragraphs:,}')
    print(f'  Unique documents:     {unique_docs:,}')
    print(f'  Avg paragraphs/doc:   {total_paragraphs / unique_docs:.1f}')

    # By document type
    print(f'\n📄 BY DOCUMENT TYPE')
    doc_types = Counter(p['doc_type'] for p in data if p['doc_type'])
    for doc_type, count in doc_types.most_common():
        pct = count / total_paragraphs * 100
        docs = len(set(p['pdf_filename'] for p in data if p['doc_type'] == doc_type))
        print(f'  {doc_type:12s}: {count:4d} paragraphs ({pct:5.1f}%) from {docs} documents')

    # By source type
    print(f'\n💾 BY SOURCE TYPE (RAW DATA)')
    source_types = Counter(p['source_type'] for p in data)
    for source_type, count in source_types.most_common():
        pct = count / total_paragraphs * 100
        docs = len(set(p['pdf_filename'] for p in data if p['source_type'] == source_type))
        print(f'  {source_type:12s}: {count:4d} paragraphs ({pct:5.1f}%) from {docs} documents')

    # By year
    print(f'\n📅 BY YEAR')
    years = Counter(p['year'] for p in data if p['year'])
    for year in sorted(years.keys()):
        count = years[year]
        pct = count / total_paragraphs * 100
        docs = len(set(p['pdf_filename'] for p in data if p['year'] == year))
        print(f'  {year}: {count:4d} paragraphs ({pct:5.1f}%) from {docs:2d} documents')

    # Identify peak years
    if years:
        max_year = max(years.items(), key=lambda x: x[1])
        min_year = min(years.items(), key=lambda x: x[1])
        print(f'\n  🔥 Peak year:    {max_year[0]} ({max_year[1]} paragraphs)')
        print(f'  📉 Lowest year:  {min_year[0]} ({min_year[1]} paragraphs)')


def calculate_paragraph_statistics(data: List[Dict]):
    """Calculate and print detailed paragraph statistics."""

    print_header('PARAGRAPH LENGTH STATISTICS')

    lengths = [p['length'] for p in data]

    # Basic statistics
    print(f'\n📏 BASIC STATS')
    print(f'  Total paragraphs: {len(lengths):,}')
    print(f'  Total characters: {sum(lengths):,}')
    print(f'  Mean length:      {statistics.mean(lengths):,.1f} chars')
    print(f'  Median length:    {statistics.median(lengths):,} chars')
    print(f'  Std deviation:    {statistics.stdev(lengths):,.1f} chars')

    # Range
    print(f'\n📊 RANGE')
    print(f'  Minimum:  {min(lengths):,} chars')
    print(f'  Maximum:  {max(lengths):,} chars')
    print(f'  Range:    {max(lengths) - min(lengths):,} chars')

    # Percentiles
    print(f'\n📈 PERCENTILES')
    percentiles = [5, 10, 25, 50, 75, 90, 95, 99]
    for p in percentiles:
        value = np.percentile(lengths, p)
        print(f'  P{p:2d}:  {value:7,.0f} chars')

    # Distribution by size category
    print(f'\n📦 SIZE CATEGORIES')
    categories = {
        'Very short (<200)':   lambda x: x < 200,
        'Short (200-400)':     lambda x: 200 <= x < 400,
        'Medium (400-700)':    lambda x: 400 <= x < 700,
        'Long (700-1000)':     lambda x: 700 <= x < 1000,
        'Very long (1000+)':   lambda x: x >= 1000
    }

    for category, condition in categories.items():
        count = sum(1 for l in lengths if condition(l))
        pct = count / len(lengths) * 100
        print(f'  {category:20s}: {count:4d} paragraphs ({pct:5.1f}%)')


def calculate_temporal_statistics(data: List[Dict]):
    """Calculate temporal statistics (by month, year)."""

    print_header('TEMPORAL ANALYSIS')

    # Opinions per year
    print(f'\n📅 DOCUMENTS PER YEAR')
    docs_by_year = {}
    for p in data:
        if p['year']:
            if p['year'] not in docs_by_year:
                docs_by_year[p['year']] = set()
            docs_by_year[p['year']].add(p['pdf_filename'])

    for year in sorted(docs_by_year.keys()):
        count = len(docs_by_year[year])
        print(f'  {year}: {count:2d} documents')

    # By month (aggregated across all years)
    print(f'\n📊 PARAGRAPHS BY MONTH (ALL YEARS COMBINED)')
    months = Counter(p['month'] for p in data if p['month'])
    month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    for month_num in range(1, 13):
        if month_num in months:
            count = months[month_num]
            month_name = month_names[month_num]
            print(f'  {month_name:3s}: {count:3d} paragraphs')


def calculate_document_statistics(data: List[Dict]):
    """Calculate per-document statistics."""

    print_header('PER-DOCUMENT STATISTICS')

    # Paragraphs per document
    paras_per_doc = Counter(p['pdf_filename'] for p in data)

    print(f'\n📄 PARAGRAPHS PER DOCUMENT')
    print(f'  Total documents:      {len(paras_per_doc)}')
    print(f'  Mean paragraphs/doc:  {statistics.mean(paras_per_doc.values()):.1f}')
    print(f'  Median:               {statistics.median(paras_per_doc.values()):.1f}')
    print(f'  Std deviation:        {statistics.stdev(paras_per_doc.values()):.1f}')

    # Top documents by paragraph count
    print(f'\n🔝 TOP 10 DOCUMENTS (BY PARAGRAPH COUNT)')
    for i, (doc, count) in enumerate(paras_per_doc.most_common(10), 1):
        # Get doc type and year
        entry = next((p for p in data if p['pdf_filename'] == doc), None)
        doc_type = entry.get('doc_type') or 'Unknown' if entry else 'Unknown'
        year = entry.get('year') or 'Unknown' if entry else 'Unknown'
        print(f'  {i:2d}. {doc[:50]:50s} | {count:3d} paras | {doc_type:10s} | {year}')

    # Bottom documents
    print(f'\n📉 BOTTOM 10 DOCUMENTS (BY PARAGRAPH COUNT)')
    for i, (doc, count) in enumerate(list(paras_per_doc.most_common())[-10:], 1):
        entry = next((p for p in data if p['pdf_filename'] == doc), None)
        doc_type = entry.get('doc_type') or 'Unknown' if entry else 'Unknown'
        year = entry.get('year') or 'Unknown' if entry else 'Unknown'
        print(f'  {i:2d}. {doc[:50]:50s} | {count:3d} paras | {doc_type:10s} | {year}')

    # By document type
    print(f'\n📊 PARAGRAPHS PER DOCUMENT TYPE')
    for doc_type in ['Informe', 'Comunicado']:
        docs = [p['pdf_filename'] for p in data if p['doc_type'] == doc_type]
        if docs:
            paras = [paras_per_doc[doc] for doc in set(docs)]
            print(f'  {doc_type:12s}: mean={statistics.mean(paras):5.1f}, '
                  f'median={statistics.median(paras):5.1f}, '
                  f'max={max(paras):3d}, min={min(paras):2d}')


def create_visualizations(data: List[Dict], output_dir: str = 'visualizations'):
    """Create comprehensive visualizations."""

    print_header('GENERATING VISUALIZATIONS')

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # 1. Paragraph length distribution (histogram)
    print('\n  Creating histogram: paragraph_length_distribution.png')
    fig, ax = plt.subplots(figsize=(12, 6))
    lengths = [p['length'] for p in data]
    ax.hist(lengths, bins=50, edgecolor='black', alpha=0.7)
    ax.set_xlabel('Paragraph Length (characters)')
    ax.set_ylabel('Frequency')
    ax.set_title('Distribution of Paragraph Lengths in CF Opinion Corpus')
    ax.axvline(statistics.mean(lengths), color='red', linestyle='--',
               label=f'Mean: {statistics.mean(lengths):.0f}')
    ax.axvline(statistics.median(lengths), color='green', linestyle='--',
               label=f'Median: {statistics.median(lengths):.0f}')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path / 'paragraph_length_distribution.png', dpi=300)
    plt.close()

    # 2. Box plot of paragraph lengths by document type
    print('  Creating box plot: paragraph_length_by_doctype.png')
    fig, ax = plt.subplots(figsize=(10, 6))
    doc_types = sorted(set(p['doc_type'] for p in data if p['doc_type']))
    data_by_type = [[p['length'] for p in data if p['doc_type'] == dt] for dt in doc_types]
    ax.boxplot(data_by_type, labels=doc_types)
    ax.set_ylabel('Paragraph Length (characters)')
    ax.set_title('Paragraph Length Distribution by Document Type')
    ax.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(output_path / 'paragraph_length_by_doctype.png', dpi=300)
    plt.close()

    # 3. Documents per year (bar chart)
    print('  Creating bar chart: documents_per_year.png')
    fig, ax = plt.subplots(figsize=(12, 6))
    docs_by_year = {}
    for p in data:
        if p['year']:
            if p['year'] not in docs_by_year:
                docs_by_year[p['year']] = set()
            docs_by_year[p['year']].add(p['pdf_filename'])

    years = sorted(docs_by_year.keys())
    counts = [len(docs_by_year[y]) for y in years]
    ax.bar(years, counts, edgecolor='black', alpha=0.7)
    ax.set_xlabel('Year')
    ax.set_ylabel('Number of Documents')
    ax.set_title('CF Opinion Documents Published per Year')
    ax.grid(True, alpha=0.3, axis='y')
    for i, (year, count) in enumerate(zip(years, counts)):
        ax.text(year, count + 0.5, str(count), ha='center', va='bottom')
    plt.tight_layout()
    plt.savefig(output_path / 'documents_per_year.png', dpi=300)
    plt.close()

    # 4. Paragraphs per year (bar chart)
    print('  Creating bar chart: paragraphs_per_year.png')
    fig, ax = plt.subplots(figsize=(12, 6))
    paras_by_year = Counter(p['year'] for p in data if p['year'])
    years = sorted(paras_by_year.keys())
    counts = [paras_by_year[y] for y in years]
    ax.bar(years, counts, edgecolor='black', alpha=0.7, color='steelblue')
    ax.set_xlabel('Year')
    ax.set_ylabel('Number of Paragraphs')
    ax.set_title('CF Opinion Paragraphs per Year')
    ax.grid(True, alpha=0.3, axis='y')
    for i, (year, count) in enumerate(zip(years, counts)):
        ax.text(year, count + 5, str(count), ha='center', va='bottom')
    plt.tight_layout()
    plt.savefig(output_path / 'paragraphs_per_year.png', dpi=300)
    plt.close()

    # 5. Document type distribution (pie chart)
    print('  Creating pie chart: document_type_distribution.png')
    fig, ax = plt.subplots(figsize=(8, 8))
    doc_types = Counter(p['doc_type'] for p in data if p['doc_type'])
    labels = list(doc_types.keys())
    sizes = list(doc_types.values())
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
    ax.set_title('Paragraphs by Document Type')
    plt.tight_layout()
    plt.savefig(output_path / 'document_type_distribution.png', dpi=300)
    plt.close()

    # 6. Source type distribution (pie chart)
    print('  Creating pie chart: source_type_distribution.png')
    fig, ax = plt.subplots(figsize=(8, 8))
    source_types = Counter(p['source_type'] for p in data)
    labels = list(source_types.keys())
    sizes = list(source_types.values())
    colors = ['lightcoral', 'lightskyblue']
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors)
    ax.set_title('Paragraphs by Source Type (Scanned vs Editable)')
    plt.tight_layout()
    plt.savefig(output_path / 'source_type_distribution.png', dpi=300)
    plt.close()

    # 7. Cumulative documents over time
    print('  Creating line plot: cumulative_documents.png')
    fig, ax = plt.subplots(figsize=(12, 6))

    # Get all unique documents with dates
    docs_with_dates = []
    for p in data:
        if p['date'] and p['pdf_filename']:
            try:
                date = datetime.fromisoformat(p['date'].replace('Z', '+00:00'))
                docs_with_dates.append((date, p['pdf_filename']))
            except:
                pass

    # Remove duplicates and sort
    unique_docs = list(set(docs_with_dates))
    unique_docs.sort(key=lambda x: x[0])

    if unique_docs:
        dates = [d[0] for d in unique_docs]
        cumulative = list(range(1, len(dates) + 1))

        ax.plot(dates, cumulative, linewidth=2, marker='o', markersize=4)
        ax.set_xlabel('Date')
        ax.set_ylabel('Cumulative Number of Documents')
        ax.set_title('Cumulative CF Opinion Documents Over Time')
        ax.grid(True, alpha=0.3)

        # Format x-axis
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        ax.xaxis.set_major_locator(mdates.YearLocator())
        plt.xticks(rotation=45)

        plt.tight_layout()
        plt.savefig(output_path / 'cumulative_documents.png', dpi=300)
        plt.close()

    print(f'\n✅ All visualizations saved to: {output_path}/')


def export_summary_statistics(data: List[Dict], output_path: str = 'metadata/corpus_statistics.json'):
    """Export summary statistics to JSON file."""

    print_header('EXPORTING SUMMARY STATISTICS')

    lengths = [p['length'] for p in data]

    summary = {
        'corpus_overview': {
            'total_paragraphs': len(data),
            'total_documents': len(set(p['pdf_filename'] for p in data)),
            'total_characters': sum(lengths),
            'date_generated': datetime.now().isoformat()
        },
        'paragraph_statistics': {
            'mean_length': statistics.mean(lengths),
            'median_length': statistics.median(lengths),
            'std_deviation': statistics.stdev(lengths),
            'min_length': min(lengths),
            'max_length': max(lengths),
            'percentiles': {
                f'p{p}': float(np.percentile(lengths, p))
                for p in [5, 10, 25, 50, 75, 90, 95, 99]
            }
        },
        'by_document_type': {},
        'by_source_type': {},
        'by_year': {}
    }

    # By document type
    for doc_type in set(p['doc_type'] for p in data if p['doc_type']):
        type_data = [p for p in data if p['doc_type'] == doc_type]
        summary['by_document_type'][doc_type] = {
            'paragraphs': len(type_data),
            'documents': len(set(p['pdf_filename'] for p in type_data))
        }

    # By source type
    for source_type in set(p['source_type'] for p in data):
        type_data = [p for p in data if p['source_type'] == source_type]
        summary['by_source_type'][source_type] = {
            'paragraphs': len(type_data),
            'documents': len(set(p['pdf_filename'] for p in type_data))
        }

    # By year
    for year in sorted(set(p['year'] for p in data if p['year'])):
        year_data = [p for p in data if p['year'] == year]
        summary['by_year'][year] = {
            'paragraphs': len(year_data),
            'documents': len(set(p['pdf_filename'] for p in year_data))
        }

    # Save
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f'\n✅ Summary statistics exported to: {output_file}')


def main():
    """Execute comprehensive analysis pipeline."""

    print('='*80)
    print(' CF OPINION CORPUS - COMPREHENSIVE STATISTICAL ANALYSIS '.center(80, '='))
    print('='*80)
    print('\nThis script analyzes the CF opinion corpus and generates:')
    print('  - Detailed statistics on documents, paragraphs, and temporal patterns')
    print('  - Visualizations of data distributions and trends')
    print('  - Summary statistics exported to JSON')
    print('='*80)

    # Load data
    metadata_path = 'metadata/cf_comprehensive_metadata.json'
    print(f'\n📂 Loading data from: {metadata_path}')
    data = load_comprehensive_metadata(metadata_path)
    print(f'✅ Loaded {len(data):,} paragraphs')

    # Run analyses
    calculate_general_statistics(data)
    calculate_paragraph_statistics(data)
    calculate_temporal_statistics(data)
    calculate_document_statistics(data)

    # Create visualizations
    create_visualizations(data)

    # Export summary
    export_summary_statistics(data)

    # Final message
    print_header('ANALYSIS COMPLETE')
    print('\n✅ All statistics calculated and visualizations generated!')
    print('\n📁 Output files:')
    print('  - visualizations/*.png (7 charts)')
    print('  - metadata/corpus_statistics.json (summary statistics)')
    print('\n🎯 Next step: Semantic paragraph normalization using sentence embeddings')
    print('='*80)


if __name__ == '__main__':
    main()
