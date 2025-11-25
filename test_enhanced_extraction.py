"""
Test script for enhanced scanned PDF extraction.
Tests on the example PDFs to verify cropping boundaries.
"""

import os
from enhanced_scanned_ocr import extract_text_from_scanned_pdf, get_adaptive_crop_boundaries
from pdf2image import convert_from_path
import cv2
import numpy as np


def visualize_crop_boundaries(pdf_path, output_folder="test_results"):
    """
    Creates visualization showing the exact crop boundaries applied.
    """
    os.makedirs(output_folder, exist_ok=True)
    filename = os.path.basename(pdf_path).replace('.pdf', '')

    print(f"\n{'='*80}")
    print(f"Testing: {filename}")
    print(f"{'='*80}")

    try:
        images = convert_from_path(pdf_path, dpi=300)

        for page_num, image in enumerate(images[:2], start=1):  # Test first 2 pages
            print(f"\nPage {page_num}:")

            # Get crop boundaries
            top_y, bottom_y = get_adaptive_crop_boundaries(image, page_num)

            print(f"  Image size: {image.width} x {image.height}")
            print(f"  Top crop: {top_y} px ({top_y/image.height*100:.1f}%)")
            print(f"  Bottom crop: {bottom_y} px ({bottom_y/image.height*100:.1f}%)")
            print(f"  Content region: {bottom_y - top_y} px")

            # Create visualization with blue box
            vis_img = np.array(image).copy()

            # Draw crop region with BLUE box (matching your examples)
            cv2.rectangle(vis_img,
                         (0, top_y),
                         (image.width, bottom_y),
                         (0, 0, 255),  # Blue color
                         10)  # Thick border

            # Add labels
            cv2.putText(vis_img, f"TOP CROP: {top_y/image.height*100:.1f}%",
                       (20, top_y - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)

            cv2.putText(vis_img, f"BOTTOM CROP: {bottom_y/image.height*100:.1f}%",
                       (20, bottom_y + 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 255), 3)

            # Save visualization
            vis_path = os.path.join(output_folder, f"{filename}_page{page_num}_test.png")
            cv2.imwrite(vis_path, cv2.cvtColor(vis_img, cv2.COLOR_RGB2BGR))
            print(f"  Saved: {vis_path}")

            # Also save just the cropped region
            cropped = image.crop((0, top_y, image.width, bottom_y))
            crop_path = os.path.join(output_folder, f"{filename}_page{page_num}_cropped.png")
            cropped.save(crop_path)
            print(f"  Saved: {crop_path}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


def test_full_extraction(pdf_path):
    """
    Tests full extraction pipeline on a PDF.
    """
    print(f"\n{'='*80}")
    print(f"FULL EXTRACTION TEST")
    print(f"{'='*80}")

    paragraphs = extract_text_from_scanned_pdf(pdf_path, debug=True)

    print(f"\n{'='*80}")
    print(f"EXTRACTION RESULTS")
    print(f"{'='*80}")
    print(f"Total paragraphs extracted: {len(paragraphs)}")

    if paragraphs:
        print(f"\nFirst 3 paragraphs:")
        for i, para in enumerate(paragraphs[:3], 1):
            print(f"\n--- Paragraph {i} (Page {para['page']}) ---")
            print(f"{para['text'][:200]}...")
            print(f"Length: {len(para['text'])} characters")

        print(f"\nParagraph distribution by page:")
        from collections import Counter
        page_counts = Counter(p['page'] for p in paragraphs)
        for page, count in sorted(page_counts.items()):
            print(f"  Page {page}: {count} paragraphs")


def main():
    """
    Main test function - tests on example PDFs.
    """
    scanned_folder = "data/raw/scanned"

    # Test PDFs (the ones from your examples)
    test_pdfs = [
        "INFORME_N_001-2017-CF.pdf",
        "INFORME_N_002-2017-CF.pdf",
    ]

    print("="*80)
    print("TESTING ENHANCED SCANNED PDF EXTRACTION")
    print("="*80)
    print("\nThis test will:")
    print("1. Visualize crop boundaries with blue boxes")
    print("2. Extract text using the enhanced pipeline")
    print("3. Show sample paragraphs")
    print()

    for pdf_file in test_pdfs:
        pdf_path = os.path.join(scanned_folder, pdf_file)

        if not os.path.exists(pdf_path):
            print(f"\n[Skip] {pdf_file} not found")
            continue

        # Test 1: Visualize boundaries
        visualize_crop_boundaries(pdf_path)

        # Test 2: Full extraction
        test_full_extraction(pdf_path)

        print("\n" + "="*80 + "\n")

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("\nPlease review:")
    print("1. test_results/ folder - Compare blue boxes with your examples")
    print("2. debug_enhanced_ocr/ folder - Detailed line detection visuals")
    print("\nIf boundaries match your examples, the implementation is correct!")


if __name__ == "__main__":
    main()
