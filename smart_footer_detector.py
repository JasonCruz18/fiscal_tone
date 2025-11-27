"""
Smart Footer Line Detector - Horizontal Sampling Strategy

Key insight: Real footer separator lines are ISOLATED at their exact Y-coordinate.
Word underlines have text characters directly to their left/right at the SAME Y.

Strategy:
1. Detect horizontal lines in footer region (75-95%)
2. For each line, sample pixels EXACTLY at line's Y-coordinate to left and right
3. Footer lines: whitespace to left/right at same Y
4. Word underlines: black pixels (text) to left/right at same Y
5. Select bottom-most isolated line

This avoids false positives from word underlines embedded in text flow.
"""

import cv2
import numpy as np
from pdf2image import convert_from_path
import pytesseract
from pathlib import Path
import json

# Tesseract configuration
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'

# Footer detection parameters
FOOTER_SEARCH_START = 0.75    # Start search at 75% from top
FOOTER_SEARCH_END = 0.95      # End search at 95% from top
LINE_MIN_LENGTH = 0.10        # Minimum 10% of page width
LINE_MAX_LENGTH = 0.35        # Maximum 35% of page width
FALLBACK_POSITION = 0.807     # Median position from previous analysis

# Horizontal sampling parameters
SAMPLE_DISTANCE = 50          # Pixels to sample left/right of line
SAMPLE_WIDTH = 30             # Width of sampling region
TEXT_BLACKNESS_THRESHOLD = 0.10  # 10% black pixels indicates text presence

# Vertical isolation parameters
VERTICAL_CHECK_HEIGHT = 40    # Pixels to check above line
VERTICAL_WHITESPACE_MIN = 0.75  # 75% whitespace required above


def detect_horizontal_lines(binary_image, search_start_ratio, search_end_ratio,
                            min_length_ratio, max_length_ratio):
    """
    Detect horizontal lines in specified region using Hough transform.
    Returns list of lines sorted from BOTTOM to TOP.
    """
    height, width = binary_image.shape

    # Define search region
    y_start = int(height * search_start_ratio)
    y_end = int(height * search_end_ratio)
    search_region = binary_image[y_start:y_end, :]

    # Invert for Hough (needs white lines on black background)
    inverted = cv2.bitwise_not(search_region)

    # Detect lines
    lines = cv2.HoughLinesP(
        inverted,
        rho=1,
        theta=np.pi/180,
        threshold=50,
        minLineLength=int(width * min_length_ratio),
        maxLineGap=15
    )

    if lines is None:
        return []

    # Filter horizontal lines and adjust Y coordinates
    horizontal_lines = []
    for line in lines:
        x1, y1, x2, y2 = line[0]

        # Check if line is horizontal (small Y variation)
        if abs(y2 - y1) <= 3:
            # Adjust Y coordinate to full page coordinate system
            adjusted_y = y_start + y1
            line_length = abs(x2 - x1)

            # Check length constraints
            if width * min_length_ratio <= line_length <= width * max_length_ratio:
                horizontal_lines.append({
                    'x1': min(x1, x2),
                    'x2': max(x1, x2),
                    'y': adjusted_y,
                    'length': line_length,
                    'length_ratio': line_length / width
                })

    # Sort from BOTTOM to TOP (highest Y first for bottom-up search)
    horizontal_lines.sort(key=lambda l: l['y'], reverse=True)

    return horizontal_lines


def check_horizontal_isolation(binary_image, line_info):
    """
    Check if the line is isolated horizontally by sampling pixels
    EXACTLY at the line's Y-coordinate to the left and right.

    Real footer lines: whitespace (255) to left/right
    Word underlines: text (0) to left/right

    Returns: (is_isolated, left_blackness, right_blackness)
    """
    height, width = binary_image.shape
    y = line_info['y']
    x1 = line_info['x1']
    x2 = line_info['x2']

    # Define sampling regions EXACTLY at line's Y-coordinate
    # Left region: sample to the left of line start
    left_x_start = max(0, x1 - SAMPLE_DISTANCE - SAMPLE_WIDTH)
    left_x_end = max(0, x1 - SAMPLE_DISTANCE)

    # Right region: sample to the right of line end
    right_x_start = min(width, x2 + SAMPLE_DISTANCE)
    right_x_end = min(width, x2 + SAMPLE_DISTANCE + SAMPLE_WIDTH)

    # Sample SINGLE ROW at exact Y position
    if y >= height:
        y = height - 1

    left_sample = binary_image[y, left_x_start:left_x_end]
    right_sample = binary_image[y, right_x_start:right_x_end]

    # Calculate blackness (text presence indicator)
    left_blackness = 0.0
    right_blackness = 0.0

    if left_sample.size > 0:
        left_blackness = np.sum(left_sample == 0) / left_sample.size

    if right_sample.size > 0:
        right_blackness = np.sum(right_sample == 0) / right_sample.size

    # Line is isolated if BOTH sides have low blackness (mostly white)
    is_isolated = (left_blackness < TEXT_BLACKNESS_THRESHOLD and
                   right_blackness < TEXT_BLACKNESS_THRESHOLD)

    return is_isolated, left_blackness, right_blackness


