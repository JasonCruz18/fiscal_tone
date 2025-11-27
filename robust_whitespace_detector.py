"""
Robust Whitespace-Based Footer Detector

Strategy based on user's clear analysis:

1. Identify ALL whitespace zones from BOTTOM to TOP
2. Always discard 1st zone (final margin below address)
3. Check if 3rd zone is LARGEST of top 3 zones:
   - YES → Footnote exists → Cyan zone = 3rd zone
   - NO → No footnote → Cyan zone = 2nd zone
4. Search for short separator segment in cyan zone (left side, white space to right)
5. If not found → Use base of cyan zone
6. Fallback if needed

Key insight: Address is always centered and is the LAST text element on page.
"""

import cv2
import numpy as np
from pdf2image import convert_from_path
from pathlib import Path
import json

# Configuration
PAGE_MID = 0.50
WHITESPACE_THRESHOLD = 0.05
MIN_ZONE_HEIGHT = 20
LINE_MIN_LENGTH = 0.02
LINE_MAX_LENGTH = 0.20
SEGMENT_CHECK_RIGHT_MARGIN = 100  # Check 100px to right for isolation


def calculate_row_blackness(binary_image, start_y, end_y):
    """Calculate blackness for each row"""
    width = binary_image.shape[1]
    row_blackness = []

    for y in range(start_y, end_y):
        row = binary_image[y, :]
        blackness = np.sum(row == 0) / width
        row_blackness.append({'y': y, 'blackness': blackness})

    return row_blackness


def find_all_whitespace_zones(binary_image, start_from_mid=True):
    """
    Find ALL whitespace zones from bottom to top.
    Returns zones sorted from BOTTOM to TOP.
    """
    height, width = binary_image.shape
    start_y = int(height * PAGE_MID) if start_from_mid else 0

    row_blackness = calculate_row_blackness(binary_image, start_y, height)

    zones = []
    in_zone = False
    zone_start = 0

    for item in row_blackness:
        y = item['y']
        blackness = item['blackness']

        if blackness < WHITESPACE_THRESHOLD and not in_zone:
            zone_start = y
            in_zone = True
        elif blackness >= WHITESPACE_THRESHOLD and in_zone:
            if y - zone_start >= MIN_ZONE_HEIGHT:
                zones.append({
                    'start': zone_start,
                    'end': y,
                    'height': y - zone_start,
                    'position_pct': zone_start / height
                })
            in_zone = False

    # Handle zone extending to end
    if in_zone and row_blackness:
        y_last = row_blackness[-1]['y']
        if y_last - zone_start >= MIN_ZONE_HEIGHT:
            zones.append({
                'start': zone_start,
                'end': y_last,
                'height': y_last - zone_start,
                'position_pct': zone_start / height
            })

    # Sort from BOTTOM to TOP (highest Y first)
    zones.sort(key=lambda z: z['end'], reverse=True)

    return zones


def identify_cyan_zone(zones, height, debug=False):
    """
    Identify the correct cyan zone based on user's logic:

    1. Discard 1st zone (final margin)
    2. If 3rd zone is LARGEST of top 3 → footnote exists → cyan = 3rd
    3. Else → no footnote → cyan = 2nd

    Returns: (cyan_zone, has_footnote, discarded_zones)
    """
    if len(zones) < 2:
        return None, False, []

    # Always discard 1st zone (final margin below address)
    discarded = [zones[0]]
    remaining = zones[1:]

    if debug:
        print(f"\n  [DISCARD] Zone 1 (final margin): Y={zones[0]['start']}-{zones[0]['end']} "
              f"({zones[0]['start']/height:.1%}-{zones[0]['end']/height:.1%}), "
              f"Height={zones[0]['height']}px")

    # Check if we have at least 3 zones total (to check 2nd and 3rd)
    if len(zones) < 3:
        # Only 2 zones total → use 2nd as cyan
        cyan_zone = zones[1]
        has_footnote = False

        if debug:
            print(f"  [INFO] Only 2 zones total -> Using 2nd zone as cyan (no footnote)")
    else:
        # We have at least 3 zones
        # Get top 3 zones from bottom (1st already discarded, so get next 2)
        zone_2 = zones[1]
        zone_3 = zones[2]

        # Check if 3rd is LARGEST of the 3
        if zone_3['height'] > zone_2['height'] and zone_3['height'] > zones[0]['height']:
            # 3rd is largest → footnote exists
            cyan_zone = zone_3
            has_footnote = True
            discarded.append(zone_2)  # Also discard 2nd zone

            if debug:
                print(f"  [FOOTNOTE DETECTED] Zone 3 is largest ({zone_3['height']}px > "
                      f"{zone_2['height']}px, {zones[0]['height']}px)")
                print(f"  [DISCARD] Zone 2: Y={zone_2['start']}-{zone_2['end']} "
                      f"({zone_2['start']/height:.1%}-{zone_2['end']/height:.1%}), "
                      f"Height={zone_2['height']}px")
        else:
            # 3rd is not largest → no footnote
            cyan_zone = zone_2
            has_footnote = False

            if debug:
                print(f"  [NO FOOTNOTE] Zone 3 is not largest ({zone_3['height']}px vs "
                      f"{zone_2['height']}px, {zones[0]['height']}px)")

    if debug:
        print(f"  [CYAN ZONE] Y={cyan_zone['start']}-{cyan_zone['end']} "
              f"({cyan_zone['start']/height:.1%}-{cyan_zone['end']/height:.1%}), "
              f"Height={cyan_zone['height']}px")

    return cyan_zone, has_footnote, discarded


