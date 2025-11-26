"""
Comprehensive test of balanced detector on all 90 pages.
Compares performance against original detector.
"""

import os
import pandas as pd
from pdf2image import convert_from_path

from footer_detector import detect_footer_separator_line as detect_original
from balanced_footer_detector import detect_footer_separator_line as detect_balanced


SCANNED_FOLDER = "data/raw/scanned"
OUTPUT_FOLDER = "balanced_comprehensive_test"
DPI = 300


def test_all_pages():
    """
    Tests balanced detector on all pages and compares with original.
    """
    print("="*80)
    print("BALANCED DETECTOR COMPREHENSIVE TEST")
    print("="*80)
    print("\nTesting on all 90 pages...\n")

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    pdf_files = sorted([f for f in os.listdir(SCANNED_FOLDER) if f.lower().endswith('.pdf')])

    results = []
    total_pages = 0

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

                # Test both detectors
                footer_y_original = detect_original(image)
                footer_y_balanced = detect_balanced(image)

                ratio_original = footer_y_original / image.height
                ratio_balanced = footer_y_balanced / image.height

                # Classify methods
                original_method = "fallback" if abs(ratio_original - 0.807) < 0.001 else "detected"
                balanced_method = "fallback" if abs(ratio_balanced - 0.807) < 0.001 else "detected"

                results.append({
                    'pdf': pdf_file,
                    'page': page_num,
                    'original_y': footer_y_original,
                    'original_ratio': ratio_original,
                    'original_method': original_method,
                    'balanced_y': footer_y_balanced,
                    'balanced_ratio': ratio_balanced,
                    'balanced_method': balanced_method,
                    'diff_px': footer_y_balanced - footer_y_original,
                    'diff_ratio': ratio_balanced - ratio_original,
                    'image_height': image.height
                })

                # Brief output
                if balanced_method == 'detected':
                    print(f"  Page {page_num}: [+] {ratio_balanced:.1%}")
                else:
                    print(f"  Page {page_num}: [o] {ratio_balanced:.1%} (fallback)")

        except Exception as e:
            print(f"  Error: {e}")

    # Create DataFrame
    df = pd.DataFrame(results)

    # Save results
    csv_path = os.path.join(OUTPUT_FOLDER, "balanced_test_results.csv")
    df.to_csv(csv_path, index=False)

    # Generate report
    print("\n" + "="*80)
    print("COMPREHENSIVE TEST RESULTS")
    print("="*80)

    print(f"\nTotal pages tested: {total_pages}")

    # Original detector stats
    original_detected = len(df[df['original_method'] == 'detected'])
    original_fallback = len(df[df['original_method'] == 'fallback'])

    # Balanced detector stats
    balanced_detected = len(df[df['balanced_method'] == 'detected'])
    balanced_fallback = len(df[df['balanced_method'] == 'fallback'])

    print(f"\nOriginal Detector:")
    print(f"  Line detection: {original_detected} ({original_detected/total_pages*100:.1f}%)")
    print(f"  Fallback: {original_fallback} ({original_fallback/total_pages*100:.1f}%)")

    print(f"\nBalanced Detector:")
    print(f"  Line detection: {balanced_detected} ({balanced_detected/total_pages*100:.1f}%)")
    print(f"  Fallback: {balanced_fallback} ({balanced_fallback/total_pages*100:.1f}%)")

    # Detection rate comparison
    print(f"\n{'='*80}")
    print("DETECTION RATE ANALYSIS")
    print(f"{'='*80}\n")

    detection_rate_change = (balanced_detected - original_detected) / original_detected * 100
    print(f"Detection rate change: {detection_rate_change:+.1f}%")
    print(f"  Original: {original_detected}/{total_pages} ({original_detected/total_pages*100:.1f}%)")
    print(f"  Balanced: {balanced_detected}/{total_pages} ({balanced_detected/total_pages*100:.1f}%)")

    # Position statistics
    print(f"\n{'='*80}")
    print("FOOTER POSITION STATISTICS")
    print(f"{'='*80}\n")

    balanced_detected_df = df[df['balanced_method'] == 'detected']

    if len(balanced_detected_df) > 0:
        print(f"Balanced detector (line detected cases only):")
        print(f"  Min: {balanced_detected_df['balanced_ratio'].min():.1%}")
        print(f"  Max: {balanced_detected_df['balanced_ratio'].max():.1%}")
        print(f"  Mean: {balanced_detected_df['balanced_ratio'].mean():.1%}")
        print(f"  Median: {balanced_detected_df['balanced_ratio'].median():.1%}")
        print(f"  Std Dev: {balanced_detected_df['balanced_ratio'].std():.3f}")

    # Quality checks
    print(f"\n{'='*80}")
    print("QUALITY CHECKS")
    print(f"{'='*80}\n")

    # Check for pages cropping too low (might include footer)
    too_low = df[df['balanced_ratio'] > 0.90]
    if len(too_low) > 0:
        print(f"[!] WARNING: {len(too_low)} pages cropping above 90% (might include footer)")
        for _, row in too_low.head(10).iterrows():
            print(f"  {row['pdf']} page {row['page']}: {row['balanced_ratio']:.1%} ({row['balanced_method']})")
    else:
        print(f"[+] No pages cropping too low (all <= 90%)")

    # Check for pages cropping too high (might lose content)
    too_high = df[df['balanced_ratio'] < 0.70]
    if len(too_high) > 0:
        print(f"\n[!] WARNING: {len(too_high)} pages cropping below 70% (might lose content)")
        for _, row in too_high.head(10).iterrows():
            print(f"  {row['pdf']} page {row['page']}: {row['balanced_ratio']:.1%} ({row['balanced_method']})")
    else:
        print(f"\n[+] No pages cropping too high (all >= 70%)")

    # Summary
    print(f"\n{'='*80}")
    print("RECOMMENDATION")
    print(f"{'='*80}\n")

    if balanced_detected >= original_detected * 0.90:
        print(f"[+] Balanced detector maintains {balanced_detected/original_detected*100:.1f}% of original detection rate")
        print(f"    With improved false positive handling")
        if balanced_detected >= original_detected:
            print(f"    EXCELLENT: Detection rate maintained or improved!")
        else:
            print(f"    GOOD: Minor detection drop acceptable for better accuracy")
    else:
        print(f"[o] Balanced detector has {100 - balanced_detected/original_detected*100:.1f}% detection drop")
        print(f"    May need parameter tuning")

    print(f"\n[+] Detailed results saved to: {csv_path}")

    return df


if __name__ == "__main__":
    results_df = test_all_pages()
