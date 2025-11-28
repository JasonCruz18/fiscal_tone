"""
Compare Original vs Semantically Normalized Paragraphs

This script generates a detailed comparison showing improvements
from semantic normalization.

Author: Claude Code
Date: 2025-01-28
"""

import json
import sys
import io
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

plt.style.use('seaborn-v0_8-darkgrid')
plt.rcParams['figure.figsize'] = (14, 8)


def load_data():
    """Load original and normalized datasets."""

    print("\n" + "="*80)
    print("LOADING DATA FOR COMPARISON")
    print("="*80)

    with open('metadata/cf_comprehensive_metadata.json', 'r', encoding='utf-8') as f:
        original = json.load(f)

    with open('metadata/cf_normalized_paragraphs.json', 'r', encoding='utf-8') as f:
        normalized = json.load(f)

    print(f"\nOriginal paragraphs:    {len(original):,}")
    print(f"Normalized paragraphs:  {len(normalized):,}")
    print(f"Change:                 {len(normalized) - len(original):+,} ({(len(normalized) - len(original)) / len(original) * 100:+.1f}%)")

    return original, normalized


def print_statistics_comparison(original, normalized):
    """Print detailed statistical comparison."""

    print("\n" + "="*80)
    print("STATISTICAL COMPARISON")
    print("="*80)

    orig_lengths = [p['length'] for p in original]
    norm_lengths = [p['length'] for p in normalized]

    # Basic stats
    print("\n📊 BASIC STATISTICS")
    print(f"{'Metric':<20} {'Original':>15} {'Normalized':>15} {'Change':>15}")
    print("-" * 70)

    metrics = [
        ("Mean", np.mean, "chars"),
        ("Median", np.median, "chars"),
        ("Std Dev", np.std, "chars"),
        ("Min", min, "chars"),
        ("Max", max, "chars")
    ]

    for name, func, unit in metrics:
        orig_val = func(orig_lengths)
        norm_val = func(norm_lengths)
        change = norm_val - orig_val
        change_pct = (change / orig_val * 100) if orig_val != 0 else 0

        print(f"{name:<20} {orig_val:>12,.0f} {unit:3s} {norm_val:>12,.0f} {unit:3s} {change:>+7,.0f} ({change_pct:+6.1f}%)")

    # Percentiles
    print("\n📈 PERCENTILES")
    print(f"{'Percentile':<20} {'Original':>15} {'Normalized':>15} {'Change':>15}")
    print("-" * 70)

    for p in [25, 50, 75, 90, 95, 99]:
        orig_val = np.percentile(orig_lengths, p)
        norm_val = np.percentile(norm_lengths, p)
        change = norm_val - orig_val
        change_pct = (change / orig_val * 100) if orig_val != 0 else 0

        print(f"P{p:<19d} {orig_val:>12,.0f} chars {norm_val:>12,.0f} chars {change:>+7,.0f} ({change_pct:+6.1f}%)")

    # Distribution
    print("\n📦 SIZE DISTRIBUTION")
    print(f"{'Category':<20} {'Original':>15} {'Normalized':>15} {'Change':>15}")
    print("-" * 70)

    categories = [
        ("Very short (<200)", lambda l: l < 200),
        ("Short (200-400)", lambda l: 200 <= l < 400),
        ("Medium (400-700)", lambda l: 400 <= l < 700),
        ("Long (700-1000)", lambda l: 700 <= l < 1000),
        ("Very long (1000+)", lambda l: l >= 1000)
    ]

    for name, condition in categories:
        orig_count = sum(1 for l in orig_lengths if condition(l))
        norm_count = sum(1 for l in norm_lengths if condition(l))
        orig_pct = orig_count / len(orig_lengths) * 100
        norm_pct = norm_count / len(norm_lengths) * 100
        change_pct = norm_pct - orig_pct

        print(f"{name:<20} {orig_count:>6,} ({orig_pct:5.1f}%) {norm_count:>6,} ({norm_pct:5.1f}%) {change_pct:>+6.1f} pp")

    # Target range
    target_orig = sum(1 for l in orig_lengths if 400 <= l <= 700)
    target_norm = sum(1 for l in norm_lengths if 400 <= l <= 700)
    target_orig_pct = target_orig / len(orig_lengths) * 100
    target_norm_pct = target_norm / len(norm_lengths) * 100

    print(f"\n🎯 TARGET RANGE (400-700 chars)")
    print(f"  Original:    {target_orig:4,} ({target_orig_pct:5.1f}%)")
    print(f"  Normalized:  {target_norm:4,} ({target_norm_pct:5.1f}%)")
    print(f"  Improvement: {target_norm - target_orig:+4,} ({target_norm_pct - target_orig_pct:+5.1f} pp)")


