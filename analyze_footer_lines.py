"""
Comprehensive footer line analysis across all scanned PDFs.
Analyzes line patterns to develop robust 100% footer exclusion strategy.
"""

import os
import json
import numpy as np
import cv2
from pdf2image import convert_from_path
from PIL import Image
import pandas as pd
from collections import defaultdict


# === Configuration ===
SCANNED_FOLDER = "data/raw/scanned"
OUTPUT_FOLDER = "footer_line_analysis"
DPI = 300


def binarize_image(image):
    """Binarize image using Otsu's method."""
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def detect_all_horizontal_lines(image, search_start_ratio=0.25, search_end_ratio=0.95):
    """
    Detects ALL horizontal lines in the bottom portion of the page.

    Args:
        image: PIL Image
        search_start_ratio: Start searching at this percentage of page height
        search_end_ratio: End searching at this percentage

    Returns:
        List of line dictionaries with detailed properties
    """
    height = image.height
    width = image.width

    # Binarize
    binary = binarize_image(image)

    # Search region
    search_start_y = int(height * search_start_ratio)
    search_end_y = int(height * search_end_ratio)
    search_region = binary[search_start_y:search_end_y, :]

    # Invert for line detection
    inverted = cv2.bitwise_not(search_region)

    # Detect lines with VERY permissive parameters to catch everything
    lines = cv2.HoughLinesP(
        inverted,
        rho=1,
        theta=np.pi/180,
        threshold=30,  # Lower threshold to detect more lines
        minLineLength=int(width * 0.10),  # Minimum 10% of width
        maxLineGap=15
    )

    detected_lines = []

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]

            # Only horizontal lines (within 5 degrees of horizontal)
            if abs(y2 - y1) > 5:
                continue

            # Calculate properties
            actual_y = y1 + search_start_y  # Adjust to full image coordinates
            line_length = abs(x2 - x1)
            line_length_ratio = line_length / width
            rel_position = actual_y / height

            # Calculate line thickness by examining pixels around it
            y_check = min(actual_y, height - 5)
            line_region = binary[y_check-2:y_check+3, x1:x2] if x1 < x2 else binary[y_check-2:y_check+3, x2:x1]

            if line_region.size > 0:
                thickness = 5 - (np.sum(line_region == 255) / line_region.size) * 5
            else:
                thickness = 1

            detected_lines.append({
                'y': actual_y,
                'x1': x1,
                'x2': x2,
                'length': line_length,
                'length_ratio': line_length_ratio,
                'rel_position': rel_position,
                'thickness': thickness
            })

    # Sort by Y position (top to bottom)
    detected_lines.sort(key=lambda l: l['y'])

    return detected_lines


