"""
Comprehensive comparison between original and robust footer detectors.
Tests both on all 90 pages to measure false positive elimination vs detection rate.
"""

import os
import pandas as pd
from pdf2image import convert_from_path
from PIL import Image

# Import both detectors
from footer_detector import detect_footer_separator_line as detect_original
from robust_footer_detector import detect_footer_separator_line as detect_robust


SCANNED_FOLDER = "data/raw/scanned"
OUTPUT_FOLDER = "detector_comparison"
DPI = 300


def compare_detectors():
    """
    Tests both detectors on all pages and generates comparative report.
    """
    print("="*80)
    print("FOOTER DETECTOR PERFORMANCE COMPARISON")
    print("="*80)
    print("\nComparing original vs robust detector on all 90 pages...\n")

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

                # Test ORIGINAL detector
                footer_y_original = detect_original(image)
                ratio_original = footer_y_original / image.height

                # Test ROBUST detector
                footer_y_robust = detect_robust(image)
                ratio_robust = footer_y_robust / image.height

                # Calculate difference
                diff_px = footer_y_robust - footer_y_original
                diff_ratio = ratio_robust - ratio_original

                # Classify detection methods
                # Original uses fallback at 80.7%
                original_method = "fallback" if abs(ratio_original - 0.807) < 0.001 else "detected"
                robust_method = "fallback" if abs(ratio_robust - 0.807) < 0.001 else "detected"

                results.append({
                    'pdf': pdf_file,
                    'page': page_num,
                    'original_y': footer_y_original,
                    'original_ratio': ratio_original,
                    'original_method': original_method,
                    'robust_y': footer_y_robust,
                    'robust_ratio': ratio_robust,
                    'robust_method': robust_method,
                    'diff_px': diff_px,
                    'diff_ratio': diff_ratio,
                    'agreement': original_method == robust_method,
                    'image_height': image.height,
                    'image_width': image.width
                })

                # Brief output
                if original_method != robust_method:
                    print(f"  Page {page_num}: DIFFER - Original={original_method} Robust={robust_method}")
                else:
                    print(f"  Page {page_num}: {original_method}")

        except Exception as e:
            print(f"  Error: {e}")

    # Create DataFrame
    df = pd.DataFrame(results)

    # Save detailed results
    csv_path = os.path.join(OUTPUT_FOLDER, "comparison_results.csv")
    df.to_csv(csv_path, index=False)

    # Generate report
    print("\n" + "="*80)
    print("COMPARISON RESULTS")
    print("="*80)

    print(f"\nTotal pages tested: {total_pages}")

    # Original detector stats
    original_detected = len(df[df['original_method'] == 'detected'])
    original_fallback = len(df[df['original_method'] == 'fallback'])
    print(f"\nOriginal Detector:")
    print(f"  Line detection: {original_detected} ({original_detected/total_pages*100:.1f}%)")
    print(f"  Fallback: {original_fallback} ({original_fallback/total_pages*100:.1f}%)")

    # Robust detector stats
    robust_detected = len(df[df['robust_method'] == 'detected'])
    robust_fallback = len(df[df['robust_method'] == 'fallback'])
    print(f"\nRobust Detector:")
    print(f"  Line detection: {robust_detected} ({robust_detected/total_pages*100:.1f}%)")
    print(f"  Fallback: {robust_fallback} ({robust_fallback/total_pages*100:.1f}%)")

    # Agreement analysis
    agreement = len(df[df['agreement']])
    disagreement = len(df[~df['agreement']])
    print(f"\nAgreement:")
    print(f"  Same method: {agreement} ({agreement/total_pages*100:.1f}%)")
    print(f"  Different method: {disagreement} ({disagreement/total_pages*100:.1f}%)")

    # Analyze disagreements
    if disagreement > 0:
        print(f"\n{'='*80}")
        print("DISAGREEMENT ANALYSIS")
        print("="*80)

        # Original detected, Robust fallback (potentially over-strict)
        over_strict = df[(df['original_method'] == 'detected') & (df['robust_method'] == 'fallback')]
        if len(over_strict) > 0:
            print(f"\n[!] Robust detector is MORE STRICT: {len(over_strict)} pages")
            print("    (Original detected line, Robust used fallback)")
            print("    These could be:")
            print("      - False positives eliminated (GOOD)")
            print("      - Real footer lines rejected (BAD)")
            print("\n    Top 10 cases:")
            for _, row in over_strict.head(10).iterrows():
                print(f"      {row['pdf']} page {row['page']}: {row['original_ratio']:.1%} -> {row['robust_ratio']:.1%}")

        # Robust detected, Original fallback (potentially finding new lines)
        less_strict = df[(df['original_method'] == 'fallback') & (df['robust_method'] == 'detected')]
        if len(less_strict) > 0:
            print(f"\n[!] Robust detector is LESS STRICT: {len(less_strict)} pages")
            print("    (Original used fallback, Robust detected line)")
            print("    This is unexpected - original should be more permissive")
            for _, row in less_strict.head(10).iterrows():
                print(f"      {row['pdf']} page {row['page']}: {row['original_ratio']:.1%} -> {row['robust_ratio']:.1%}")

    # Position difference analysis
    print(f"\n{'='*80}")
    print("POSITION DIFFERENCE ANALYSIS")
    print("="*80)

    # Only for pages where both detected lines (not fallback)
    both_detected = df[(df['original_method'] == 'detected') & (df['robust_method'] == 'detected')]
    if len(both_detected) > 0:
        print(f"\n{len(both_detected)} pages where BOTH detectors found lines:")
        print(f"  Mean difference: {both_detected['diff_ratio'].mean():.3f} ({both_detected['diff_px'].mean():.1f}px)")
        print(f"  Std deviation: {both_detected['diff_ratio'].std():.3f}")
        print(f"  Max difference: {both_detected['diff_ratio'].max():.3f} ({both_detected['diff_px'].max():.0f}px)")

        # Check for identical detections
        identical = both_detected[abs(both_detected['diff_px']) < 1]
        print(f"\n  Identical detections: {len(identical)} ({len(identical)/len(both_detected)*100:.1f}%)")
        print(f"  Different detections: {len(both_detected) - len(identical)} ({(len(both_detected)-len(identical))/len(both_detected)*100:.1f}%)")
    else:
        print("\nNo pages where both detectors found lines (all disagreements)")

    # Summary
    print(f"\n{'='*80}")
    print("RECOMMENDATION")
    print("="*80)

    if robust_detected >= original_detected * 0.95:
        print("\n[+] Robust detector maintains similar detection rate (>=95%)")
        print("    While eliminating known false positives.")
        print("    RECOMMENDED: Use robust detector")
    elif robust_detected >= original_detected * 0.80:
        print("\n[o] Robust detector has moderate detection drop (80-95%)")
        print("    Trade-off: Fewer false positives vs lower detection")
        print("    NEEDS REVIEW: Check disagreement cases manually")
    else:
        print("\n[!] Robust detector has significant detection drop (<80%)")
        print("    May be too strict - rejecting real footer lines")
        print("    RECOMMENDED: Relax parameters or investigate cases")

    print(f"\n[+] Detailed results saved to: {csv_path}")

    return df


if __name__ == "__main__":
    results_df = compare_detectors()
