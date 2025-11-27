"""
Whitespace-Zone-Based Footer Detector

Strategy: Find the LARGEST whitespace zone in the bottom half of the page.
The footer separator line is at the BOTTOM boundary of this zone.
Explicitly discard address lines in the 93-100% region.

Based on comprehensive analysis of INFORME_N_002-2017-CF.pdf showing:
- All pages have a large whitespace gap (100-400px) before footer content
- Footer separator is at the bottom of this gap (75-93% depending on content)
- Address line "Av. República de Panamá..." is always at 93-95%
"""

import cv2
import numpy as np
from pdf2image import convert_from_path
from pathlib import Path
import json

# Configuration
PAGE_MID = 0.50                      # Start analysis from page middle
WHITESPACE_THRESHOLD = 0.05          # <5% blackness = whitespace
MIN_ZONE_HEIGHT = 20                 # Minimum zone height (pixels)
ADDRESS_REGION_START = 0.93          # Discard lines above 93%
FOOTER_SEARCH_MARGIN = 30            # Search ±30px around boundary
LINE_MIN_LENGTH = 0.02               # Min 2% page width
LINE_MAX_LENGTH = 0.20               # Max 20% page width
FALLBACK_POSITION = 0.90             # Fallback to 90% if no zones found


def calculate_row_blackness(binary_image, start_y, end_y):
    """Calculate blackness for each row in range"""
    width = binary_image.shape[1]
    row_blackness = []

    for y in range(start_y, end_y):
        row = binary_image[y, :]
        blackness = np.sum(row == 0) / width
        row_blackness.append({'y': y, 'blackness': blackness})

    return row_blackness


def find_whitespace_zones(row_blackness, min_height=MIN_ZONE_HEIGHT):
    """Identify continuous whitespace zones"""
    zones = []
    in_zone = False
    zone_start = 0

    for item in row_blackness:
        y = item['y']
        blackness = item['blackness']

        if blackness < WHITESPACE_THRESHOLD and not in_zone:
            # Start new zone
            zone_start = y
            in_zone = True
        elif blackness >= WHITESPACE_THRESHOLD and in_zone:
            # End zone
            if y - zone_start >= min_height:
                zones.append({
                    'start': zone_start,
                    'end': y,
                    'height': y - zone_start
                })
            in_zone = False

    # Handle zone extending to end
    if in_zone and row_blackness:
        y_last = row_blackness[-1]['y']
        if y_last - zone_start >= min_height:
            zones.append({
                'start': zone_start,
                'end': y_last,
                'height': y_last - zone_start
            })

    return zones


def detect_horizontal_lines_in_region(binary_image, y_start, y_end, min_length_ratio, max_length_ratio):
    """Detect horizontal lines in specific Y region"""
    height, width = binary_image.shape

    # Extract region
    region = binary_image[y_start:y_end, :]
    inverted = cv2.bitwise_not(region)

    # Hough transform
    lines = cv2.HoughLinesP(
        inverted,
        rho=1,
        theta=np.pi/180,
        threshold=30,
        minLineLength=int(width * min_length_ratio),
        maxLineGap=10
    )

    if lines is None:
        return []

    horizontal_lines = []
    for line in lines:
        x1, y1, x2, y2 = line[0]

        if abs(y2 - y1) <= 3:  # Horizontal
            adjusted_y = y_start + y1  # Adjust to full page coordinates
            line_length = abs(x2 - x1)

            if width * min_length_ratio <= line_length <= width * max_length_ratio:
                horizontal_lines.append({
                    'x1': min(x1, x2),
                    'x2': max(x1, x2),
                    'y': adjusted_y,
                    'length': line_length,
                    'length_pct': line_length / width
                })

    return horizontal_lines


