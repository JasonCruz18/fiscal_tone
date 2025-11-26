"""
Identifies true footer separator lines from all detected lines.
Focuses on bottom 15-20% of page where footer separators appear.
"""

import pandas as pd
import numpy as np


def analyze_footer_separators():
    """
    Analyzes lines specifically in the footer region to identify separator patterns.
    """
    print("="*80)
    print("FOOTER SEPARATOR LINE IDENTIFICATION")
    print("="*80)

    # Load all lines data
    df = pd.read_csv("footer_line_analysis/all_lines_detailed.csv")
    print(f"\nTotal lines detected: {len(df)}")

    # Focus on bottom 15% of pages (85-95% range) where footer separators appear
    FOOTER_REGION_START = 0.80
    FOOTER_REGION_END = 0.95

    footer_lines = df[(df['rel_position'] >= FOOTER_REGION_START) &
                      (df['rel_position'] <= FOOTER_REGION_END)]

    print(f"Lines in footer region (80-95%): {len(footer_lines)}")
    print(f"  Percentage of all lines: {len(footer_lines)/len(df)*100:.1f}%")

    # Analyze by page
    print(f"\n" + "="*80)
    print("PER-PAGE FOOTER LINE ANALYSIS")
    print("="*80)

    # Group by document and page
    grouped = footer_lines.groupby(['filename', 'page'])

    results = []

    for (filename, page), group in grouped:
        # For each page, find the TOPMOST line in footer region
        # This is the footer separator
        if len(group) == 0:
            continue

        topmost_line = group.loc[group['rel_position'].idxmin()]

        results.append({
            'filename': filename,
            'page': page,
            'footer_separator_y': topmost_line['rel_position'],
            'separator_length': topmost_line['length_ratio'],
            'total_footer_lines': len(group),
            'topmost_line_y_px': topmost_line['y']
        })

    results_df = pd.DataFrame(results)

    # Statistics
    print(f"\nPages with footer lines detected: {len(results_df)}")
    print(f"\nFooter Separator Statistics:")
    print(f"  Position (% of page height):")
    print(f"    Min: {results_df['footer_separator_y'].min():.1%}")
    print(f"    Max: {results_df['footer_separator_y'].max():.1%}")
    print(f"    Mean: {results_df['footer_separator_y'].mean():.1%}")
    print(f"    Median: {results_df['footer_separator_y'].median():.1%}")
    print(f"    Std Dev: {results_df['footer_separator_y'].std():.3f}")

    print(f"\n  Length (% of page width):")
    print(f"    Min: {results_df['separator_length'].min():.1%}")
    print(f"    Max: {results_df['separator_length'].max():.1%}")
    print(f"    Mean: {results_df['separator_length'].mean():.1%}")
    print(f"    Median: {results_df['separator_length'].median():.1%}")

    # Distribution analysis
    print(f"\n  Position Distribution:")
    print(f"    80-85%: {len(results_df[results_df['footer_separator_y'] < 0.85])}")
    print(f"    85-90%: {len(results_df[(results_df['footer_separator_y'] >= 0.85) & (results_df['footer_separator_y'] < 0.90)])}")
    print(f"    90-95%: {len(results_df[results_df['footer_separator_y'] >= 0.90])}")

    # Save results
    results_df.to_csv("footer_line_analysis/footer_separators_identified.csv", index=False)
    print(f"\n[+] Saved to: footer_line_analysis/footer_separators_identified.csv")

    # Recommendations
    print(f"\n" + "="*80)
    print("RECOMMENDED FOOTER DETECTION STRATEGY")
    print("="*80)

    # Find optimal search range
    min_pos = results_df['footer_separator_y'].min()
    median_pos = results_df['footer_separator_y'].median()

    recommended_search_start = max(0.75, min_pos - 0.05)  # Start 5% before earliest
    recommended_search_end = 0.95

    print(f"\n1. SEARCH REGION:")
    print(f"   Start: {recommended_search_start:.1%} of page height")
    print(f"   End: {recommended_search_end:.1%} of page height")
    print(f"   Rationale: Captures {min_pos:.1%} (earliest) to {results_df['footer_separator_y'].max():.1%} (latest)")

    print(f"\n2. LINE LENGTH FILTER:")
    print(f"   Min: 10% of page width")
    print(f"   Max: 35% of page width")
    print(f"   Rationale: Footer separators are typically short lines")

    print(f"\n3. SELECTION STRATEGY:")
    print(f"   Use: TOPMOST line in search region")
    print(f"   Rationale: Footer separator is the first line marking footer boundary")

    print(f"\n4. SAFETY MARGIN:")
    print(f"   Subtract: 20 pixels from detected line Y position")
    print(f"   Rationale: Ensures no footer content is included")

    print(f"\n5. FALLBACK (if no line found):")
    print(f"   Crop at: {median_pos:.1%} of page height")
    print(f"   Rationale: Median position of detected footer separators")

    # Check coverage
    print(f"\n" + "="*80)
    print("COVERAGE ANALYSIS")
    print("="*80)

    # How many pages would be covered by this strategy?
    total_pages_analyzed = df.groupby(['filename', 'page']).ngroups
    pages_with_footer_lines = len(results_df)

    print(f"\nTotal pages: {total_pages_analyzed}")
    print(f"Pages with detectable footer lines: {pages_with_footer_lines}")
    print(f"Coverage: {pages_with_footer_lines/total_pages_analyzed*100:.1f}%")
    print(f"Pages needing fallback: {total_pages_analyzed - pages_with_footer_lines}")

    return results_df


if __name__ == "__main__":
    results = analyze_footer_separators()
