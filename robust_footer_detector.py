"""
Robust Footer Line Detector - Eliminates False Positives

Key improvements based on user feedback:
1. Footer lines MUST start from left edge (x1 ≈ 0)
2. Footer lines MUST be isolated (no text above/below)
3. Checks spatial context to distinguish footer lines from word underlines
4. Handles fragmented lines (multiple short lines near each other)
"""

import numpy as np
import cv2
from PIL import Image
from typing import Optional, List, Dict, Tuple


# === Optimized Parameters ===

FOOTER_SEARCH_START = 0.75    # Start at 75% of page height
FOOTER_SEARCH_END = 0.95      # End at 95% of page height

LINE_MIN_LENGTH = 0.10        # Minimum 10% of page width
LINE_MAX_LENGTH = 0.40        # Maximum 40% of page width (increased slightly)

# NEW: Left edge constraint
LEFT_EDGE_TOLERANCE = 50      # Line must start within 50px of left edge

# NEW: Isolation checking
ISOLATION_CHECK_HEIGHT = 30   # Check 30px above and below line
ISOLATION_MIN_WHITESPACE = 0.85  # At least 85% white pixels = isolated

HOUGH_THRESHOLD = 50
MIN_LINE_LENGTH_PX = None
MAX_LINE_GAP = 10

SAFETY_MARGIN = 20
FALLBACK_POSITION = 0.807


def binarize_image(image: Image.Image) -> np.ndarray:
    """Binarize image using Otsu's method."""
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def is_isolated_line(binary: np.ndarray, line_y: int, x1: int, x2: int,
                     check_height: int = ISOLATION_CHECK_HEIGHT,
                     min_whitespace: float = ISOLATION_MIN_WHITESPACE) -> bool:
    """
    Checks if a line is isolated (no text above/below).

    A true footer line has whitespace around it.
    Word underlines have text directly above them.

    Args:
        binary: Binarized image
        line_y: Y-coordinate of line
        x1, x2: X-coordinates of line endpoints
        check_height: Pixels to check above and below
        min_whitespace: Minimum ratio of white pixels to be considered isolated

    Returns:
        True if line is isolated (likely footer), False if surrounded by text
    """
    height, width = binary.shape
    x_min = min(x1, x2)
    x_max = max(x1, x2)

    # Check region above line
    y_above_start = max(0, line_y - check_height)
    y_above_end = line_y
    region_above = binary[y_above_start:y_above_end, x_min:x_max]

    # Check region below line
    y_below_start = line_y + 1
    y_below_end = min(height, line_y + check_height)
    region_below = binary[y_below_start:y_below_end, x_min:x_max]

    # Calculate whitespace ratio
    if region_above.size > 0:
        whitespace_above = np.sum(region_above == 255) / region_above.size
    else:
        whitespace_above = 1.0

    if region_below.size > 0:
        whitespace_below = np.sum(region_below == 255) / region_below.size
    else:
        whitespace_below = 1.0

    # Line is isolated if BOTH above and below have sufficient whitespace
    is_isolated_above = whitespace_above >= min_whitespace
    is_isolated_below = whitespace_below >= min_whitespace

    return is_isolated_above and is_isolated_below