def analyze_single_pdf(pdf_path, debug=True):
    """
    Analyzes all pages in a single PDF for footer lines.

    Returns:
        List of page analysis results
    """
    filename = os.path.basename(pdf_path)
    filename_base = filename.replace('.pdf', '')

    print(f"\n[Analyzing] {filename}")

    try:
        images = convert_from_path(pdf_path, dpi=DPI)
        page_results = []

        for page_num, image in enumerate(images, start=1):
            # Skip horizontal pages
            if image.height <= image.width:
                print(f"  Page {page_num}: Skipped (horizontal)")
                continue

            # Detect all lines
            lines = detect_all_horizontal_lines(image)

            print(f"  Page {page_num}: {len(lines)} lines detected")

            # Debug visualization
            if debug and lines:
                os.makedirs(OUTPUT_FOLDER, exist_ok=True)

                binary = binarize_image(image)
                vis_img = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

                # Draw all lines with color coding by length
                for i, line in enumerate(lines):
                    # Color by length ratio
                    if line['length_ratio'] < 0.15:
                        color = (0, 0, 255)  # Red - very short
                    elif line['length_ratio'] < 0.25:
                        color = (0, 165, 255)  # Orange - short
                    elif line['length_ratio'] < 0.40:
                        color = (0, 255, 255)  # Yellow - medium
                    else:
                        color = (0, 255, 0)  # Green - long

                    cv2.line(vis_img, (line['x1'], line['y']), (line['x2'], line['y']), color, 2)

                    # Label with position and length
                    label = f"{line['rel_position']:.1%} | {line['length_ratio']:.1%}"
                    cv2.putText(vis_img, label, (line['x1'], line['y'] - 5),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

                # Save
                output_path = os.path.join(OUTPUT_FOLDER, f"{filename_base}_page{page_num}_all_lines.png")
                cv2.imwrite(output_path, vis_img)

            # Store results
            page_results.append({
                'filename': filename,
                'page': page_num,
                'total_lines': len(lines),
                'lines': lines,
                'image_height': image.height,
                'image_width': image.width
            })

        return page_results

    except Exception as e:
        print(f"  Error: {e}")
        return []


def analyze_all_pdfs():
    """
    Analyzes all PDFs in the scanned folder.

    Returns:
        Comprehensive statistics and patterns
    """
    print("="*80)
    print("COMPREHENSIVE FOOTER LINE ANALYSIS")
    print("="*80)

    pdf_files = sorted([f for f in os.listdir(SCANNED_FOLDER) if f.lower().endswith('.pdf')])
    print(f"\nFound {len(pdf_files)} PDF files")

    all_results = []

    for pdf_file in pdf_files:
        pdf_path = os.path.join(SCANNED_FOLDER, pdf_file)
        results = analyze_single_pdf(pdf_path, debug=True)
        all_results.extend(results)

    return all_results


def generate_statistics(all_results):
    """
    Generates comprehensive statistics from all detected lines.
    """
    print("\n" + "="*80)
    print("STATISTICAL ANALYSIS")
    print("="*80)

    # Overall statistics
    total_pages = len(all_results)
    pages_with_lines = len([r for r in all_results if r['total_lines'] > 0])
    pages_without_lines = total_pages - pages_with_lines

    print(f"\nOverall:")
    print(f"  Total pages analyzed: {total_pages}")
    print(f"  Pages WITH lines: {pages_with_lines} ({pages_with_lines/total_pages*100:.1f}%)")
    print(f"  Pages WITHOUT lines: {pages_without_lines} ({pages_without_lines/total_pages*100:.1f}%)")

    # Collect all lines
    all_lines = []
    for result in all_results:
        for line in result['lines']:
            all_lines.append({
                'filename': result['filename'],
                'page': result['page'],
                **line
            })

    if not all_lines:
        print("\n[!] No lines detected in any PDF!")
        return

    # Create DataFrame for analysis
    df = pd.DataFrame(all_lines)

    print(f"\nTotal lines detected: {len(df)}")
    print(f"Average lines per page: {len(df) / total_pages:.1f}")

    # Position analysis
    print(f"\nLine Position Statistics (Y position as % of page height):")
    print(f"  Min position: {df['rel_position'].min():.1%}")
    print(f"  Max position: {df['rel_position'].max():.1%}")
    print(f"  Mean position: {df['rel_position'].mean():.1%}")
    print(f"  Median position: {df['rel_position'].median():.1%}")
    print(f"  25th percentile: {df['rel_position'].quantile(0.25):.1%}")
    print(f"  75th percentile: {df['rel_position'].quantile(0.75):.1%}")

    # Length analysis
    print(f"\nLine Length Statistics (% of page width):")
    print(f"  Min length: {df['length_ratio'].min():.1%}")
    print(f"  Max length: {df['length_ratio'].max():.1%}")
    print(f"  Mean length: {df['length_ratio'].mean():.1%}")
    print(f"  Median length: {df['length_ratio'].median():.1%}")
    print(f"  25th percentile: {df['length_ratio'].quantile(0.25):.1%}")
    print(f"  75th percentile: {df['length_ratio'].quantile(0.75):.1%}")

    # Categorize lines by length
    print(f"\nLine Distribution by Length:")
    very_short = len(df[df['length_ratio'] < 0.15])
    short = len(df[(df['length_ratio'] >= 0.15) & (df['length_ratio'] < 0.25)])
    medium = len(df[(df['length_ratio'] >= 0.25) & (df['length_ratio'] < 0.40)])
    long = len(df[df['length_ratio'] >= 0.40])

    print(f"  Very short (< 15%): {very_short} ({very_short/len(df)*100:.1f}%)")
    print(f"  Short (15-25%): {short} ({short/len(df)*100:.1f}%)")
    print(f"  Medium (25-40%): {medium} ({medium/len(df)*100:.1f}%)")
    print(f"  Long (>= 40%): {long} ({long/len(df)*100:.1f}%)")

    # Position distribution for different lengths (footer lines are typically short and in bottom region)
    print(f"\nPosition Analysis by Line Length Category:")
    for category, min_len, max_len in [
        ("Very short (< 15%)", 0, 0.15),
        ("Short (15-25%)", 0.15, 0.25),
        ("Medium (25-40%)", 0.25, 0.40),
        ("Long (>= 40%)", 0.40, 1.0)
    ]:
        subset = df[(df['length_ratio'] >= min_len) & (df['length_ratio'] < max_len)]
        if len(subset) > 0:
            print(f"\n  {category}:")
            print(f"    Count: {len(subset)}")
            print(f"    Avg position: {subset['rel_position'].mean():.1%}")
            print(f"    Position range: {subset['rel_position'].min():.1%} - {subset['rel_position'].max():.1%}")

    # Lines in footer region (70%+)
    footer_region_lines = df[df['rel_position'] >= 0.70]
    print(f"\nLines in Footer Region (70%+ of page):")
    print(f"  Total: {len(footer_region_lines)} ({len(footer_region_lines)/len(df)*100:.1f}% of all lines)")
    if len(footer_region_lines) > 0:
        print(f"  Average length: {footer_region_lines['length_ratio'].mean():.1%}")
        print(f"  Most common length range: {footer_region_lines['length_ratio'].median():.1%}")

    # Save detailed CSV
    csv_path = os.path.join(OUTPUT_FOLDER, "all_lines_detailed.csv")
    df.to_csv(csv_path, index=False)
    print(f"\n[+] Detailed line data saved to: {csv_path}")

    # Recommendations
    print("\n" + "="*80)
    print("RECOMMENDATIONS FOR FOOTER DETECTION")
    print("="*80)

    # Find optimal parameters
    footer_lines = df[df['rel_position'] >= 0.60]  # Lines in bottom 40%

    if len(footer_lines) > 0:
        # Most footer lines are short
        optimal_min_length = footer_lines['length_ratio'].quantile(0.10)
        optimal_max_length = footer_lines['length_ratio'].quantile(0.90)
        optimal_search_start = footer_lines['rel_position'].min() - 0.05  # 5% buffer

        print(f"\nBased on detected patterns:")
        print(f"  1. Search region: Start at {optimal_search_start:.1%} of page height")
        print(f"  2. Line length filter: {optimal_min_length:.1%} - {optimal_max_length:.1%} of page width")
        print(f"  3. Use TOPMOST line in search region for crop point")
        print(f"  4. Safety margin: 15-20 pixels above detected line")

    # Pages without lines
    if pages_without_lines > 0:
        print(f"\n  NOTE: {pages_without_lines} pages have NO lines detected")
        print(f"        These need fallback strategy (suggest: crop at 72% of page height)")

    return df


if __name__ == "__main__":
    # Run analysis
    results = analyze_all_pdfs()

    # Generate statistics
    if results:
        stats_df = generate_statistics(results)

        print("\n" + "="*80)
        print("ANALYSIS COMPLETE")
        print("="*80)
        print(f"\nReview folder: {OUTPUT_FOLDER}/")
        print("  - *_all_lines.png: Visual inspection of all detected lines")
        print("  - all_lines_detailed.csv: Complete data for further analysis")
    else:
        print("\n[!] No results to analyze")