def detect_footer_line(binary_image, debug=False):
    """
    Detect footer separator using whitespace zone analysis.

    Returns: (footer_y, detection_info)
    """
    height, width = binary_image.shape

    detection_info = {
        'method': 'fallback',
        'confidence': 'low',
        'footer_y': int(height * FALLBACK_POSITION),
        'details': {}
    }

    # Step 1: Analyze from page mid to bottom
    mid_y = int(height * PAGE_MID)

    if debug:
        print(f"  [INFO] Page: {width}x{height}, analyzing from Y={mid_y} (50%) to bottom")

    row_blackness = calculate_row_blackness(binary_image, mid_y, height)

    # Step 2: Find whitespace zones
    zones = find_whitespace_zones(row_blackness, MIN_ZONE_HEIGHT)

    if debug:
        print(f"  [INFO] Found {len(zones)} whitespace zones")
        for i, zone in enumerate(zones, 1):
            print(f"    Zone {i}: Y={zone['start']}-{zone['end']} "
                  f"({zone['start']/height:.1%}-{zone['end']/height:.1%}), "
                  f"Height={zone['height']}px")

    if not zones:
        if debug:
            print(f"  [FALLBACK] No whitespace zones found. Using {FALLBACK_POSITION:.1%}")
        return detection_info['footer_y'], detection_info

    # Step 3: Find LARGEST zone
    largest_zone = max(zones, key=lambda z: z['height'])

    if debug:
        print(f"\n  [LARGEST ZONE] Y={largest_zone['start']}-{largest_zone['end']} "
              f"({largest_zone['start']/height:.1%}-{largest_zone['end']/height:.1%}), "
              f"Height={largest_zone['height']}px")

    # Step 4: Footer separator at BOTTOM of largest zone
    footer_candidate_y = largest_zone['end']

    if debug:
        print(f"  [CANDIDATE] Footer boundary at Y={footer_candidate_y} "
              f"({footer_candidate_y/height:.1%})")

    # Step 5: Search for horizontal lines near boundary
    search_start = max(mid_y, footer_candidate_y - FOOTER_SEARCH_MARGIN)
    search_end = min(height, footer_candidate_y + FOOTER_SEARCH_MARGIN)

    if debug:
        print(f"  [SEARCH] Looking for lines in Y={search_start}-{search_end} "
              f"({search_start/height:.1%}-{search_end/height:.1%})")

    lines = detect_horizontal_lines_in_region(
        binary_image, search_start, search_end,
        LINE_MIN_LENGTH, LINE_MAX_LENGTH
    )

    if debug:
        print(f"  [LINES] Detected {len(lines)} horizontal lines")

    # Step 6: Filter out address region (above 93%)
    address_threshold = int(height * ADDRESS_REGION_START)
    valid_lines = [l for l in lines if l['y'] < address_threshold]

    if debug:
        if len(valid_lines) < len(lines):
            print(f"  [FILTER] Removed {len(lines) - len(valid_lines)} lines in address region (>{ADDRESS_REGION_START:.0%})")
        print(f"  [VALID] {len(valid_lines)} lines remain after filtering")

    # Step 7: Select best line
    if valid_lines:
        # Choose line closest to whitespace boundary
        footer_line = min(valid_lines, key=lambda l: abs(l['y'] - footer_candidate_y))

        if debug:
            print(f"  [SELECTED] Line at Y={footer_line['y']} ({footer_line['y']/height:.1%}), "
                  f"Length={footer_line['length_pct']:.1%}")

        detection_info = {
            'method': 'line_detected',
            'confidence': 'high',
            'footer_y': int(footer_line['y']),
            'details': {
                'largest_zone_start': int(largest_zone['start']),
                'largest_zone_end': int(largest_zone['end']),
                'largest_zone_height': int(largest_zone['height']),
                'line_position': int(footer_line['y']),
                'line_length_pct': float(footer_line['length_pct']),
                'distance_from_boundary': int(abs(footer_line['y'] - footer_candidate_y))
            }
        }
        return int(footer_line['y']), detection_info

    else:
        # Use whitespace boundary directly
        if debug:
            print(f"  [BOUNDARY] No lines found, using whitespace boundary at Y={footer_candidate_y} "
                  f"({footer_candidate_y/height:.1%})")

        detection_info = {
            'method': 'whitespace_boundary',
            'confidence': 'medium',
            'footer_y': int(footer_candidate_y),
            'details': {
                'largest_zone_start': int(largest_zone['start']),
                'largest_zone_end': int(largest_zone['end']),
                'largest_zone_height': int(largest_zone['height'])
            }
        }
        return int(footer_candidate_y), detection_info


