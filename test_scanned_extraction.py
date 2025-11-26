"""
Test script for scanned PDF extraction with OCR best practices.
Tests binarization, logo detection, and footer detection.
"""

import os
import cv2
import numpy as np
from pdf2image import convert_from_path
from scanned_pdf_extractor import (
    binarize_image,
    denoise_binary,
    detect_black_square_logo,
    detect_footer_region,
    extract_from_pdf
)


def test_binarization():
    """Test binarization on sample pages"""
    print("\n" + "="*80)
    print("TEST 1: Binarization Quality")
    print("="*80)

    pdf_path = "data/raw/scanned/INFORME_N_002-2017-CF.pdf"

    if not os.path.exists(pdf_path):
        print(f"[Skip] {pdf_path} not found")
        return

    images = convert_from_path(pdf_path, dpi=300)

    # Test on first page
    page1 = images[0]
    print(f"\nOriginal image: {page1.width} x {page1.height}")

    # Test different binarization methods
    methods = ['otsu', 'adaptive', 'fixed']

    os.makedirs("test_results", exist_ok=True)

    for method in methods:
        binary = binarize_image(page1, method=method)
        denoised = denoise_binary(binary)

        # Save results
        cv2.imwrite(f"test_results/binary_{method}.png", binary)
        cv2.imwrite(f"test_results/binary_{method}_denoised.png", denoised)

        # Calculate statistics
        black_ratio = 1.0 - (np.sum(binary == 255) / binary.size)
        print(f"  {method:10s}: {black_ratio*100:.1f}% black pixels")

    print(f"\n[+] Saved to test_results/binary_*.png")


def test_logo_detection():
    """Test black square logo detection"""
    print("\n" + "="*80)
    print("TEST 2: Black Square Logo Detection")
    print("="*80)

    test_pdfs = [
        "data/raw/scanned/INFORME_N_001-2017-CF.pdf",
        "data/raw/scanned/INFORME_N_002-2017-CF.pdf"
    ]

    os.makedirs("test_results", exist_ok=True)

    for pdf_path in test_pdfs:
        if not os.path.exists(pdf_path):
            continue

        filename = os.path.basename(pdf_path)
        print(f"\n{filename}:")

        images = convert_from_path(pdf_path, dpi=300)

        # Test on page 2 (should have logo)
        if len(images) >= 2:
            page2 = images[1]
            print(f"  Page 2: {page2.width} x {page2.height}")

            logo_bottom = detect_black_square_logo(
                page2,
                debug_path=f"test_results/{filename[:-4]}_page2_logo_detection.png"
            )

            if logo_bottom:
                print(f"  [+] Logo detected at Y={logo_bottom} ({logo_bottom/page2.height*100:.1f}%)")
                print(f"    Crop starts at: {logo_bottom + 10} px")
            else:
                print(f"  [-] Logo not detected - will use 8% fallback")


def test_footer_detection():
    """Test footer detection with comprehensive debug output"""
    print("\n" + "="*80)
    print("TEST 3: Footer Detection (Lines + Density)")
    print("="*80)

    test_pdfs = [
        "data/raw/scanned/INFORME_N_001-2017-CF.pdf",
        "data/raw/scanned/INFORME_N_002-2017-CF.pdf",
        "data/raw/scanned/INFORME_N_003-2017-CF.pdf"
    ]

    for pdf_path in test_pdfs:
        if not os.path.exists(pdf_path):
            continue

        filename = os.path.basename(pdf_path)
        filename_base = filename.replace('.pdf', '')
        print(f"\n{filename}:")

        images = convert_from_path(pdf_path, dpi=300)

        # Test on first 2 pages
        for page_num, image in enumerate(images[:2], start=1):
            print(f"  Page {page_num}:", end=" ")

            footer_y = detect_footer_region(
                image,
                filename_base=filename_base,
                page_num=page_num,
                debug=True  # This creates detailed visualizations
            )

            print(f"Footer at Y={footer_y} ({footer_y/image.height*100:.1f}%)")

    print(f"\n[+] Check 'footer_inspection/' folder for detailed visualizations")
    print(f"  - *_footer_analysis.png: Shows lines, density, and final crop")
    print(f"  - *_density_profile.png: Text density graph")


def test_full_extraction():
    """Test full extraction on one PDF"""
    print("\n" + "="*80)
    print("TEST 4: Full Extraction")
    print("="*80)

    pdf_path = "data/raw/scanned/INFORME_N_001-2017-CF.pdf"

    if not os.path.exists(pdf_path):
        print(f"[Skip] {pdf_path} not found")
        return

    page_records = extract_from_pdf(pdf_path, debug=True)

    print("\n" + "-"*80)
    print("EXTRACTION RESULTS")
    print("-"*80)
    print(f"Pages extracted: {len(page_records)}")

    if page_records:
        # Show first page
        first = page_records[0]
        print(f"\nFirst page record:")
        print(f"  Filename: {first['filename']}")
        print(f"  Page: {first['page']}")
        print(f"  Text length: {len(first['text'])} characters")
        print(f"\n  First 500 characters:")
        print(f"  {first['text'][:500]}")
        print("  ...")

        # Show statistics
        total_chars = sum(len(r['text']) for r in page_records)
        avg_chars = total_chars / len(page_records)
        print(f"\nStatistics:")
        print(f"  Total characters: {total_chars}")
        print(f"  Average per page: {avg_chars:.0f}")


def main():
    """Run all tests"""
    print("="*80)
    print("TESTING SCANNED PDF EXTRACTION WITH OCR BEST PRACTICES")
    print("="*80)
    print("\nThis will test:")
    print("1. Binarization quality (Otsu, Adaptive, Fixed)")
    print("2. Black square logo detection (density-based)")
    print("3. Footer detection (lines + density on last 3/4)")
    print("4. Full extraction pipeline")
    print()

    test_binarization()
    test_logo_detection()
    test_footer_detection()
    test_full_extraction()

    print("\n" + "="*80)
    print("ALL TESTS COMPLETE")
    print("="*80)
    print("\nGenerated folders:")
    print("  - test_results/       : Binarization and logo detection tests")
    print("  - footer_inspection/  : Detailed footer analysis (REVIEW THIS!)")
    print()
    print("IMPORTANT: Review footer_inspection/ folder to verify footer detection")
    print("           is correctly identifying footer boundaries on all pages")


if __name__ == "__main__":
    main()
