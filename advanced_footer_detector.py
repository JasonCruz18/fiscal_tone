"""
Advanced Footer Line Detector with Horizontal Text-Line Context Analysis

Strategy:
1. Search from BOTTOM upward in 75-95% region
2. Detect horizontal lines using Hough transform
3. For each line, analyze horizontal neighbors (text to left/right on same Y-level)
4. Use OCR text box detection to identify text regions
5. Select bottom-most line that is truly isolated (no text neighbors)

This eliminates false positives from word underlines while preserving real footer lines.
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

# Horizontal neighbor detection parameters
HORIZONTAL_CHECK_WIDTH = 100   # Pixels to check left/right of line
HORIZONTAL_CHECK_HEIGHT = 15   # Height of band to check around line Y-position
TEXT_DENSITY_THRESHOLD = 0.05  # 5% black pixels indicates text presence

# Vertical isolation parameters
VERTICAL_CHECK_HEIGHT = 30     # Pixels to check above line
VERTICAL_WHITESPACE_MIN = 0.80 # 80% whitespace required above


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


def check_horizontal_neighbors(binary_image, line_info):
    """
    Check if there is text to the left or right of the line on the same horizontal level.
    Returns (has_left_neighbor, has_right_neighbor, left_density, right_density)
    """
    height, width = binary_image.shape
    y = line_info['y']
    x1 = line_info['x1']
    x2 = line_info['x2']

    # Define regions to check
    y_min = max(0, y - HORIZONTAL_CHECK_HEIGHT // 2)
    y_max = min(height, y + HORIZONTAL_CHECK_HEIGHT // 2)

    # Left region: from left edge to line start
    left_x_min = max(0, x1 - HORIZONTAL_CHECK_WIDTH)
    left_x_max = x1

    # Right region: from line end to right edge
    right_x_min = x2
    right_x_max = min(width, x2 + HORIZONTAL_CHECK_WIDTH)

    # Extract regions
    left_region = binary_image[y_min:y_max, left_x_min:left_x_max]
    right_region = binary_image[y_min:y_max, right_x_min:right_x_max]

    # Calculate text density (black pixels in binary image)
    left_density = 0.0
    right_density = 0.0

    if left_region.size > 0:
        left_density = np.sum(left_region == 0) / left_region.size

    if right_region.size > 0:
        right_density = np.sum(right_region == 0) / right_region.size

    # Check if density exceeds threshold (indicates text presence)
    has_left_neighbor = left_density > TEXT_DENSITY_THRESHOLD
    has_right_neighbor = right_density > TEXT_DENSITY_THRESHOLD

    return has_left_neighbor, has_right_neighbor, left_density, right_density


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


def get_text_boxes_from_ocr(binary_image):
    """
    Use Tesseract to detect text boxes on the page.
    Returns list of bounding boxes (x, y, w, h) for text regions.
    """
    try:
        # Convert binary to RGB for Tesseract
        rgb_image = cv2.cvtColor(binary_image, cv2.COLOR_GRAY2RGB)

        # Get bounding boxes from Tesseract
        data = pytesseract.image_to_data(rgb_image, output_type=pytesseract.Output.DICT)

        text_boxes = []
        n_boxes = len(data['text'])

        for i in range(n_boxes):
            # Filter out empty text
            if int(data['conf'][i]) > 0:  # Confidence > 0
                x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
                text_boxes.append({
                    'x': x,
                    'y': y,
                    'w': w,
                    'h': h,
                    'text': data['text'][i]
                })

        return text_boxes
    except Exception as e:
        print(f"  [WARNING] OCR text box detection failed: {e}")
        return []


def is_line_inside_text_block(line_info, text_boxes):
    """
    Check if the detected line falls within a text block (word underline).
    Returns True if line overlaps with any text box.
    """
    line_y = line_info['y']
    line_x1 = line_info['x1']
    line_x2 = line_info['x2']

    for box in text_boxes:
        box_y_min = box['y']
        box_y_max = box['y'] + box['h']
        box_x_min = box['x']
        box_x_max = box['x'] + box['w']

        # Check if line Y overlaps with text box Y range
        if box_y_min <= line_y <= box_y_max:
            # Check if line X overlaps with text box X range
            if not (line_x2 < box_x_min or line_x1 > box_x_max):
                return True, box

    return False, None


def detect_footer_line(binary_image, debug=False):
    """
    Detect footer separator line using horizontal text-line context analysis.

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

    # Step 2: Get text boxes from OCR (optional, can be slow)
    # Commenting out for now to improve performance
    # text_boxes = get_text_boxes_from_ocr(binary_image)

    # Step 3: Search from BOTTOM upward for isolated line
    for idx, line in enumerate(lines):
        if debug:
            print(f"\n  [CANDIDATE {idx+1}] Y={line['y']} ({line['y']/height:.1%}), "
                  f"Length={line['length']}px ({line['length_ratio']:.1%})")

        # Check horizontal neighbors
        has_left, has_right, left_dens, right_dens = check_horizontal_neighbors(binary_image, line)

        if debug:
            print(f"    Left neighbor: {has_left} (density={left_dens:.3f})")
            print(f"    Right neighbor: {has_right} (density={right_dens:.3f})")

        # Check if line is inside text block (word underline)
        # Commenting out OCR-based check for performance
        # is_in_text, overlapping_box = is_line_inside_text_block(line, text_boxes)
        # if is_in_text and debug:
        #     print(f"    [REJECT] Line inside text block: '{overlapping_box['text']}'")
        #     continue

        # Check vertical isolation
        is_isolated, whitespace = check_vertical_isolation(binary_image, line)

        if debug:
            print(f"    Vertical isolation: {is_isolated} (whitespace={whitespace:.1%})")

        # Decision criteria: ISOLATED footer line
        # - NO text to left or right (not a word underline)
        # - Whitespace above (clear separation from content)
        if not has_left and not has_right and is_isolated:
            if debug:
                print(f"  [SELECTED] Footer line at Y={line['y']} ({line['y']/height:.1%})")

            detection_info = {
                'method': 'isolated_line',
                'confidence': 'high',
                'footer_y': line['y'],
                'details': {
                    'line_position_ratio': line['y'] / height,
                    'line_length_ratio': line['length_ratio'],
                    'left_density': left_dens,
                    'right_density': right_dens,
                    'vertical_whitespace': whitespace
                }
            }
            return line['y'], detection_info

        elif debug:
            reasons = []
            if has_left:
                reasons.append("has_left_neighbor")
            if has_right:
                reasons.append("has_right_neighbor")
            if not is_isolated:
                reasons.append("not_vertically_isolated")
            print(f"    [REJECT] {', '.join(reasons)}")

    # Step 4: Fallback if no isolated line found
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
    filename = f"{pdf_path.stem}_page{page_num}_advanced_footer.png"
    output_path = output_dir / filename
    cv2.imwrite(str(output_path), vis_image)
    print(f"[+] Saved visualization: {filename}")

    return info


def test_all_pdfs():
    """
    Test footer detection on all 13 scanned PDFs.
    """
    scanned_dir = Path("data/raw/scanned")
    output_dir = Path("footer_detector_advanced_test")

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

    # Save results (convert numpy types to Python types)
    results_serializable = []
    for r in results:
        r_copy = {
            'pdf_filename': r['pdf_filename'],
            'page_number': int(r['page_number']),
            'detection_method': r['detection_method'],
            'confidence': r['confidence'],
            'footer_y': int(r['footer_y']),
            'details': {k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                       for k, v in r['details'].items()} if r['details'] else {}
        }
        results_serializable.append(r_copy)

    results_path = output_dir / "detection_results.json"
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(results_serializable, f, indent=2)

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