def find_separator_segment_in_zone(binary_image, zone, debug=False):
    """
    Search for short horizontal segment in cyan zone.

    Criteria:
    - Left side of zone (bottom-left region)
    - Short length (2-20% of width)
    - White space to the RIGHT (no text neighbors)

    Returns: line dict or None
    """
    height, width = binary_image.shape

    # Extract zone region
    zone_region = binary_image[zone['start']:zone['end'], :]
    zone_height = zone['end'] - zone['start']

    # Invert for Hough
    inverted = cv2.bitwise_not(zone_region)

    # Detect lines
    lines = cv2.HoughLinesP(
        inverted,
        rho=1,
        theta=np.pi/180,
        threshold=30,
        minLineLength=int(width * LINE_MIN_LENGTH),
        maxLineGap=10
    )

    if lines is None:
        if debug:
            print(f"  [SEARCH] No lines found in cyan zone")
        return None

    # Filter horizontal lines and adjust coordinates
    candidates = []
    for line in lines:
        x1, y1, x2, y2 = line[0]

        if abs(y2 - y1) <= 3:  # Horizontal
            adjusted_y = zone['start'] + y1
            line_length = abs(x2 - x1)

            if width * LINE_MIN_LENGTH <= line_length <= width * LINE_MAX_LENGTH:
                candidates.append({
                    'x1': min(x1, x2),
                    'x2': max(x1, x2),
                    'y': adjusted_y,
                    'length': line_length,
                    'length_pct': line_length / width
                })

    if debug:
        print(f"  [SEARCH] Found {len(candidates)} candidate segments in cyan zone")

    # Check each candidate for isolation (white space to right)
    for candidate in candidates:
        x_end = candidate['x2']
        y = candidate['y']

        # Check region to the RIGHT
        x_check_start = min(x_end + 10, width)
        x_check_end = min(x_end + SEGMENT_CHECK_RIGHT_MARGIN, width)

        if x_check_start >= width:
            continue

        # Sample pixels to the right at same Y level
        right_sample = binary_image[y, x_check_start:x_check_end]

        if right_sample.size == 0:
            continue

        # Check if mostly white (isolated)
        whiteness = np.sum(right_sample == 255) / right_sample.size

        if whiteness > 0.90:  # 90% white to the right
            if debug:
                print(f"  [FOUND] Isolated segment at Y={candidate['y']} ({candidate['y']/height:.1%}), "
                      f"Length={candidate['length_pct']:.1%}, Whiteness to right={whiteness:.1%}")
            return candidate

    if debug:
        print(f"  [NOT FOUND] No isolated segment in cyan zone")

    return None


def detect_footer_line(binary_image, debug=False):
    """
    Main detection logic following user's robust strategy.

    Returns: (footer_y, detection_info)
    """
    height, width = binary_image.shape

    detection_info = {
        'method': 'fallback',
        'confidence': 'low',
        'footer_y': int(height * 0.90),
        'details': {}
    }

    if debug:
        print(f"  [INFO] Page: {width}x{height}")

    # Step 1: Find all whitespace zones from bottom
    zones = find_all_whitespace_zones(binary_image, start_from_mid=True)

    if debug:
        print(f"  [INFO] Found {len(zones)} whitespace zones from bottom to top")

    if len(zones) < 2:
        if debug:
            print(f"  [FALLBACK] Not enough zones found")
        return detection_info['footer_y'], detection_info

    # Step 2: Identify cyan zone
    cyan_zone, has_footnote, discarded_zones = identify_cyan_zone(zones, height, debug)

    if cyan_zone is None:
        if debug:
            print(f"  [FALLBACK] Could not identify cyan zone")
        return detection_info['footer_y'], detection_info

    # Step 3: Search for separator segment in cyan zone
    separator = find_separator_segment_in_zone(binary_image, cyan_zone, debug)

    if separator:
        # Found separator segment
        footer_y = separator['y']
        method = 'separator_segment'
        confidence = 'high'

        if debug:
            print(f"  [SUCCESS] Using separator segment at Y={footer_y} ({footer_y/height:.1%})")
    else:
        # Use base of cyan zone
        footer_y = cyan_zone['end']
        method = 'cyan_zone_base'
        confidence = 'medium'

        if debug:
            print(f"  [SUCCESS] Using cyan zone base at Y={footer_y} ({footer_y/height:.1%})")

    detection_info = {
        'method': method,
        'confidence': confidence,
        'footer_y': int(footer_y),
        'details': {
            'cyan_zone_start': int(cyan_zone['start']),
            'cyan_zone_end': int(cyan_zone['end']),
            'cyan_zone_height': int(cyan_zone['height']),
            'has_footnote': has_footnote,
            'num_zones_found': len(zones),
            'num_discarded_zones': len(discarded_zones),
            'discarded_zones': [{'start': int(z['start']), 'end': int(z['end']),
                                 'height': int(z['height'])} for z in discarded_zones]
        }
    }

    if separator:
        detection_info['details']['separator_length_pct'] = float(separator['length_pct'])

    return int(footer_y), detection_info


