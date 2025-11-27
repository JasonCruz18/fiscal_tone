"""
Final Footer Detector - Whitespace-Based Isolation Strategy

Key insights from analysis:
1. Footer separator = multiple SHORT line segments (2-10% width) at 92-94%
2. These segments sit in a MOSTLY WHITE region (gap between content and footer text)
3. Footer text is ABOVE the separator lines
4. Segments are horizontally isolated (whitespace to left/right within same Y-row)

New strategy:
- Detect shorter lines (2-10% width) in 88-95% region
- Check if line sits in a WHITE ZONE (low text density in surrounding area)
- Select the BOTTOM-MOST line in a white zone
- Fallback: use median 92% position
"""

import cv2
import numpy as np
from pdf2image import convert_from_path
from pathlib import Path
import json

# Tesseract configuration
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'

# Footer detection parameters - ADJUSTED for short separator lines
FOOTER_SEARCH_START = 0.88    # Start higher (88% instead of 75%)
FOOTER_SEARCH_END = 0.95      # End at 95%
LINE_MIN_LENGTH = 0.02        # Minimum 2% of page width (for short segments)
LINE_MAX_LENGTH = 0.15        # Maximum 15% of page width
FALLBACK_POSITION = 0.92      # Based on analysis, most separators at ~92%

# Whitespace zone detection
ZONE_CHECK_RADIUS = 80        # Pixels to check around line (larger area)
WHITE_ZONE_THRESHOLD = 0.85   # 85% whitespace indicates isolated line

# Vertical isolation (whitespace above)
VERTICAL_CHECK_HEIGHT = 60    # Check larger area above
VERTICAL_WHITESPACE_MIN = 0.80  # 80% whitespace above


def detect_horizontal_lines(binary_image, search_start_ratio, search_end_ratio,
                            min_length_ratio, max_length_ratio):
    """Detect horizontal lines including SHORT segments"""
    height, width = binary_image.shape

    y_start = int(height * search_start_ratio)
    y_end = int(height * search_end_ratio)
    search_region = binary_image[y_start:y_end, :]

    inverted = cv2.bitwise_not(search_region)

    # Adjusted parameters for detecting shorter lines
    lines = cv2.HoughLinesP(
        inverted,
        rho=1,
        theta=np.pi/180,
        threshold=30,  # Lower threshold
        minLineLength=int(width * min_length_ratio),
        maxLineGap=10  # Smaller gap
    )

    if lines is None:
        return []

    horizontal_lines = []
    for line in lines:
        x1, y1, x2, y2 = line[0]

        if abs(y2 - y1) <= 3:  # Horizontal
            adjusted_y = y_start + y1
            line_length = abs(x2 - x1)

            if width * min_length_ratio <= line_length <= width * max_length_ratio:
                horizontal_lines.append({
                    'x1': min(x1, x2),
                    'x2': max(x1, x2),
                    'y': adjusted_y,
                    'length': line_length,
                    'length_ratio': line_length / width
                })

    # Sort from BOTTOM to TOP
    horizontal_lines.sort(key=lambda l: l['y'], reverse=True)

    return horizontal_lines