def visualize_detection(pdf_path, page_num, output_dir):
    """Create visualization of footer detection"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Convert PDF to image
    images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=300)
    page_image = np.array(images[0])

    # Binarize
    gray = cv2.cvtColor(page_image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Detect
    print(f"\nProcessing {pdf_path.name} - Page {page_num}")
    footer_y, info = detect_footer_line(binary, debug=True)

    # Create visualization
    vis_image = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    height, width = binary.shape

    # Draw page mid
    mid_y = int(height * PAGE_MID)
    cv2.line(vis_image, (0, mid_y), (width, mid_y), (255, 0, 255), 2)  # Magenta
    cv2.putText(vis_image, f'PAGE MID ({PAGE_MID:.0%})', (10, mid_y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 255), 2)

    # Draw address region threshold
    addr_y = int(height * ADDRESS_REGION_START)
    cv2.line(vis_image, (0, addr_y), (width, addr_y), (0, 0, 255), 2)  # Red
    cv2.putText(vis_image, f'ADDRESS REGION ({ADDRESS_REGION_START:.0%})', (width - 600, addr_y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)

    # Draw largest whitespace zone if available
    if 'largest_zone_start' in info['details']:
        zone_start = info['details']['largest_zone_start']
        zone_end = info['details']['largest_zone_end']
        # Draw semi-transparent cyan rectangle
        overlay = vis_image.copy()
        cv2.rectangle(overlay, (0, zone_start), (width, zone_end), (255, 255, 0), -1)
        cv2.addWeighted(overlay, 0.2, vis_image, 0.8, 0, vis_image)
        # Draw borders
        cv2.line(vis_image, (0, zone_start), (width, zone_start), (255, 255, 0), 2)
        cv2.line(vis_image, (0, zone_end), (width, zone_end), (255, 255, 0), 2)
        cv2.putText(vis_image, f'LARGEST WHITESPACE ZONE ({zone_start/height:.1%}-{zone_end/height:.1%})',
                    (10, zone_start + 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2)

    # Draw detected footer line
    color = (0, 255, 0) if info['method'] != 'fallback' else (0, 0, 255)  # Green or Red
    cv2.line(vis_image, (0, footer_y), (width, footer_y), color, 4)
    label = f"{info['method'].upper()}: {footer_y/height:.1%}"
    cv2.putText(vis_image, label, (10, footer_y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

    # Save
    filename = f"{pdf_path.stem}_page{page_num}_whitespace_zone.png"
    output_path = output_dir / filename
    cv2.imwrite(str(output_path), vis_image)
    print(f"[+] Saved: {filename}\n")

    return info


def test_all_pdfs():
    """Test on all 13 scanned PDFs"""
    scanned_dir = Path("data/raw/scanned")
    output_dir = Path("whitespace_zone_test")

    pdf_files = sorted(scanned_dir.glob("*.pdf"))
    results = []

    for pdf_path in pdf_files:
        print(f"\n{'='*80}")
        print(f"Testing: {pdf_path.name}")
        print('='*80)

        images = convert_from_path(pdf_path, dpi=72)
        num_pages = len(images)

        for page_num in range(1, num_pages + 1):
            info = visualize_detection(pdf_path, page_num, output_dir)

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
    line_detected = sum(1 for r in results if r['detection_method'] == 'line_detected')
    boundary = sum(1 for r in results if r['detection_method'] == 'whitespace_boundary')
    fallback = sum(1 for r in results if r['detection_method'] == 'fallback')

    print(f"Total pages: {total}")
    print(f"Line detected: {line_detected} ({line_detected/total*100:.1f}%)")
    print(f"Whitespace boundary: {boundary} ({boundary/total*100:.1f}%)")
    print(f"Fallback: {fallback} ({fallback/total*100:.1f}%)")
    print(f"\nSuccess rate: {(line_detected + boundary)/total*100:.1f}%")

    print(f"\n[+] Results saved to: {results_path}")


if __name__ == "__main__":
    test_all_pdfs()