def check_vertical_isolation(binary_image, line_info):
    """
    Check if there is sufficient whitespace above the line.
    Returns (is_isolated, whitespace_ratio)
    """
    height, width = binary_image.shape
    y = line_info['y']
    x1 = line_info['x1']
    x2 = line_info['x2']

    # Define region above the line
    y_start = max(0, y - VERTICAL_CHECK_HEIGHT)
    y_end = y
    x_min = max(0, x1 - 20)
    x_max = min(width, x2 + 20)

    # Extract region
    region_above = binary_image[y_start:y_end, x_min:x_max]

    if region_above.size == 0:
        return False, 0.0

    # Calculate whitespace ratio
    whitespace_ratio = np.sum(region_above == 255) / region_above.size

    is_isolated = whitespace_ratio >= VERTICAL_WHITESPACE_MIN

    return is_isolated, whitespace_ratio


def detect_footer_line(binary_image, debug=False):
    """
    Detect footer separator line using horizontal isolation at exact Y-coordinate.

    Returns:
        footer_y: Y-coordinate of footer line (or fallback position)
        detection_info: Dictionary with detection details
    """
    height, width = binary_image.shape

    detection_info = {
        'method': 'fallback',
        'confidence': 'low',
        'footer_y': int(height * FALLBACK_POSITION),
        'details': {}
    }

    # Step 1: Detect all horizontal lines in footer region
    lines = detect_horizontal_lines(
        binary_image,
        FOOTER_SEARCH_START,
        FOOTER_SEARCH_END,
        LINE_MIN_LENGTH,
        LINE_MAX_LENGTH
    )

    if not lines:
        if debug:
            print(f"  [FALLBACK] No lines detected in footer region. Using {FALLBACK_POSITION:.1%}")
        return detection_info['footer_y'], detection_info

    if debug:
        print(f"  [INFO] Detected {len(lines)} candidate lines, searching bottom-up...")

    # Step 2: Search from BOTTOM upward for isolated line
    for idx, line in enumerate(lines):
        if debug:
            print(f"\n  [CANDIDATE {idx+1}] Y={line['y']} ({line['y']/height:.1%}), "
                  f"Length={line['length']}px ({line['length_ratio']:.1%})")

        # Check horizontal isolation at EXACT Y-coordinate
        is_h_isolated, left_black, right_black = check_horizontal_isolation(binary_image, line)

        if debug:
            print(f"    Horizontal isolation: {is_h_isolated}")
            print(f"      Left blackness: {left_black:.3f} ({'TEXT' if left_black >= TEXT_BLACKNESS_THRESHOLD else 'CLEAR'})")
            print(f"      Right blackness: {right_black:.3f} ({'TEXT' if right_black >= TEXT_BLACKNESS_THRESHOLD else 'CLEAR'})")

        # Check vertical isolation
        is_v_isolated, whitespace = check_vertical_isolation(binary_image, line)

        if debug:
            print(f"    Vertical isolation: {is_v_isolated} (whitespace={whitespace:.1%})")

        # Decision criteria: ISOLATED footer line
        # - NO text to left or right at SAME Y-coordinate (horizontally isolated)
        # - Whitespace above (vertically isolated)
        if is_h_isolated and is_v_isolated:
            if debug:
                print(f"  [SELECTED] Footer line at Y={line['y']} ({line['y']/height:.1%})")

            detection_info = {
                'method': 'isolated_line',
                'confidence': 'high',
                'footer_y': int(line['y']),
                'details': {
                    'line_position_ratio': float(line['y'] / height),
                    'line_length_ratio': float(line['length_ratio']),
                    'left_blackness': float(left_black),
                    'right_blackness': float(right_black),
                    'vertical_whitespace': float(whitespace)
                }
            }
            return int(line['y']), detection_info

        elif debug:
            reasons = []
            if not is_h_isolated:
                reasons.append("not_horizontally_isolated")
                if left_black >= TEXT_BLACKNESS_THRESHOLD:
                    reasons.append("(text_on_left)")
                if right_black >= TEXT_BLACKNESS_THRESHOLD:
                    reasons.append("(text_on_right)")
            if not is_v_isolated:
                reasons.append("not_vertically_isolated")
            print(f"    [REJECT] {' '.join(reasons)}")

    # Step 3: Fallback if no isolated line found
    if debug:
        print(f"\n  [FALLBACK] No isolated line found. Using median position {FALLBACK_POSITION:.1%}")

    return detection_info['footer_y'], detection_info