def is_in_white_zone(binary_image, line_info):
    """
    Check if line is surrounded by whitespace (isolated in a white zone).

    Returns: (is_in_white_zone, whitespace_ratio)
    """
    height, width = binary_image.shape
    y = line_info['y']
    x1 = line_info['x1']
    x2 = line_info['x2']

    # Define zone around the line
    y_min = max(0, y - ZONE_CHECK_RADIUS)
    y_max = min(height, y + ZONE_CHECK_RADIUS)
    x_min = max(0, (x1 + x2) // 2 - ZONE_CHECK_RADIUS)  # Center of line
    x_max = min(width, (x1 + x2) // 2 + ZONE_CHECK_RADIUS)

    # Extract zone
    zone = binary_image[y_min:y_max, x_min:x_max]

    if zone.size == 0:
        return False, 0.0

    # Calculate whitespace ratio
    whitespace_ratio = np.sum(zone == 255) / zone.size

    is_white_zone = whitespace_ratio >= WHITE_ZONE_THRESHOLD

    return is_white_zone, whitespace_ratio


def check_vertical_whitespace(binary_image, line_info):
    """Check for whitespace ABOVE the line"""
    height, width = binary_image.shape
    y = line_info['y']
    x1 = line_info['x1']
    x2 = line_info['x2']

    # Region above line
    y_start = max(0, y - VERTICAL_CHECK_HEIGHT)
    y_end = y
    x_min = max(0, x1 - 20)
    x_max = min(width, x2 + 20)

    region_above = binary_image[y_start:y_end, x_min:x_max]

    if region_above.size == 0:
        return False, 0.0

    whitespace_ratio = np.sum(region_above == 255) / region_above.size
    is_clear_above = whitespace_ratio >= VERTICAL_WHITESPACE_MIN

    return is_clear_above, whitespace_ratio


def detect_footer_line(binary_image, debug=False):
    """
    Detect footer separator line using whitespace zone strategy.

    Returns: (footer_y, detection_info)
    """
    height, width = binary_image.shape

    detection_info = {
        'method': 'fallback',
        'confidence': 'low',
        'footer_y': int(height * FALLBACK_POSITION),
        'details': {}
    }

    # Detect lines (including short segments)
    lines = detect_horizontal_lines(
        binary_image,
        FOOTER_SEARCH_START,
        FOOTER_SEARCH_END,
        LINE_MIN_LENGTH,
        LINE_MAX_LENGTH
    )

    if not lines:
        if debug:
            print(f"  [FALLBACK] No lines detected. Using {FALLBACK_POSITION:.1%}")
        return detection_info['footer_y'], detection_info

    if debug:
        print(f"  [INFO] Detected {len(lines)} candidate lines, searching bottom-up...")

    # Search from BOTTOM upward for line in white zone
    for idx, line in enumerate(lines):
        if debug:
            print(f"\n  [CANDIDATE {idx+1}] Y={line['y']} ({line['y']/height:.1%}), "
                  f"Length={line['length']}px ({line['length_ratio']:.1%})")

        # Check if in white zone
        in_white_zone, zone_whitespace = is_in_white_zone(binary_image, line)

        if debug:
            print(f"    White zone: {in_white_zone} (whitespace={zone_whitespace:.1%})")

        # Check whitespace above
        clear_above, above_whitespace = check_vertical_whitespace(binary_image, line)

        if debug:
            print(f"    Clear above: {clear_above} (whitespace={above_whitespace:.1%})")

        # Decision: line in white zone AND clear above
        if in_white_zone and clear_above:
            if debug:
                print(f"  [SELECTED] Footer line at Y={line['y']} ({line['y']/height:.1%})")

            detection_info = {
                'method': 'white_zone',
                'confidence': 'high',
                'footer_y': int(line['y']),
                'details': {
                    'line_position_ratio': float(line['y'] / height),
                    'line_length_ratio': float(line['length_ratio']),
                    'zone_whitespace': float(zone_whitespace),
                    'above_whitespace': float(above_whitespace)
                }
            }
            return int(line['y']), detection_info

        elif debug:
            reasons = []
            if not in_white_zone:
                reasons.append(f"not_in_white_zone({zone_whitespace:.1%})")
            if not clear_above:
                reasons.append(f"not_clear_above({above_whitespace:.1%})")
            print(f"    [REJECT] {' '.join(reasons)}")

    # Fallback
    if debug:
        print(f"\n  [FALLBACK] No isolated line found. Using {FALLBACK_POSITION:.1%}")

    return detection_info['footer_y'], detection_info


def visualize_footer_detection(pdf_path, page_num, output_dir):
    """Visualize footer detection with annotations"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Convert PDF to image
    images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=300)
    page_image = np.array(images[0])

    # Binarize
    gray = cv2.cvtColor(page_image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Detect footer
    print(f"\nProcessing {pdf_path.name} - Page {page_num}")
    footer_y, info = detect_footer_line(binary, debug=True)

    # Create visualization
    vis_image = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    height, width = binary.shape

    # Draw search region
    search_start_y = int(height * FOOTER_SEARCH_START)
    search_end_y = int(height * FOOTER_SEARCH_END)
    cv2.line(vis_image, (0, search_start_y), (width, search_start_y), (255, 0, 255), 2)
    cv2.line(vis_image, (0, search_end_y), (width, search_end_y), (255, 0, 255), 2)

    # Draw detected footer line
    if info['method'] == 'white_zone':
        cv2.line(vis_image, (0, footer_y), (width, footer_y), (0, 255, 0), 3)  # Green
        label = f"DETECTED: {info['details']['line_position_ratio']:.1%}"
    else:
        cv2.line(vis_image, (0, footer_y), (width, footer_y), (0, 0, 255), 3)  # Red
        label = f"FALLBACK: {FALLBACK_POSITION:.1%}"

    cv2.putText(vis_image, label, (10, footer_y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                (0, 255, 0) if info['method'] == 'white_zone' else (0, 0, 255), 2)

    # Save
    filename = f"{pdf_path.stem}_page{page_num}_final_footer.png"
    output_path = output_dir / filename
    cv2.imwrite(str(output_path), vis_image)
    print(f"[+] Saved: {filename}\n")

    return info


def test_all_pdfs():
    """Test on all 13 scanned PDFs"""
    scanned_dir = Path("data/raw/scanned")
    output_dir = Path("footer_detector_final_test")

    pdf_files = sorted(scanned_dir.glob("*.pdf"))
    results = []

    for pdf_path in pdf_files:
        print(f"\n{'='*80}")
        print(f"Testing: {pdf_path.name}")
        print('='*80)

        images = convert_from_path(pdf_path, dpi=72)
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

    # Save results
    results_path = output_dir / "detection_results.json"
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    # Summary
    print(f"\n{'='*80}")
    print("DETECTION SUMMARY")
    print('='*80)

    total = len(results)
    detected = sum(1 for r in results if r['detection_method'] == 'white_zone')
    fallback = total - detected

    print(f"Total pages: {total}")
    print(f"Detected (white zone): {detected} ({detected/total*100:.1f}%)")
    print(f"Fallback: {fallback} ({fallback/total*100:.1f}%)")

    print(f"\n[+] Results saved to: {results_path}")


if __name__ == "__main__":
    test_all_pdfs()
