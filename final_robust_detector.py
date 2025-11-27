"""
Final Robust Footer Detector - Based on User's Clear Examples

Strategy (verified with user's examples):
1. Find address (last centered text element, ~94-96% of page)
2. Zone 1 (yellow): After address = final margin (DISCARD)
3. Detect footnote: Check blackness between zones
4. If HAS footnote:
   - Zone 2 (yellow): Between footnote and address (DISCARD)
   - Zone CYAN: Large whitespace BEFORE footnote (~79-89%)
5. If NO footnote:
   - Zone CYAN: Large whitespace BEFORE address (~87-93%)
"""

import cv2
import numpy as np
from pdf2image import convert_from_path
from pathlib import Path
import json

PAGE_MID = 0.50
WHITESPACE_THRESHOLD = 0.05
MIN_ZONE_HEIGHT = 20
LINE_MIN_LENGTH = 0.02
LINE_MAX_LENGTH = 0.20
FOOTNOTE_BLACKNESS_THRESHOLD = 0.10  # 10% blackness indicates footnote text


def calculate_row_blackness(binary_image, start_y, end_y):
    """Calculate blackness for each row"""
    width = binary_image.shape[1]
    row_blackness = []
    for y in range(start_y, end_y):
        row = binary_image[y, :]
        blackness = np.sum(row == 0) / width
        row_blackness.append({'y': y, 'blackness': blackness})
    return row_blackness


def find_all_whitespace_zones(binary_image):
    """Find all whitespace zones, sorted by height (largest first)"""
    height, width = binary_image.shape
    start_y = int(height * PAGE_MID)

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
                    'height': y - zone_start
                })
            in_zone = False

    if in_zone and row_blackness:
        y_last = row_blackness[-1]['y']
        if y_last - zone_start >= MIN_ZONE_HEIGHT:
            zones.append({
                'start': zone_start,
                'end': y_last,
                'height': y_last - zone_start
            })

    # Sort by HEIGHT (largest first)
    zones.sort(key=lambda z: z['height'], reverse=True)
    return zones


def find_address_and_margin(binary_image):
    """
    Find the address (last centered text) and final margin zone.

    Returns: (address_y_range, margin_zone)
    """
    height, width = binary_image.shape

    # Search bottom 20% for address
    search_start = int(height * 0.80)

    # Find last text block (address is usually 94-97%)
    row_blackness = calculate_row_blackness(binary_image, search_start, height)

    # Find the last continuous text region
    text_threshold = 0.05
    address_end = None
    address_start = None

    for i in range(len(row_blackness) - 1, -1, -1):
        y = row_blackness[i]['y']
        blackness = row_blackness[i]['blackness']

        if blackness > text_threshold:
            if address_end is None:
                address_end = y
            address_start = y
        elif address_end is not None:
            # Found gap after text
            break

    if address_start is None or address_end is None:
        # Fallback: assume address at 94-96%
        address_start = int(height * 0.94)
        address_end = int(height * 0.96)

    # Margin zone is after address_end
    margin_zone = {
        'start': address_end,
        'end': height,
        'height': height - address_end,
        'type': 'final_margin'
    }

    return (address_start, address_end), margin_zone


