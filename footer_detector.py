"""
Focused Footer Line Detector - 100% Exclusion Strategy

Based on comprehensive analysis of 90 pages from 13 PDFs:
- Footer separator lines appear at 75-95% of page height
- Lines are 10-35% of page width (median: 12.6%)
- 100% of pages have detectable lines in this region
- Topmost line in region marks footer boundary
"""

import numpy as np
import cv2
from PIL import Image
from typing import Optional


# === Optimized Parameters (from empirical analysis) ===

FOOTER_SEARCH_START = 0.75    # Start at 75% of page height
FOOTER_SEARCH_END = 0.95      # End at 95% of page height

LINE_MIN_LENGTH = 0.10        # Minimum 10% of page width
LINE_MAX_LENGTH = 0.35        # Maximum 35% of page width

HOUGH_THRESHOLD = 50          # Line detection sensitivity
MIN_LINE_LENGTH_PX = None     # Will be calculated per-image
MAX_LINE_GAP = 10             # Maximum gap in line pixels

SAFETY_MARGIN = 20            # Pixels to subtract from detected line

FALLBACK_POSITION = 0.807     # 80.7% - median from analysis (rarely needed)


def binarize_image(image: Image.Image) -> np.ndarray:
    """
    Binarize image using Otsu's method.

    Args:
        image: PIL Image

    Returns:
        Binary numpy array
    """
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def detect_footer_separator_line(image: Image.Image,
                                 debug_path: Optional[str] = None) -> int:
    """
    Detects footer separator line using focused search strategy.

    Strategy:
    1. Binarize image
    2. Search bottom 20% of page (75-95% region)
    3. Detect horizontal lines 10-35% of page width
    4. Select TOPMOST line (earliest footer boundary)
    5. Subtract safety margin

    Args:
        image: PIL Image
        debug_path: Optional path to save debug visualization

    Returns:
        Y-coordinate where to crop (above footer)
    """
    height = image.height
    width = image.width

    # Binarize
    binary = binarize_image(image)

    # Define search region (bottom 20% of page)
    search_start_y = int(height * FOOTER_SEARCH_START)
    search_end_y = int(height * FOOTER_SEARCH_END)
    search_region = binary[search_start_y:search_end_y, :]

    # Invert for line detection (black lines on white background)
    inverted = cv2.bitwise_not(search_region)

    # Calculate minimum line length in pixels
    min_line_length_px = int(width * LINE_MIN_LENGTH)
    max_line_length_px = int(width * LINE_MAX_LENGTH)

    # Detect lines using Hough transform
    lines = cv2.HoughLinesP(
        inverted,
        rho=1,
        theta=np.pi / 180,
        threshold=HOUGH_THRESHOLD,
        minLineLength=min_line_length_px,
        maxLineGap=MAX_LINE_GAP
    )

    detected_lines = []

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]

            # Filter: Only horizontal lines (within 5 pixels vertical deviation)
            if abs(y2 - y1) > 5:
                continue

            # Calculate line properties
            line_length = abs(x2 - x1)
            line_length_ratio = line_length / width

            # Filter: Line length must be 10-35% of page width
            if not (LINE_MIN_LENGTH <= line_length_ratio <= LINE_MAX_LENGTH):
                continue

            # Adjust Y to full image coordinates
            actual_y = y1 + search_start_y

            detected_lines.append({
                'y': actual_y,
                'x1': x1,
                'x2': x2,
                'length': line_length,
                'length_ratio': line_length_ratio
            })

    # Select TOPMOST line (earliest footer marker)
    if detected_lines:
        topmost_line = min(detected_lines, key=lambda l: l['y'])
        footer_y = topmost_line['y'] - SAFETY_MARGIN

        # Ensure we don't crop above search region
        footer_y = max(footer_y, search_start_y)

        detection_method = "line_detected"
        num_lines = len(detected_lines)
    else:
        # Fallback (should rarely happen - 100% coverage in analysis)
        footer_y = int(height * FALLBACK_POSITION)
        detection_method = "fallback"
        num_lines = 0
        topmost_line = None

    # Debug visualization
    if debug_path:
        vis_img = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

        # Draw search region boundaries
        cv2.line(vis_img, (0, search_start_y), (width, search_start_y), (0, 255, 255), 2)
        cv2.line(vis_img, (0, search_end_y), (width, search_end_y), (0, 255, 255), 2)
        cv2.putText(vis_img, f"Search: {FOOTER_SEARCH_START:.0%}-{FOOTER_SEARCH_END:.0%}",
                   (10, search_start_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Draw all detected lines
        if detected_lines:
            for i, line in enumerate(detected_lines):
                # Color code: Green for selected, Yellow for others
                color = (0, 255, 0) if line == topmost_line else (0, 255, 255)
                thickness = 4 if line == topmost_line else 2

                cv2.line(vis_img, (line['x1'], line['y']), (line['x2'], line['y']), color, thickness)

                # Label
                label = f"{line['length_ratio']:.1%}"
                cv2.putText(vis_img, label, (line['x1'], line['y'] - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        # Draw final crop line
        cv2.line(vis_img, (0, footer_y), (width, footer_y), (0, 0, 255), 4)
        cv2.putText(vis_img,
                   f"CROP: {footer_y}px ({footer_y/height:.1%}) | {detection_method} | {num_lines} lines",
                   (10, footer_y - 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Save
        import os
        os.makedirs(os.path.dirname(debug_path) or '.', exist_ok=True)
        cv2.imwrite(debug_path, vis_img)

    return footer_y


# === Testing Function ===

def test_footer_detector():
    """
    Tests footer detector on sample PDFs.
    """
    from pdf2image import convert_from_path
    import os

    print("="*80)
    print("TESTING FOCUSED FOOTER DETECTOR")
    print("="*80)

    test_pdfs = [
        "data/raw/scanned/INFORME_N_002-2017-CF.pdf",
        "data/raw/scanned/Informe_CF_N_001-2016.pdf"
    ]

    output_folder = "footer_detector_test"
    os.makedirs(output_folder, exist_ok=True)

    for pdf_path in test_pdfs:
        if not os.path.exists(pdf_path):
            continue

        filename = os.path.basename(pdf_path).replace('.pdf', '')
        print(f"\n[Testing] {filename}")

        images = convert_from_path(pdf_path, dpi=300)

        for page_num, image in enumerate(images[:3], start=1):  # Test first 3 pages
            if image.height <= image.width:
                print(f"  Page {page_num}: Skipped (horizontal)")
                continue

            debug_path = os.path.join(output_folder, f"{filename}_page{page_num}_footer.png")

            footer_y = detect_footer_separator_line(image, debug_path=debug_path)

            print(f"  Page {page_num}: Footer at {footer_y}px ({footer_y/image.height:.1%})")

    print(f"\n[+] Test visualizations saved to: {output_folder}/")
    print("="*80)


if __name__ == "__main__":
    test_footer_detector()
