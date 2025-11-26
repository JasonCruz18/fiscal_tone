"""
Comprehensive verification of footer exclusion across all 90 pages.
Tests the focused footer detector on every page to ensure 100% exclusion.
"""

import os
import cv2
import numpy as np
from pdf2image import convert_from_path
from PIL import Image
import pandas as pd
from footer_detector import detect_footer_separator_line, binarize_image


SCANNED_FOLDER = "data/raw/scanned"
OUTPUT_FOLDER = "footer_exclusion_verification"
DPI = 300


def verify_all_pages():
    """
    Tests footer detection on all pages and generates comprehensive report.
    """
    print("="*80)
    print("COMPREHENSIVE FOOTER EXCLUSION VERIFICATION")
    print("="*80)
    print("\nTesting focused footer detector on all pages...")
    print("This will verify 100% footer exclusion across 13 PDFs\n")

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    pdf_files = sorted([f for f in os.listdir(SCANNED_FOLDER) if f.lower().endswith('.pdf')])

    results = []
    total_pages = 0
    pages_with_detection = 0
    pages_with_fallback = 0

    for idx, pdf_file in enumerate(pdf_files, start=1):
        pdf_path = os.path.join(SCANNED_FOLDER, pdf_file)
        filename_base = pdf_file.replace('.pdf', '')

        print(f"[{idx}/{len(pdf_files)}] {pdf_file}")

        try:
            images = convert_from_path(pdf_path, dpi=DPI)

            for page_num, image in enumerate(images, start=1):
                # Skip horizontal pages
                if image.height <= image.width:
                    print(f"  Page {page_num}: Skipped (horizontal)")
                    continue

                total_pages += 1

                # Detect footer (with debug output for first page of first 3 PDFs)
                debug_path = None
                if idx <= 3 and page_num == 1:
                    debug_path = os.path.join(OUTPUT_FOLDER, f"{filename_base}_page{page_num}_verify.png")

                footer_y = detect_footer_separator_line(image, debug_path=debug_path)

                # Calculate metrics
                footer_ratio = footer_y / image.height
                excluded_region = image.height - footer_y
                excluded_ratio = excluded_region / image.height

                # Classify detection method (check if fallback was used)
                # Re-detect to get method info
                binary = binarize_image(image)
                search_start_y = int(image.height * 0.75)
                search_end_y = int(image.height * 0.95)
                search_region = binary[search_start_y:search_end_y, :]
                inverted = cv2.bitwise_not(search_region)

                min_line_length_px = int(image.width * 0.10)

                lines = cv2.HoughLinesP(
                    inverted, rho=1, theta=np.pi/180, threshold=50,
                    minLineLength=min_line_length_px, maxLineGap=10
                )

                detected_lines = []
                if lines is not None:
                    for line in lines:
                        x1, y1, x2, y2 = line[0]
                        if abs(y2 - y1) <= 5:
                            line_length = abs(x2 - x1)
                            line_length_ratio = line_length / image.width
                            if 0.10 <= line_length_ratio <= 0.35:
                                detected_lines.append((y1 + search_start_y, line_length_ratio))

                if detected_lines:
                    method = "line_detected"
                    pages_with_detection += 1
                    num_lines = len(detected_lines)
                else:
                    method = "fallback"
                    pages_with_fallback += 1
                    num_lines = 0

                results.append({
                    'pdf': pdf_file,
                    'page': page_num,
                    'footer_y': footer_y,
                    'footer_ratio': footer_ratio,
                    'excluded_px': excluded_region,
                    'excluded_ratio': excluded_ratio,
                    'method': method,
                    'num_lines': num_lines,
                    'image_height': image.height,
                    'image_width': image.width
                })

                # Brief output
                if num_lines > 0:
                    print(f"  Page {page_num}: [+] {footer_ratio:.1%} ({num_lines} lines)")
                else:
                    print(f"  Page {page_num}: [o] {footer_ratio:.1%} (fallback)")

        except Exception as e:
            print(f"  Error: {e}")

    # Create DataFrame
    df = pd.DataFrame(results)

    # Save detailed results
    csv_path = os.path.join(OUTPUT_FOLDER, "verification_results.csv")
    df.to_csv(csv_path, index=False)

    # Generate report
    print("\n" + "="*80)
    print("VERIFICATION RESULTS")
    print("="*80)

    print(f"\nTotal pages tested: {total_pages}")
    print(f"Pages with line detection: {pages_with_detection} ({pages_with_detection/total_pages*100:.1f}%)")
    print(f"Pages using fallback: {pages_with_fallback} ({pages_with_fallback/total_pages*100:.1f}%)")

    print(f"\nFooter Position Statistics:")
    print(f"  Min: {df['footer_ratio'].min():.1%}")
    print(f"  Max: {df['footer_ratio'].max():.1%}")
    print(f"  Mean: {df['footer_ratio'].mean():.1%}")
    print(f"  Median: {df['footer_ratio'].median():.1%}")
    print(f"  Std Dev: {df['footer_ratio'].std():.3f}")

    print(f"\nExcluded Region Statistics (footer size):")
    print(f"  Min excluded: {df['excluded_ratio'].min():.1%}")
    print(f"  Max excluded: {df['excluded_ratio'].max():.1%}")
    print(f"  Mean excluded: {df['excluded_ratio'].mean():.1%}")

    # Check for potential issues
    print(f"\n" + "="*80)
    print("QUALITY CHECKS")
    print("="*80)

    # Check 1: Pages cropping too high (might lose content)
    too_high = df[df['footer_ratio'] < 0.70]
    if len(too_high) > 0:
        print(f"\n[!] WARNING: {len(too_high)} pages cropping below 70% (might lose content)")
        for _, row in too_high.iterrows():
            print(f"  {row['pdf']} page {row['page']}: {row['footer_ratio']:.1%}")
    else:
        print(f"\n[+] No pages cropping too high (all >= 70%)")

    # Check 2: Pages cropping too low (might include footer)
    too_low = df[df['footer_ratio'] > 0.90]
    if len(too_low) > 0:
        print(f"\n[!] WARNING: {len(too_low)} pages cropping above 90% (might include footer)")
        for _, row in too_low.iterrows():
            print(f"  {row['pdf']} page {row['page']}: {row['footer_ratio']:.1%}")
    else:
        print(f"\n[+] No pages cropping too low (all <= 90%)")

    # Check 3: Consistency
    if df['footer_ratio'].std() < 0.05:
        print(f"\n[+] Excellent consistency (std dev: {df['footer_ratio'].std():.3f})")
    else:
        print(f"\n[o] Moderate consistency (std dev: {df['footer_ratio'].std():.3f})")

    # Summary
    print(f"\n" + "="*80)
    print("FOOTER EXCLUSION VERIFICATION: ", end="")

    if pages_with_detection == total_pages:
        print("100% SUCCESS [+]")
        print("="*80)
        print("\nAll pages have detectable footer separator lines!")
        print("Footer exclusion strategy is OPTIMAL for this dataset.")
    elif pages_with_detection >= total_pages * 0.95:
        print(">95% SUCCESS [+]")
        print("="*80)
        print(f"\n{pages_with_detection/total_pages*100:.1f}% of pages use line detection.")
        print(f"{pages_with_fallback} pages use safe fallback at 80.7%.")
        print("Footer exclusion strategy is HIGHLY RELIABLE.")
    else:
        print("NEEDS REVIEW")
        print("="*80)
        print(f"\nOnly {pages_with_detection/total_pages*100:.1f}% of pages detected lines.")
        print("Recommend parameter adjustment.")

    print(f"\n[+] Detailed results saved to: {csv_path}")
    print(f"[+] Sample visualizations in: {OUTPUT_FOLDER}/")

    return df


if __name__ == "__main__":
    results_df = verify_all_pages()