def detect_footnote(binary_image, address_start, zones, debug=False):
    """
    Detect if footnote exists by analyzing zone structure near address.

    Strategy:
    1. Find zones before address, sorted by proximity to address (closest first)
    2. The CLOSEST large zone to address (>150px) is the cyan zone
    3. Look for other zones between that cyan and even earlier zones
    4. If there's a large zone (>300px) much earlier -> that's the actual cyan, current one is footnote

    Returns: (has_footnote, footnote_zone, cyan_zone)
    """
    height, width = binary_image.shape

    # Find all zones that end before or at the address
    zones_before_address = [z for z in zones if z['end'] <= address_start + 10]

    if debug:
        print(f"  [DEBUG] Address starts at Y={address_start} ({address_start/height:.1%})")
        print(f"  [DEBUG] Found {len(zones_before_address)} zones before address")

    if not zones_before_address:
        # Fallback
        return False, None, zones[0] if zones else None

    # Sort by proximity to address (closest first)
    zones_before_address_sorted = sorted(zones_before_address, key=lambda z: address_start - z['end'])

    if debug:
        print(f"  [DEBUG] Zones sorted by proximity to address:")
        for i, z in enumerate(zones_before_address_sorted[:5]):  # Show top 5
            print(f"  [DEBUG]   {i+1}. Y={z['start']}-{z['end']} ({z['start']/height:.1%}-{z['end']/height:.1%}), Height={z['height']}px, Distance={address_start - z['end']}px")

    # Find the closest zone with reasonable size (>150px)
    closest_large_zone = None
    for z in zones_before_address_sorted:
        if z['height'] > 150:
            closest_large_zone = z
            break

    if closest_large_zone is None:
        # Fallback: use largest zone overall
        closest_large_zone = max(zones_before_address, key=lambda z: z['height'])

    if debug:
        print(f"  [DEBUG] Closest large zone: Y={closest_large_zone['start']}-{closest_large_zone['end']} ({closest_large_zone['start']/height:.1%}-{closest_large_zone['end']/height:.1%}), Height={closest_large_zone['height']}px")

    # Now check TWO scenarios for footnote:
    # Scenario A: There's a zone BETWEEN closest_large_zone and address (footnote zone)
    # Scenario B: There's a MUCH LARGER zone earlier, and closest_large_zone is the footnote

    # Scenario A: Look for zones between closest_large_zone.end and address_start
    zones_after_closest = [z for z in zones_before_address if z['start'] >= closest_large_zone['end'] - 10 and z['end'] <= address_start]

    if debug and zones_after_closest:
        print(f"  [DEBUG] Found {len(zones_after_closest)} zones between closest large zone and address:")
        for i, z in enumerate(zones_after_closest):
            print(f"  [DEBUG]   {i+1}. Y={z['start']}-{z['end']} ({z['start']/height:.1%}-{z['end']/height:.1%}), Height={z['height']}px")

    # Check if there's a zone >50px but <120px between closest_large and address
    # (footnotes are typically small zones, not large content zones)
    intermediate_footnote_candidates = [z for z in zones_after_closest if 50 < z['height'] < 120]

    if intermediate_footnote_candidates:
        # Scenario A: Found footnote zone between cyan and address
        cyan_zone = closest_large_zone
        footnote_zone = max(intermediate_footnote_candidates, key=lambda z: z['height'])
        footnote_zone['type'] = 'footnote_area'

        if debug:
            print(f"  [DEBUG] FOOTNOTE DETECTED (Scenario A)! Zone between cyan and address:")
            print(f"  [DEBUG]   Cyan zone: Y={cyan_zone['start']}-{cyan_zone['end']} ({cyan_zone['start']/height:.1%}-{cyan_zone['end']/height:.1%})")
            print(f"  [DEBUG]   Footnote zone: Y={footnote_zone['start']}-{footnote_zone['end']} ({footnote_zone['start']/height:.1%}-{footnote_zone['end']/height:.1%})")

        return True, footnote_zone, cyan_zone

    # Scenario B: Check if there's a MUCH LARGER zone (>300px) that ends before closest_large_zone
    earlier_zones = [z for z in zones_before_address if z['end'] < closest_large_zone['start'] - 30]
    very_large_earlier_zones = [z for z in earlier_zones if z['height'] > 300]

    if very_large_earlier_zones:
        # Scenario B: Found very large zone earlier - that's the cyan zone
        cyan_zone = max(very_large_earlier_zones, key=lambda z: z['height'])
        footnote_zone = closest_large_zone
        footnote_zone['type'] = 'footnote_area'

        if debug:
            print(f"  [DEBUG] FOOTNOTE DETECTED (Scenario B)! Very large zone earlier:")
            print(f"  [DEBUG]   Cyan zone: Y={cyan_zone['start']}-{cyan_zone['end']} ({cyan_zone['start']/height:.1%}-{cyan_zone['end']/height:.1%})")
            print(f"  [DEBUG]   Footnote zone: Y={footnote_zone['start']}-{footnote_zone['end']} ({footnote_zone['start']/height:.1%}-{footnote_zone['end']/height:.1%})")

        return True, footnote_zone, cyan_zone

    # No footnote detected
    cyan_zone = closest_large_zone

    if debug:
        print(f"  [DEBUG] No footnote detected")
        print(f"  [DEBUG] Cyan zone: Y={cyan_zone['start']}-{cyan_zone['end']} ({cyan_zone['start']/height:.1%}-{cyan_zone['end']/height:.1%})")

    return False, None, cyan_zone