def visualize_footer_detection(pdf_path, page_num, output_dir):
    """
    Visualize footer detection for a single page with debug annotations.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Convert PDF page to image
    images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=300)
    page_image = np.array(images[0])

    # Convert to grayscale and binarize
    gray = cv2.cvtColor(page_image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Detect footer
    print(f"\nProcessing {pdf_path.name} - Page {page_num}")
    footer_y, info = detect_footer_line(binary, debug=True)

    # Create visualization
    vis_image = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    height, width = binary.shape

    # Draw search region boundaries
    search_start_y = int(height * FOOTER_SEARCH_START)
    search_end_y = int(height * FOOTER_SEARCH_END)
    cv2.line(vis_image, (0, search_start_y), (width, search_start_y), (255, 0, 255), 2)  # Magenta
    cv2.line(vis_image, (0, search_end_y), (width, search_end_y), (255, 0, 255), 2)

    # Draw detected footer line
    if info['method'] == 'isolated_line':
        cv2.line(vis_image, (0, footer_y), (width, footer_y), (0, 255, 0), 3)  # Green
        label = f"DETECTED: {info['details']['line_position_ratio']:.1%}"
    else:
        cv2.line(vis_image, (0, footer_y), (width, footer_y), (0, 0, 255), 3)  # Red
        label = f"FALLBACK: {FALLBACK_POSITION:.1%}"

    # Add label
    cv2.putText(vis_image, label, (10, footer_y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0) if info['method'] == 'isolated_line' else (0, 0, 255), 2)

    # Save
    filename = f"{pdf_path.stem}_page{page_num}_smart_footer.png"
    output_path = output_dir / filename
    cv2.imwrite(str(output_path), vis_image)
    print(f"[+] Saved visualization: {filename}")

    return info


def test_all_pdfs():
    """
    Test footer detection on all 13 scanned PDFs.
    """
    scanned_dir = Path("data/raw/scanned")
    output_dir = Path("footer_detector_smart_test")

    pdf_files = sorted(scanned_dir.glob("*.pdf"))

    results = []

    for pdf_path in pdf_files:
        print(f"\n{'='*80}")
        print(f"Testing: {pdf_path.name}")
        print('='*80)

        # Get page count
        images = convert_from_path(pdf_path, dpi=72)  # Low DPI just for counting
        num_pages = len(images)

        for page_num in range(1, num_pages + 1):
            info = visualize_footer_detection(pdf_path, page_num, output_dir)

            results.append({
                'pdf_filename': pdf_path.name,
                'page_number': page_num,
                'detection_method': info['method'],
                'confidence': info['confidence'],
                'footer_y': info['footer_y'],
                'details': info['details']
            })

    # Save results (already using Python native types)
    results_path = output_dir / "detection_results.json"
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    # Print summary
    print(f"\n{'='*80}")
    print("DETECTION SUMMARY")
    print('='*80)

    total_pages = len(results)
    detected = sum(1 for r in results if r['detection_method'] == 'isolated_line')
    fallback = total_pages - detected

    print(f"Total pages: {total_pages}")
    print(f"Detected (isolated line): {detected} ({detected/total_pages*100:.1f}%)")
    print(f"Fallback: {fallback} ({fallback/total_pages*100:.1f}%)")

    print(f"\n[+] Results saved to: {results_path}")


if __name__ == "__main__":
    test_all_pdfs()
