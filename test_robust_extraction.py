"""
Test script for robust scanned PDF extraction.
Tests logo detection, orientation filtering, and paragraph markers.
"""

import os
import cv2
import numpy as np
from pdf2image import convert_from_path
from robust_scanned_extraction import (
    detect_red_logo_baseline,
    detect_content_start_y,
    detect_footer_line_hough,
    is_vertical_page,
    extract_from_scanned_pdf
)


def test_logo_detection():
    """Test red CF logo detection on page 2+"""
    print("\n" + "="*80)
    print("TEST 1: Red CF Logo Detection")
    print("="*80)

    pdf_path = "data/raw/scanned/INFORME_N_002-2017-CF.pdf"

    if not os.path.exists(pdf_path):
        print(f"[Skip] {pdf_path} not found")
        return

    images = convert_from_path(pdf_path, dpi=300)

    # Test on page 2 (should have logo)
    if len(images) >= 2:
        page2 = images[1]
        print(f"\nPage 2 size: {page2.width} x {page2.height}")

        logo_bottom = detect_red_logo_baseline(
            page2,
            debug_path="test_results/logo_detection_page2.png"
        )

        if logo_bottom:
            print(f"✓ Logo detected! Bottom Y = {logo_bottom} ({logo_bottom/page2.height*100:.1f}%)")
            print(f"  Crop will start at: {logo_bottom + 10} px")

            # Create visualization
            img_array = np.array(page2)
            crop_y = logo_bottom + 10
            cv2.line(img_array, (0, crop_y), (page2.width, crop_y), (0, 0, 255), 5)
            cv2.putText(img_array, f"CROP LINE: {crop_y/page2.height*100:.1f}%",
                       (20, crop_y - 20), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)

            os.makedirs("test_results", exist_ok=True)
            cv2.imwrite("test_results/logo_crop_line.png", cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR))
            print(f"  Saved: test_results/logo_crop_line.png")
        else:
            print("✗ Logo not detected - will use fallback (8%)")


def test_page1_content_detection():
    """Test dynamic content start detection for page 1"""
    print("\n" + "="*80)
    print("TEST 2: Page 1 Content Start Detection")
    print("="*80)

    pdf_path = "data/raw/scanned/INFORME_N_001-2017-CF.pdf"

    if not os.path.exists(pdf_path):
        print(f"[Skip] {pdf_path} not found")
        return

    images = convert_from_path(pdf_path, dpi=300)
    page1 = images[0]

    print(f"\nPage 1 size: {page1.width} x {page1.height}")

    content_start = detect_content_start_y(page1)
    print(f"✓ Content starts at: {content_start} px ({content_start/page1.height*100:.1f}%)")

    # Visualize
    img_array = np.array(page1)
    cv2.line(img_array, (0, content_start), (page1.width, content_start), (0, 255, 0), 5)
    cv2.putText(img_array, f"CONTENT START: {content_start/page1.height*100:.1f}%",
               (20, content_start + 50), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)

    os.makedirs("test_results", exist_ok=True)
    cv2.imwrite("test_results/page1_content_start.png", cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR))
    print(f"Saved: test_results/page1_content_start.png")


def test_orientation_filter():
    """Test orientation filtering"""
    print("\n" + "="*80)
    print("TEST 3: Orientation Filtering")
    print("="*80)

    # Test on available PDFs
    test_pdfs = [
        "data/raw/scanned/INFORME_N_001-2017-CF.pdf",
        "data/raw/scanned/INFORME_N_002-2017-CF.pdf"
    ]

    for pdf_path in test_pdfs:
        if not os.path.exists(pdf_path):
            continue

        filename = os.path.basename(pdf_path)
        print(f"\n{filename}:")

        images = convert_from_path(pdf_path, dpi=300)

        for i, img in enumerate(images[:3], 1):  # Check first 3 pages
            is_vertical = is_vertical_page(img)
            orientation = "VERTICAL (OK)" if is_vertical else "HORIZONTAL (SKIP)"
            print(f"  Page {i}: {img.width}x{img.height} -> {orientation}")


def test_full_extraction():
    """Test full extraction on sample PDF"""
    print("\n" + "="*80)
    print("TEST 4: Full Extraction with Paragraph Markers")
    print("="*80)

    pdf_path = "data/raw/scanned/INFORME_N_001-2017-CF.pdf"

    if not os.path.exists(pdf_path):
        print(f"[Skip] {pdf_path} not found")
        return

    result = extract_from_scanned_pdf(pdf_path, debug=True)

    print("\n" + "-"*80)
    print("EXTRACTION RESULT")
    print("-"*80)
    print(f"Success: {result['success']}")
    print(f"Pages processed: {result['pages_processed']}")
    print(f"Total characters: {len(result['text'])}")

    if result['text']:
        print(f"\nFirst 800 characters:")
        print(result['text'][:800])
        print("\n...")

        # Count paragraph breaks
        paragraph_count = result['text'].count('\n\n')
        print(f"\nParagraph markers (\\n\\n) found: {paragraph_count}")


def main():
    """Run all tests"""
    print("="*80)
    print("TESTING ROBUST SCANNED PDF EXTRACTION")
    print("="*80)
    print("\nThis will test:")
    print("1. Red CF logo detection (page 2+)")
    print("2. Dynamic content start detection (page 1)")
    print("3. Orientation filtering")
    print("4. Full extraction with paragraph markers")
    print()

    # Run tests
    test_logo_detection()
    test_page1_content_detection()
    test_orientation_filter()
    test_full_extraction()

    print("\n" + "="*80)
    print("ALL TESTS COMPLETE")
    print("="*80)
    print("\nCheck test_results/ and debug_extraction/ folders for visualizations")


if __name__ == "__main__":
    main()