def find_separator_in_cyan_zone(binary_image, cyan_zone):
    """Find horizontal separator segment in cyan zone"""
    height, width = binary_image.shape

    zone_region = binary_image[cyan_zone['start']:cyan_zone['end'], :]
    inverted = cv2.bitwise_not(zone_region)

    lines = cv2.HoughLinesP(
        inverted,
        rho=1,
        theta=np.pi/180,
        threshold=30,
        minLineLength=int(width * LINE_MIN_LENGTH),
        maxLineGap=10
    )

    if lines is None:
        return None

    candidates = []
    for line in lines:
        x1, y1, x2, y2 = line[0]

        if abs(y2 - y1) <= 3:
            adjusted_y = cyan_zone['start'] + y1
            line_length = abs(x2 - x1)

            if width * LINE_MIN_LENGTH <= line_length <= width * LINE_MAX_LENGTH:
                # Check isolation (white space to right)
                x_end = max(x1, x2)
                if x_end + 100 < width:
                    right_sample = binary_image[adjusted_y, x_end+10:min(x_end+100, width)]
                    if right_sample.size > 0:
                        whiteness = np.sum(right_sample == 255) / right_sample.size
                        if whiteness > 0.90:
                            candidates.append({
                                'y': adjusted_y,
                                'length': line_length,
                                'length_pct': line_length / width
                            })

    if candidates:
        # Return bottom-most candidate
        return max(candidates, key=lambda c: c['y'])

    return None


def detect_footer_line(binary_image, debug=False):
    """Main detection logic"""
    height, width = binary_image.shape

    if debug:
        print(f"  [INFO] Page: {width}x{height}")

    # Step 1: Find address and margin
    (addr_start, addr_end), margin_zone = find_address_and_margin(binary_image)

    if debug:
        print(f"  [ADDRESS] Y={addr_start}-{addr_end} ({addr_start/height:.1%}-{addr_end/height:.1%})")
        print(f"  [MARGIN] Y={margin_zone['start']}-{margin_zone['end']} ({margin_zone['start']/height:.1%}-{margin_zone['end']/height:.1%}), "
              f"Height={margin_zone['height']}px")

    # Step 2: Find all zones
    zones = find_all_whitespace_zones(binary_image)

    if debug:
        print(f"  [ZONES] Found {len(zones)} whitespace zones")

    # Step 3: Detect footnote and identify cyan zone
    has_footnote, footnote_zone, cyan_zone = detect_footnote(binary_image, addr_start, zones, debug=debug)

    if cyan_zone is None:
        # Fallback
        return int(height * 0.90), {
            'method': 'fallback',
            'confidence': 'low',
            'footer_y': int(height * 0.90),
            'details': {}
        }

    if debug:
        if has_footnote:
            print(f"  [FOOTNOTE] Detected at Y={footnote_zone['start']}-{footnote_zone['end']} "
                  f"({footnote_zone['start']/height:.1%}-{footnote_zone['end']/height:.1%})")
        else:
            print(f"  [NO FOOTNOTE]")

        print(f"  [CYAN ZONE] Y={cyan_zone['start']}-{cyan_zone['end']} "
              f"({cyan_zone['start']/height:.1%}-{cyan_zone['end']/height:.1%}), "
              f"Height={cyan_zone['height']}px")

    # Step 4: Search for separator in cyan zone
    separator = find_separator_in_cyan_zone(binary_image, cyan_zone)

    if separator:
        footer_y = separator['y']
        method = 'separator_segment'
        confidence = 'high'

        if debug:
            print(f"  [SEPARATOR] Found at Y={footer_y} ({footer_y/height:.1%}), "
                  f"Length={separator['length_pct']:.1%}")
    else:
        footer_y = cyan_zone['end']
        method = 'cyan_zone_base'
        confidence = 'medium'

        if debug:
            print(f"  [NO SEPARATOR] Using cyan zone base at Y={footer_y} ({footer_y/height:.1%})")

    detection_info = {
        'method': method,
        'confidence': confidence,
        'footer_y': int(footer_y),
        'details': {
            'has_footnote': has_footnote,
            'cyan_zone_start': int(cyan_zone['start']),
            'cyan_zone_end': int(cyan_zone['end']),
            'cyan_zone_height': int(cyan_zone['height']),
            'address_start': int(addr_start),
            'address_end': int(addr_end),
            'margin_zone': {
                'start': int(margin_zone['start']),
                'end': int(margin_zone['end']),
                'height': int(margin_zone['height'])
            }
        }
    }

    if has_footnote and footnote_zone:
        detection_info['details']['footnote_zone'] = {
            'start': int(footnote_zone['start']),
            'end': int(footnote_zone['end']),
            'height': int(footnote_zone['height'])
        }

    if separator:
        detection_info['details']['separator_length_pct'] = float(separator['length_pct'])

    return int(footer_y), detection_info


