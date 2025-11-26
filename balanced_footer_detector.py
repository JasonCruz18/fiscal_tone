"""
Balanced Footer Line Detector - Based on diagnostic findings

Key insights from diagnostics:
1. Footer lines are NOT at x=0 - they're centered/indented (x=300-600px range)
2. Footer lines are 10-40% width (consistently validated)
3. Footer lines are ISOLATED (no text above/below) - this is the key discriminator
4. False positives (word underlines) have text directly above them

Strategy:
- Remove strict left-edge constraint (was rejecting 100% of footer lines)
- Keep isolation check as primary filter
- Add horizontal position filter (footer lines in left-center region, not far right)
- Relaxed isolation threshold for better detection
"""

import numpy as np
import cv2
from PIL import Image
from typing import Optional


# === Optimized Parameters ===

FOOTER_SEARCH_START = 0.75    # Start at 75% of page height
FOOTER_SEARCH_END = 0.95      # End at 95% of page height

LINE_MIN_LENGTH = 0.10        # Minimum 10% of page width
LINE_MAX_LENGTH = 0.40        # Maximum 40% of page width

# NEW: Horizontal position constraint
# Footer lines are in left-center region (not far right)
MAX_LEFT_X_RATIO = 0.60       # Line must start within left 60% of page

# Isolation checking (optimized for balance)
ISOLATION_CHECK_HEIGHT = 30   # Check 30px above and below line
ISOLATION_MIN_WHITESPACE = 0.65  # At least 65% white pixels = isolated

HOUGH_THRESHOLD = 50
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
                     min_whitespace: float = ISOLATION_MIN_WHITESPACE) -> tuple:
    """
    Checks if a line is isolated (no text above/below).

    Returns:
        (is_isolated, whitespace_above, whitespace_below)
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
    is_isolated = whitespace_above >= min_whitespace and whitespace_below >= min_whitespace

    return is_isolated, whitespace_above, whitespace_below


def detect_footer_separator_line(image: Image.Image,
                                 debug_path: Optional[str] = None) -> int:
    """
    Detects footer separator line with balanced false positive elimination.

    Strategy:
    1. Binarize image
    2. Search bottom 20% of page (75-95%)
    3. Detect horizontal lines 10-40% width
    4. Filter: Line must start in left-center region (left 60% of page)
    5. Filter: Line must be ISOLATED (no text above/below) - KEY DISCRIMINATOR
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
    rejected_lines = []

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]

            # Filter 1: Horizontal lines only (within 5px vertical deviation)
            if abs(y2 - y1) > 5:
                rejected_lines.append({
                    'x1': x1, 'y': y1 + search_start_y, 'x2': x2,
                    'reason': 'not_horizontal'
                })
                continue

            # Calculate properties
            line_length = abs(x2 - x1)
            line_length_ratio = line_length / width
            actual_y = y1 + search_start_y
            left_x = min(x1, x2)
            left_x_ratio = left_x / width

            # Filter 2: Line length must be 10-40% of page width
            if not (LINE_MIN_LENGTH <= line_length_ratio <= LINE_MAX_LENGTH):
                rejected_lines.append({
                    'x1': x1, 'y': actual_y, 'x2': x2,
                    'reason': 'wrong_length'
                })
                continue

            # Filter 3: NEW - Line must start in left-center region (not far right)
            # This allows centered footer lines but rejects far-right elements
            if left_x_ratio > MAX_LEFT_X_RATIO:
                rejected_lines.append({
                    'x1': x1, 'y': actual_y, 'x2': x2,
                    'reason': 'too_far_right'
                })
                continue

            # Filter 4: Line must be ISOLATED (no text around it)
            # This is the KEY discriminator between footer lines and word underlines
            is_isolated, ws_above, ws_below = is_isolated_line(binary, actual_y, x1, x2)

            if not is_isolated:
                rejected_lines.append({
                    'x1': x1, 'y': actual_y, 'x2': x2,
                    'reason': 'not_isolated',
                    'ws_above': ws_above,
                    'ws_below': ws_below
                })
                continue

            # Line passes all filters - it's a valid footer separator candidate
            candidate_lines.append({
                'y': actual_y,
                'x1': x1,
                'x2': x2,
                'length': line_length,
                'length_ratio': line_length_ratio,
                'left_x': left_x,
                'left_x_ratio': left_x_ratio,
                'ws_above': ws_above,
                'ws_below': ws_below
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

        # Draw max left-x threshold
        max_left_x_px = int(width * MAX_LEFT_X_RATIO)
        cv2.line(vis_img, (max_left_x_px, search_start_y),
                (max_left_x_px, search_end_y), (255, 128, 0), 1)

        # Draw rejected lines in RED
        for r in rejected_lines:
            cv2.line(vis_img, (r['x1'], r['y']), (r['x2'], r['y']), (0, 0, 255), 1)

        # Draw qualifying candidates in YELLOW/GREEN
        if candidate_lines:
            for line in candidate_lines:
                # Selected line in GREEN, others in YELLOW
                color = (0, 255, 0) if line == selected_line else (0, 255, 255)
                thickness = 4 if line == selected_line else 2

                cv2.line(vis_img, (line['x1'], line['y']), (line['x2'], line['y']), color, thickness)

                # Label
                label = f"{line['length_ratio']:.1%} iso:{line['ws_above']:.0%}/{line['ws_below']:.0%}"
                cv2.putText(vis_img, label, (line['x1'] + 5, line['y'] - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

        # Draw final crop line
        cv2.line(vis_img, (0, footer_y), (width, footer_y), (255, 0, 255), 4)
        cv2.putText(vis_img,
                   f"CROP: {footer_y}px ({footer_y/height:.1%}) | {detection_method} | {num_candidates} valid | {len(rejected_lines)} rejected",
                   (10, footer_y - 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)

        # Add legend
        legend_y = 50
        cv2.putText(vis_img, "RED: Rejected", (10, legend_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        cv2.putText(vis_img, "YELLOW: Valid candidates", (10, legend_y + 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.putText(vis_img, "GREEN: Selected footer line", (10, legend_y + 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        cv2.putText(vis_img, f"ORANGE: Max left-x ({MAX_LEFT_X_RATIO:.0%})", (10, legend_y + 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 128, 0), 1)

        # Save
        import os
        os.makedirs(os.path.dirname(debug_path) or '.', exist_ok=True)
        cv2.imwrite(debug_path, vis_img)

    return footer_y


# === Testing Function ===

def test_balanced_detector():
    """
    Tests balanced detector on both false positive and good cases.
    """
    from pdf2image import convert_from_path
    import os

    print("="*80)
    print("TESTING BALANCED FOOTER DETECTOR")
    print("="*80)
    print("\nTesting on mix of good and problematic cases:\\n")

    test_cases = [
        ("data/raw/scanned/INFORME_N_002-2017-CF.pdf", [2, 3]),  # Perfect cases
        ("data/raw/scanned/Informe_CF_N_001-2016.pdf", [1, 2]),  # False positive cases
    ]

    output_folder = "balanced_footer_test"
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

            debug_path = os.path.join(output_folder, f"{filename}_page{page_num}_balanced.png")

            footer_y = detect_footer_separator_line(image, debug_path=debug_path)

            print(f"  Page {page_num}: Footer at {footer_y}px ({footer_y/image.height:.1%})")
            print(f"              Visualization: {debug_path}")

    print(f"\n{'='*80}")
    print(f"Test visualizations saved to: {output_folder}/")
    print(f"{'='*80}")


if __name__ == "__main__":
    test_balanced_detector()