def create_comparison_visualizations(original, normalized, output_dir='visualizations'):
    """Create before/after comparison visualizations."""

    print("\n" + "="*80)
    print("CREATING COMPARISON VISUALIZATIONS")
    print("="*80)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    orig_lengths = [p['length'] for p in original]
    norm_lengths = [p['length'] for p in normalized]

    # 1. Side-by-side histograms
    print("\n  Creating histogram comparison...")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))

    # Original
    ax1.hist(orig_lengths, bins=50, edgecolor='black', alpha=0.7, color='coral')
    ax1.axvline(np.mean(orig_lengths), color='red', linestyle='--',
                label=f'Mean: {np.mean(orig_lengths):.0f}')
    ax1.axvline(np.median(orig_lengths), color='green', linestyle='--',
                label=f'Median: {np.median(orig_lengths):.0f}')
    ax1.axvspan(400, 700, alpha=0.2, color='green', label='Target range')
    ax1.set_xlabel('Paragraph Length (characters)')
    ax1.set_ylabel('Frequency')
    ax1.set_title('Original Paragraphs (n=1,492)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Normalized
    ax2.hist(norm_lengths, bins=50, edgecolor='black', alpha=0.7, color='steelblue')
    ax2.axvline(np.mean(norm_lengths), color='red', linestyle='--',
                label=f'Mean: {np.mean(norm_lengths):.0f}')
    ax2.axvline(np.median(norm_lengths), color='green', linestyle='--',
                label=f'Median: {np.median(norm_lengths):.0f}')
    ax2.axvspan(400, 700, alpha=0.2, color='green', label='Target range')
    ax2.set_xlabel('Paragraph Length (characters)')
    ax2.set_ylabel('Frequency')
    ax2.set_title('Normalized Paragraphs (n=1,675)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path / 'normalization_comparison_histograms.png', dpi=300)
    plt.close()

    # 2. Box plot comparison
    print("  Creating box plot comparison...")
    fig, ax = plt.subplots(figsize=(10, 6))

    box_data = [orig_lengths, norm_lengths]
    bp = ax.boxplot(box_data, labels=['Original', 'Normalized'], patch_artist=True)

    # Color boxes
    colors = ['coral', 'steelblue']
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    # Add target range
    ax.axhspan(400, 700, alpha=0.1, color='green', label='Target range (400-700)')

    ax.set_ylabel('Paragraph Length (characters)')
    ax.set_title('Paragraph Length Distribution: Before vs After Normalization')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(output_path / 'normalization_comparison_boxplot.png', dpi=300)
    plt.close()

    # 3. Distribution comparison (stacked bar)
    print("  Creating distribution comparison...")
    fig, ax = plt.subplots(figsize=(10, 6))

    categories = ['Very short\n(<200)', 'Short\n(200-400)', 'Medium\n(400-700)',
                  'Long\n(700-1000)', 'Very long\n(1000+)']

    orig_dist = [
        sum(1 for l in orig_lengths if l < 200) / len(orig_lengths) * 100,
        sum(1 for l in orig_lengths if 200 <= l < 400) / len(orig_lengths) * 100,
        sum(1 for l in orig_lengths if 400 <= l < 700) / len(orig_lengths) * 100,
        sum(1 for l in orig_lengths if 700 <= l < 1000) / len(orig_lengths) * 100,
        sum(1 for l in orig_lengths if l >= 1000) / len(orig_lengths) * 100
    ]

    norm_dist = [
        sum(1 for l in norm_lengths if l < 200) / len(norm_lengths) * 100,
        sum(1 for l in norm_lengths if 200 <= l < 400) / len(norm_lengths) * 100,
        sum(1 for l in norm_lengths if 400 <= l < 700) / len(norm_lengths) * 100,
        sum(1 for l in norm_lengths if 700 <= l < 1000) / len(norm_lengths) * 100,
        sum(1 for l in norm_lengths if l >= 1000) / len(norm_lengths) * 100
    ]

    x = np.arange(len(categories))
    width = 0.35

    ax.bar(x - width/2, orig_dist, width, label='Original', color='coral', alpha=0.8)
    ax.bar(x + width/2, norm_dist, width, label='Normalized', color='steelblue', alpha=0.8)

    ax.set_ylabel('Percentage of Paragraphs (%)')
    ax.set_title('Size Distribution: Original vs Normalized')
    ax.set_xticks(x)
    ax.set_xticklabels(categories)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    # Add value labels on bars
    for i, (o, n) in enumerate(zip(orig_dist, norm_dist)):
        ax.text(i - width/2, o + 1, f'{o:.1f}%', ha='center', va='bottom', fontsize=8)
        ax.text(i + width/2, n + 1, f'{n:.1f}%', ha='center', va='bottom', fontsize=8)

    plt.tight_layout()
    plt.savefig(output_path / 'normalization_distribution_comparison.png', dpi=300)
    plt.close()

    print(f"\n✅ All comparison visualizations saved to: {output_path}/")


def print_example_transformations(original, normalized):
    """Print examples of split and merged paragraphs."""

    print("\n" + "="*80)
    print("EXAMPLE TRANSFORMATIONS")
    print("="*80)

    # Find examples of split paragraphs
    print("\n📊 EXAMPLE: LONG PARAGRAPH SPLIT")
    split_examples = [p for p in normalized if p.get('normalized') and p.get('chunk_index') == 0]

    if split_examples:
        example = split_examples[0]
        orig_para_num = example.get('original_paragraph_num')
        total_chunks = example.get('total_chunks', 1)

        print(f"\nOriginal paragraph #{orig_para_num} was split into {total_chunks} chunks")
        print(f"Document: {example['pdf_filename']}")

        # Find all chunks
        all_chunks = [p for p in normalized if p.get('original_paragraph_num') == orig_para_num]

        for i, chunk in enumerate(all_chunks[:3]):  # Show first 3 chunks
            print(f"\n  Chunk {i+1}/{len(all_chunks)} ({chunk['length']} chars):")
            print(f"    {chunk['text'][:150]}...")

    # Find examples of merged paragraphs
    print("\n\n📊 EXAMPLE: SHORT PARAGRAPHS MERGED")
    merge_examples = [p for p in normalized if p.get('merged_with')]

    if merge_examples:
        example = merge_examples[0]
        print(f"\nParagraph #{example['paragraph_num']} was created by merging:")
        print(f"Document: {example['pdf_filename']}")
        print(f"Length: {example['length']} chars")
        print(f"\nMerged text preview:")
        print(f"  {example['text'][:300]}...")


def main():
    """Execute comparison analysis."""

    print("="*80)
    print(" NORMALIZATION IMPACT ANALYSIS ".center(80, "="))
    print("="*80)
    print("\nComparing original vs semantically normalized paragraphs")
    print("="*80)

    # Load data
    original, normalized = load_data()

    # Print statistics
    print_statistics_comparison(original, normalized)

    # Create visualizations
    create_comparison_visualizations(original, normalized)

    # Show examples
    print_example_transformations(original, normalized)

    # Final summary
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)

    print("\n✅ Key Improvements:")
    orig_target = sum(1 for p in original if 400 <= p['length'] <= 700) / len(original) * 100
    norm_target = sum(1 for p in normalized if 400 <= p['length'] <= 700) / len(normalized) * 100
    print(f"  - Target range (400-700): {orig_target:.1f}% → {norm_target:.1f}% (+{norm_target - orig_target:.1f} pp)")

    orig_very_long = sum(1 for p in original if p['length'] >= 1000) / len(original) * 100
    norm_very_long = sum(1 for p in normalized if p['length'] >= 1000) / len(normalized) * 100
    print(f"  - Very long (1000+):      {orig_very_long:.1f}% → {norm_very_long:.1f}% ({norm_very_long - orig_very_long:.1f} pp)")

    print(f"\n📁 Output files:")
    print(f"  - visualizations/normalization_comparison_*.png (3 charts)")
    print(f"  - metadata/cf_normalized_paragraphs.json (ready for LLM)")

    print("\n🎯 Corpus is optimized for LLM-based fiscal tone classification!")
    print("="*80)


if __name__ == '__main__':
    main()