def visualize_detection(pdf_path, page_num, output_dir):
    """Create visualization showing cyan zone and discarded yellow zones"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Convert PDF
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

    # Draw vertical center line (like in user's examples)
    center_x = width // 2
    cv2.line(vis_image, (center_x, 0), (center_x, height), (128, 128, 128), 2)

    # Draw discarded zones in YELLOW
    if 'discarded_zones' in info['details']:
        for zone in info['details']['discarded_zones']:
            overlay = vis_image.copy()
            cv2.rectangle(overlay, (0, zone['start']), (width, zone['end']), (0, 255, 255), -1)
            cv2.addWeighted(overlay, 0.3, vis_image, 0.7, 0, vis_image)
            cv2.line(vis_image, (0, zone['start']), (width, zone['start']), (0, 255, 255), 2)
            cv2.line(vis_image, (0, zone['end']), (width, zone['end']), (0, 255, 255), 2)

    # Draw CYAN zone
    if 'cyan_zone_start' in info['details']:
        cyan_start = info['details']['cyan_zone_start']
        cyan_end = info['details']['cyan_zone_end']
        overlay = vis_image.copy()
        cv2.rectangle(overlay, (0, cyan_start), (width, cyan_end), (255, 255, 0), -1)
        cv2.addWeighted(overlay, 0.3, vis_image, 0.7, 0, vis_image)
        cv2.line(vis_image, (0, cyan_start), (width, cyan_start), (255, 255, 0), 3)
        cv2.line(vis_image, (0, cyan_end), (width, cyan_end), (255, 255, 0), 3)

        label_text = f"CYAN ZONE ({cyan_start/height:.1%}-{cyan_end/height:.1%})"
        if info['details']['has_footnote']:
            label_text += " [FOOTNOTE]"
        cv2.putText(vis_image, label_text, (10, cyan_start + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 0), 2)

    # Draw footer line
    color = (0, 255, 0) if info['method'] != 'fallback' else (0, 0, 255)
    cv2.line(vis_image, (0, footer_y), (width, footer_y), color, 4)
    label = f"{info['method'].upper()}: {footer_y/height:.1%}"
    cv2.putText(vis_image, label, (10, footer_y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

    # Save
    filename = f"{pdf_path.stem}_page{page_num}_robust.png"
    output_path = output_dir / filename
    cv2.imwrite(str(output_path), vis_image)
    print(f"[+] Saved: {filename}\n")

    return info


def test_all_pdfs():
    """Test on all 13 PDFs"""
    scanned_dir = Path("data/raw/scanned")
    output_dir = Path("robust_whitespace_test")

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
    separator = sum(1 for r in results if r['detection_method'] == 'separator_segment')
    cyan_base = sum(1 for r in results if r['detection_method'] == 'cyan_zone_base')
    fallback = sum(1 for r in results if r['detection_method'] == 'fallback')

    print(f"Total pages: {total}")
    print(f"Separator segment found: {separator} ({separator/total*100:.1f}%)")
    print(f"Cyan zone base: {cyan_base} ({cyan_base/total*100:.1f}%)")
    print(f"Fallback: {fallback} ({fallback/total*100:.1f}%)")
    print(f"\nSuccess rate: {(separator + cyan_base)/total*100:.1f}%")

    # Footnote statistics
    with_footnote = sum(1 for r in results if r['details'].get('has_footnote', False))
    print(f"\nPages with footnotes: {with_footnote} ({with_footnote/total*100:.1f}%)")

    print(f"\n[+] Results saved to: {results_path}")


if __name__ == "__main__":
    test_all_pdfs()