def visualize_detection(pdf_path, page_num, output_dir):
    """Create visualization with yellow and cyan zones like user's examples"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=300)
    page_image = np.array(images[0])

    gray = cv2.cvtColor(page_image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    print(f"\nProcessing {pdf_path.name} - Page {page_num}")
    footer_y, info = detect_footer_line(binary, debug=True)

    # Create visualization
    vis_image = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    height, width = binary.shape

    # Draw vertical center line
    center_x = width // 2
    cv2.line(vis_image, (center_x, 0), (center_x, height), (200, 200, 200), 2)

    # Draw YELLOW zones (discarded)
    # Zone 1: Final margin
    if 'margin_zone' in info['details']:
        margin = info['details']['margin_zone']
        overlay = vis_image.copy()
        cv2.rectangle(overlay, (0, margin['start']), (width, margin['end']), (0, 255, 255), -1)
        cv2.addWeighted(overlay, 0.4, vis_image, 0.6, 0, vis_image)

    # Zone 2: Footnote area (if exists)
    if 'footnote_zone' in info['details']:
        fn = info['details']['footnote_zone']
        overlay = vis_image.copy()
        cv2.rectangle(overlay, (0, fn['start']), (width, fn['end']), (0, 255, 255), -1)
        cv2.addWeighted(overlay, 0.4, vis_image, 0.6, 0, vis_image)

    # Draw CYAN zone (correct one)
    cyan_start = info['details']['cyan_zone_start']
    cyan_end = info['details']['cyan_zone_end']
    overlay = vis_image.copy()
    cv2.rectangle(overlay, (0, cyan_start), (width, cyan_end), (255, 255, 0), -1)
    cv2.addWeighted(overlay, 0.3, vis_image, 0.7, 0, vis_image)

    # Draw borders
    cv2.line(vis_image, (0, cyan_start), (width, cyan_start), (255, 255, 0), 3)
    cv2.line(vis_image, (0, cyan_end), (width, cyan_end), (255, 255, 0), 3)

    # Draw footer line
    color = (0, 255, 0) if info['method'] != 'fallback' else (0, 0, 255)
    cv2.line(vis_image, (0, footer_y), (width, footer_y), color, 4)

    # Labels
    label_text = f"CYAN ZONE ({cyan_start/height:.1%}-{cyan_end/height:.1%})"
    if info['details']['has_footnote']:
        label_text += " [HAS FOOTNOTE]"
    cv2.putText(vis_image, label_text, (10, cyan_start + 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

    line_label = f"{info['method'].upper()}: {footer_y/height:.1%}"
    cv2.putText(vis_image, line_label, (10, footer_y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

    # Save
    filename = f"{pdf_path.stem}_page{page_num}_final.png"
    output_path = output_dir / filename
    cv2.imwrite(str(output_path), vis_image)
    print(f"[+] Saved: {filename}\n")

    return info


def test_one_pdf(pdf_filename):
    """Test on one PDF to visualize zone detection"""
    pdf_path = Path(f"data/raw/scanned/{pdf_filename}")
    output_dir = Path("final_robust_test")

    print(f"\n{'='*80}")
    print(f"Testing: {pdf_path.name}")
    print('='*80)

    images = convert_from_path(pdf_path, dpi=72)
    num_pages = len(images)

    results = []

    for page_num in range(1, num_pages + 1):
        info = visualize_detection(pdf_path, page_num, output_dir)
        results.append({
            'page': page_num,
            'method': info['method'],
            'has_footnote': info['details']['has_footnote'],
            'footer_y_pct': info['footer_y'] / info['details'].get('cyan_zone_end', 1)
        })

    # Summary
    print(f"\n{'='*40}")
    print("SUMMARY")
    print('='*40)
    print(f"Total pages: {len(results)}")
    print(f"With footnotes: {sum(1 for r in results if r['has_footnote'])}")
    print(f"Separator found: {sum(1 for r in results if r['method'] == 'separator_segment')}")
    print(f"Cyan base used: {sum(1 for r in results if r['method'] == 'cyan_zone_base')}")


if __name__ == "__main__":
    # Test on the PDF from user's examples
    test_one_pdf("Informe_CF_N_001-2016.pdf")