def detect_footer_separator_line(image: Image.Image,
                                 debug_path: Optional[str] = None) -> int:
    """
    Detects footer separator line with improved false positive elimination.

    Strategy:
    1. Binarize image
    2. Search bottom 20% of page (75-95%)
    3. Detect horizontal lines 10-40% width
    4. Filter: Line must start from LEFT EDGE (within 50px of x=0)
    5. Filter: Line must be ISOLATED (no text above/below)
    6. Select TOPMOST qualifying line
    7. Subtract safety margin

    Args:
        image: PIL Image
        debug_path: Optional path for debug visualization

    Returns:
        Y-coordinate where to crop (above footer)
    """
    height = image.height
    width = image.width

    # Binarize
    binary = binarize_image(image)

    # Search region (bottom 20%)
    search_start_y = int(height * FOOTER_SEARCH_START)
    search_end_y = int(height * FOOTER_SEARCH_END)
    search_region = binary[search_start_y:search_end_y, :]

    # Invert for line detection
    inverted = cv2.bitwise_not(search_region)

    # Calculate line length thresholds
    min_line_length_px = int(width * LINE_MIN_LENGTH)
    max_line_length_px = int(width * LINE_MAX_LENGTH)

    # Detect lines
    lines = cv2.HoughLinesP(
        inverted,
        rho=1,
        theta=np.pi / 180,
        threshold=HOUGH_THRESHOLD,
        minLineLength=min_line_length_px,
        maxLineGap=MAX_LINE_GAP
    )

    candidate_lines = []

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]

            # Filter 1: Horizontal lines only (within 5px vertical deviation)
            if abs(y2 - y1) > 5:
                continue

            # Calculate properties
            line_length = abs(x2 - x1)
            line_length_ratio = line_length / width
            actual_y = y1 + search_start_y

            # Filter 2: Line length must be 10-40% of page width
            if not (LINE_MIN_LENGTH <= line_length_ratio <= LINE_MAX_LENGTH):
                continue

            # Filter 3: NEW - Line must start from LEFT EDGE
            # Footer lines start from left, word underlines can be anywhere
            left_x = min(x1, x2)
            if left_x > LEFT_EDGE_TOLERANCE:
                # Skip - this line doesn't start from left edge
                # Likely a word underline or mid-page element
                continue

            # Filter 4: NEW - Line must be ISOLATED (no text around it)
            # Footer lines have whitespace above/below
            # Word underlines have text directly above them
            if not is_isolated_line(binary, actual_y, x1, x2):
                # Skip - this line has text around it (underline, not footer)
                continue

            # Line passes all filters - it's a valid footer separator candidate
            candidate_lines.append({
                'y': actual_y,
                'x1': x1,
                'x2': x2,
                'length': line_length,
                'length_ratio': line_length_ratio,
                'left_x': left_x
            })

    # Select TOPMOST qualifying line (earliest footer boundary)
    if candidate_lines:
        topmost_line = min(candidate_lines, key=lambda l: l['y'])
        footer_y = topmost_line['y'] - SAFETY_MARGIN

        # Ensure we don't crop above search region
        footer_y = max(footer_y, search_start_y)

        detection_method = "line_detected"
        num_candidates = len(candidate_lines)
        selected_line = topmost_line
    else:
        # Fallback (no qualifying footer line found)
        footer_y = int(height * FALLBACK_POSITION)
        detection_method = "fallback"
        num_candidates = 0
        selected_line = None

    # Debug visualization
    if debug_path:
        vis_img = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

        # Draw search region
        cv2.line(vis_img, (0, search_start_y), (width, search_start_y), (0, 255, 255), 2)
        cv2.line(vis_img, (0, search_end_y), (width, search_end_y), (0, 255, 255), 2)
        cv2.putText(vis_img, f"Search: {FOOTER_SEARCH_START:.0%}-{FOOTER_SEARCH_END:.0%}",
                   (10, search_start_y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

        # Draw all Hough-detected lines (before filtering) in RED
        # This shows what was rejected
        if lines is not None:
            rejected_count = 0
            for line in lines:
                x1, y1, x2, y2 = line[0]
                actual_y = y1 + search_start_y

                # Check if this line was accepted
                is_accepted = any(
                    c['y'] == actual_y and c['x1'] == x1 and c['x2'] == x2
                    for c in candidate_lines
                )

                if not is_accepted:
                    # Draw rejected lines in RED
                    cv2.line(vis_img, (x1, actual_y), (x2, actual_y), (0, 0, 255), 1)
                    rejected_count += 1

            if rejected_count > 0:
                cv2.putText(vis_img, f"{rejected_count} rejected (red)",
                           (10, search_start_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # Draw qualifying candidates in YELLOW
        if candidate_lines:
            for i, line in enumerate(candidate_lines):
                # Selected line in GREEN, others in YELLOW
                color = (0, 255, 0) if line == selected_line else (0, 255, 255)
                thickness = 4 if line == selected_line else 2

                cv2.line(vis_img, (line['x1'], line['y']), (line['x2'], line['y']), color, thickness)

                # Label
                label = f"{line['length_ratio']:.1%}"
                cv2.putText(vis_img, label, (line['x1'] + 5, line['y'] - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        # Draw final crop line
        cv2.line(vis_img, (0, footer_y), (width, footer_y), (255, 0, 255), 4)
        cv2.putText(vis_img,
                   f"CROP: {footer_y}px ({footer_y/height:.1%}) | {detection_method} | {num_candidates} valid",
                   (10, footer_y - 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)

        # Add legend
        legend_y = 50
        cv2.putText(vis_img, "RED: Rejected (not from left OR has text around)",
                   (10, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        cv2.putText(vis_img, "YELLOW: Valid candidates (from left + isolated)",
                   (10, legend_y + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.putText(vis_img, "GREEN: Selected footer line (topmost)",
                   (10, legend_y + 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

        # Save
        import os
        os.makedirs(os.path.dirname(debug_path) or '.', exist_ok=True)
        cv2.imwrite(debug_path, vis_img)

    return footer_y


# === Testing Function ===

def test_robust_detector():
    """
    Tests robust detector specifically on false positive cases.
    """
    from pdf2image import convert_from_path
    import os

    print("="*80)
    print("TESTING ROBUST FOOTER DETECTOR - False Positive Cases")
    print("="*80)
    print("\nTesting on problematic PDFs identified by user:\n")

    test_cases = [
        ("data/raw/scanned/Informe_CF_N_001-2016.pdf", [1, 2]),  # False positives
        ("data/raw/scanned/INFORME_N_002-2017-CF.pdf", [1, 2, 3]),  # Mix of good/bad
    ]

    output_folder = "robust_footer_test"
    os.makedirs(output_folder, exist_ok=True)

    for pdf_path, pages_to_test in test_cases:
        if not os.path.exists(pdf_path):
            continue

        filename = os.path.basename(pdf_path).replace('.pdf', '')
        print(f"[Testing] {filename}")

        images = convert_from_path(pdf_path, dpi=300)

        for page_num in pages_to_test:
            if page_num > len(images):
                continue

            image = images[page_num - 1]

            if image.height <= image.width:
                print(f"  Page {page_num}: Skipped (horizontal)")
                continue

            debug_path = os.path.join(output_folder, f"{filename}_page{page_num}_robust.png")

            footer_y = detect_footer_separator_line(image, debug_path=debug_path)

            print(f"  Page {page_num}: Footer at {footer_y}px ({footer_y/image.height:.1%})")
            print(f"              Visualization: {debug_path}")

    print(f"\n{'='*80}")
    print(f"Test visualizations saved to: {output_folder}/")
    print(f"{'='*80}")
    print("\nKey improvements:")
    print("  - RED lines = Rejected (not from left OR has text around)")
    print("  - YELLOW lines = Valid candidates (from left + isolated)")
    print("  - GREEN line = Selected footer line")
    print("\nCompare with old detection in footer_detector_test/")


if __name__ == "__main__":
    test_robust_detector()
