"""
Hybrid Footer Detector - Combines line detection with whitespace zone detection

Strategy:
1. PRIMARY: Detect short horizontal separator lines (after 50% of page)
2. SECONDARY: Use whitespace zone detection (if line detection fails)
3. CORRECTION: Final margin zone is ALWAYS yellow (never cyan)
"""

import cv2
import numpy as np
from pdf2image import convert_from_path
from pathlib import Path
import json


# === CONFIGURATION ===
LINE_MIN_LENGTH_RATIO = 0.02  # 2% of page width
LINE_MAX_LENGTH_RATIO = 0.20  # 20% of page width
LINE_SEARCH_START = 0.50      # Start searching after 50% of page
LINE_SEARCH_END = 0.90        # Stop before 90% (avoid address region)
WHITESPACE_THRESHOLD = 0.05   # 5% blackness = whitespace
MIN_ZONE_HEIGHT = 20          # Minimum whitespace zone height in pixels
FOOTNOTE_ZONE_MIN = 50        # Min height for footnote zone
FOOTNOTE_ZONE_MAX = 120       # Max height for footnote zone
LARGE_ZONE_THRESHOLD = 150    # Min height for "large zone"
MARGIN_MIN_GAP = 50           # Minimum gap between cyan zone and address


def detect_separator_line(binary_image, debug=False):
    """
    PRIMARY STRATEGY: Detect short horizontal separator lines

    Returns: (line_y, method_info) or (None, None) if not found
    """
    height, width = binary_image.shape

    # Define search region (50%-95% of page)
    search_start = int(height * LINE_SEARCH_START)
    search_end = int(height * LINE_SEARCH_END)
    search_region = binary_image[search_start:search_end, :]

    # Invert for line detection
    inverted = cv2.bitwise_not(search_region)

    # Detect lines using Hough transform
    lines = cv2.HoughLinesP(
        inverted,
        rho=1,
        theta=np.pi/180,
        threshold=30,
        minLineLength=int(width * LINE_MIN_LENGTH_RATIO),
        maxLineGap=10
    )

    if lines is None:
        if debug:
            print(f"  [LINE] No lines detected in search region")
        return None, None

    # Filter horizontal lines within length constraints
    candidates = []
    for line in lines:
        x1, y1, x2, y2 = line[0]

        # Check if line is horizontal (vertical deviation <= 3px)
        if abs(y2 - y1) <= 3:
            line_length = abs(x2 - x1)
            length_ratio = line_length / width

            # Check length constraints
            if LINE_MIN_LENGTH_RATIO <= length_ratio <= LINE_MAX_LENGTH_RATIO:
                # Adjust Y to absolute position
                absolute_y = search_start + y1

                # Check isolation (whitespace to the right)
                x_end = max(x1, x2)
                if x_end + 100 < width:
                    right_sample = binary_image[absolute_y, x_end+10:min(x_end+100, width)]
                    if right_sample.size > 0:
                        whiteness = np.sum(right_sample == 255) / right_sample.size
                        if whiteness > 0.85:  # 85% white to the right
                            candidates.append({
                                'y': absolute_y,
                                'length': line_length,
                                'length_pct': length_ratio,
                                'whiteness': whiteness
                            })

    if not candidates:
        if debug:
            print(f"  [LINE] Found {len(lines)} lines but none met isolation criteria")
        return None, None

    # Select the bottom-most candidate (closest to footer)
    selected = max(candidates, key=lambda c: c['y'])

    if debug:
        print(f"  [LINE] Found {len(candidates)} candidates, selected Y={selected['y']} ({selected['y']/height:.1%}), Length={selected['length_pct']:.1%}")

    method_info = {
        'method': 'separator_line',
        'confidence': 'high',
        'line_y': selected['y'],
        'line_length_pct': selected['length_pct'],
        'total_candidates': len(candidates)
    }

    return selected['y'], method_info


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
    """Find all whitespace zones, sorted by height"""
    height, width = binary_image.shape
    start_y = int(height * 0.50)  # Start from 50%

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

    # Sort by height (largest first)
    zones.sort(key=lambda z: z['height'], reverse=True)
    return zones


def find_address_region(binary_image):
    """Find address region (last text block at bottom)"""
    height, width = binary_image.shape
    search_start = int(height * 0.80)

    row_blackness = calculate_row_blackness(binary_image, search_start, height)

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
            break

    if address_start is None or address_end is None:
        address_start = int(height * 0.93)
        address_end = int(height * 0.95)

    return address_start, address_end


def detect_zones_strategy(binary_image, address_start, debug=False):
    """
    SECONDARY STRATEGY: Detect footer using whitespace zones

    CORRECTION: The zone closest to address is FINAL MARGIN (yellow), not cyan
    """
    height, width = binary_image.shape

    zones = find_all_whitespace_zones(binary_image)

    if not zones:
        if debug:
            print(f"  [ZONES] No whitespace zones found")
        return None, None

    if debug:
        print(f"  [ZONES] Found {len(zones)} whitespace zones")

    # CRITICAL: Find zones that end BEFORE address with sufficient gap
    # The zone closest to address is the FINAL MARGIN (always yellow/discard)
    cyan_candidates = [z for z in zones if z['end'] < address_start - MARGIN_MIN_GAP]

    if not cyan_candidates:
        if debug:
            print(f"  [ZONES] No cyan candidates found (all zones too close to address)")
        return None, None

    # Sort by proximity to address (closest first)
    cyan_candidates_sorted = sorted(cyan_candidates, key=lambda z: address_start - z['end'])

    if debug:
        print(f"  [ZONES] {len(cyan_candidates)} cyan candidates (excluding final margin)")
        for i, z in enumerate(cyan_candidates_sorted[:3]):
            print(f"  [ZONES]   {i+1}. Y={z['start']}-{z['end']} ({z['start']/height:.1%}-{z['end']/height:.1%}), H={z['height']}px, Gap={address_start - z['end']}px")

    # Find closest large zone
    closest_large = None
    for z in cyan_candidates_sorted:
        if z['height'] > LARGE_ZONE_THRESHOLD:
            closest_large = z
            break

    if closest_large is None:
        closest_large = cyan_candidates_sorted[0]

    # Check for footnote (intermediate zone between cyan and address)
    has_footnote = False
    footnote_zone = None

    zones_after_cyan = [z for z in zones if z['start'] >= closest_large['end'] - 10 and z['end'] <= address_start - MARGIN_MIN_GAP]
    footnote_candidates = [z for z in zones_after_cyan if FOOTNOTE_ZONE_MIN < z['height'] < FOOTNOTE_ZONE_MAX]

    if footnote_candidates:
        has_footnote = True
        footnote_zone = max(footnote_candidates, key=lambda z: z['height'])
        if debug:
            print(f"  [ZONES] FOOTNOTE detected: Y={footnote_zone['start']}-{footnote_zone['end']} ({footnote_zone['start']/height:.1%}-{footnote_zone['end']/height:.1%})")

    # Use separator line if found within cyan zone, otherwise use zone base
    separator = None
    footer_y = closest_large['end']

    # Try to find separator within cyan zone
    cyan_region = binary_image[closest_large['start']:closest_large['end'], :]
    inverted_cyan = cv2.bitwise_not(cyan_region)

    lines = cv2.HoughLinesP(inverted_cyan, 1, np.pi/180, 30, minLineLength=int(width * LINE_MIN_LENGTH_RATIO), maxLineGap=10)

    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if abs(y2 - y1) <= 3:
                line_length = abs(x2 - x1)
                if LINE_MIN_LENGTH_RATIO <= line_length/width <= LINE_MAX_LENGTH_RATIO:
                    separator_y = closest_large['start'] + y1
                    footer_y = separator_y
                    separator = {'y': separator_y, 'length_pct': line_length/width}
                    break

    method_info = {
        'method': 'whitespace_zones',
        'confidence': 'medium' if separator is None else 'high',
        'footer_y': int(footer_y),
        'has_footnote': has_footnote,
        'cyan_zone': {
            'start': int(closest_large['start']),
            'end': int(closest_large['end']),
            'height': int(closest_large['height'])
        },
        'separator_in_cyan': separator is not None
    }

    if has_footnote:
        method_info['footnote_zone'] = {
            'start': int(footnote_zone['start']),
            'end': int(footnote_zone['end']),
            'height': int(footnote_zone['height'])
        }

    if debug:
        print(f"  [ZONES] Cyan zone: Y={closest_large['start']}-{closest_large['end']} ({closest_large['start']/height:.1%}-{closest_large['end']/height:.1%})")
        if separator:
            print(f"  [ZONES] Separator in cyan: Y={separator['y']} ({separator['y']/height:.1%})")
        print(f"  [ZONES] Footer line: Y={footer_y} ({footer_y/height:.1%})")

    return footer_y, method_info


def hybrid_detect_footer(binary_image, debug=False):
    """
    HYBRID DETECTION: Combines both strategies

    1. Try line detection (primary)
    2. Fall back to zone detection (secondary)
    """
    height, width = binary_image.shape

    if debug:
        print(f"  [HYBRID] Page size: {width}x{height}")

    # Find address first (needed for both strategies)
    address_start, address_end = find_address_region(binary_image)

    if debug:
        print(f"  [HYBRID] Address: Y={address_start}-{address_end} ({address_start/height:.1%}-{address_end/height:.1%})")

    # PRIMARY: Try line detection
    if debug:
        print(f"  [HYBRID] Trying PRIMARY strategy (line detection)...")

    line_y, line_info = detect_separator_line(binary_image, debug=debug)

    if line_y is not None:
        if debug:
            print(f"  [HYBRID] [OK] PRIMARY successful: Line at Y={line_y} ({line_y/height:.1%})")

        return line_y, {
            'strategy': 'primary',
            **line_info,
            'address_start': int(address_start),
            'address_end': int(address_end)
        }

    # SECONDARY: Fall back to zone detection
    if debug:
        print(f"  [HYBRID] PRIMARY failed, trying SECONDARY strategy (zone detection)...")

    zone_y, zone_info = detect_zones_strategy(binary_image, address_start, debug=debug)

    if zone_y is not None:
        if debug:
            print(f"  [HYBRID] [OK] SECONDARY successful: Footer at Y={zone_y} ({zone_y/height:.1%})")

        return zone_y, {
            'strategy': 'secondary',
            **zone_info,
            'address_start': int(address_start),
            'address_end': int(address_end)
        }

    # FALLBACK: Use 90% of page
    fallback_y = int(height * 0.90)

    if debug:
        print(f"  [HYBRID] [FAIL] Both strategies failed, using FALLBACK: Y={fallback_y} ({fallback_y/height:.1%})")

    return fallback_y, {
        'strategy': 'fallback',
        'method': 'fixed_percentage',
        'confidence': 'low',
        'footer_y': fallback_y,
        'address_start': int(address_start),
        'address_end': int(address_end)
    }


def visualize_hybrid_detection(pdf_path, page_num, output_dir):
    """Create visualization showing both strategies"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=300)
    page_image = np.array(images[0])

    gray = cv2.cvtColor(page_image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    print(f"\n{'='*80}")
    print(f"Processing: {pdf_path.name} - Page {page_num}")
    print('='*80)

    # Run hybrid detection
    footer_y, info = hybrid_detect_footer(binary, debug=True)

    # Create visualization
    vis_image = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    height, width = binary.shape

    # Draw vertical center line
    center_x = width // 2
    cv2.line(vis_image, (center_x, 0), (center_x, height), (200, 200, 200), 2)

    # Draw address region (light yellow)
    addr_start = info['address_start']
    addr_end = info['address_end']
    overlay = vis_image.copy()
    cv2.rectangle(overlay, (0, addr_start), (width, addr_end), (100, 200, 200), -1)
    cv2.addWeighted(overlay, 0.3, vis_image, 0.7, 0, vis_image)

    # Draw cyan zone if from secondary strategy
    if info['strategy'] == 'secondary' and 'cyan_zone' in info:
        cyan = info['cyan_zone']
        overlay = vis_image.copy()
        cv2.rectangle(overlay, (0, cyan['start']), (width, cyan['end']), (255, 255, 0), -1)  # Cyan
        cv2.addWeighted(overlay, 0.3, vis_image, 0.7, 0, vis_image)

        # Draw cyan borders
        cv2.line(vis_image, (0, cyan['start']), (width, cyan['start']), (255, 255, 0), 3)
        cv2.line(vis_image, (0, cyan['end']), (width, cyan['end']), (255, 255, 0), 3)

        # Label cyan zone
        cv2.putText(vis_image, f"CYAN ZONE ({cyan['start']/height:.1%}-{cyan['end']/height:.1%})",
                    (10, cyan['start'] + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

    # Draw footnote zone if exists
    if 'footnote_zone' in info:
        fn = info['footnote_zone']
        overlay = vis_image.copy()
        cv2.rectangle(overlay, (0, fn['start']), (width, fn['end']), (0, 255, 255), -1)  # Yellow
        cv2.addWeighted(overlay, 0.4, vis_image, 0.6, 0, vis_image)

        cv2.putText(vis_image, f"FOOTNOTE ({fn['start']/height:.1%}-{fn['end']/height:.1%})",
                    (10, fn['start'] + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 200), 2)

    # Draw footer line
    strategy_colors = {
        'primary': (0, 0, 255),      # Red for line detection
        'secondary': (0, 255, 0),    # Green for zone detection
        'fallback': (128, 128, 128)  # Gray for fallback
    }
    color = strategy_colors.get(info['strategy'], (255, 0, 0))
    cv2.line(vis_image, (0, footer_y), (width, footer_y), color, 4)

    # Label footer line
    strategy_names = {
        'primary': 'LINE DETECTION',
        'secondary': 'ZONE DETECTION',
        'fallback': 'FALLBACK'
    }
    label = f"{strategy_names[info['strategy']]}: {footer_y/height:.1%}"
    if 'confidence' in info:
        label += f" ({info['confidence']} conf)"

    cv2.putText(vis_image, label, (10, footer_y - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)

    # Save visualization
    filename = f"{pdf_path.stem}_page{page_num}_hybrid.png"
    output_path = output_dir / filename
    cv2.imwrite(str(output_path), vis_image)

    print(f"[+] Saved: {filename}")
    print(f"    Strategy: {info['strategy']}")
    print(f"    Footer Y: {footer_y} ({footer_y/height:.1%})")

    return footer_y, info


def test_hybrid_on_pdf(pdf_filename, output_dir="hybrid_test"):
    """Test hybrid detector on all pages of one PDF"""
    pdf_path = Path(f"data/raw/scanned/{pdf_filename}")

    if not pdf_path.exists():
        print(f"❌ PDF not found: {pdf_path}")
        return

    print(f"\n{'='*80}")
    print(f"HYBRID TEST: {pdf_filename}")
    print('='*80)

    images = convert_from_path(pdf_path, dpi=72)
    num_pages = len(images)

    results = []
    for page_num in range(1, num_pages + 1):
        footer_y, info = visualize_hybrid_detection(pdf_path, page_num, output_dir)
        results.append({
            'page': page_num,
            'strategy': info['strategy'],
            'footer_y': footer_y,
            'footer_y_pct': footer_y / info['address_start'] if info['address_start'] > 0 else 0,
            'info': info
        })

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print('='*80)
    print(f"Total pages: {len(results)}")
    print(f"Primary (line) used: {sum(1 for r in results if r['strategy'] == 'primary')}")
    print(f"Secondary (zones) used: {sum(1 for r in results if r['strategy'] == 'secondary')}")
    print(f"Fallback used: {sum(1 for r in results if r['strategy'] == 'fallback')}")

    # Save results to JSON
    output_path = Path(output_dir) / f"{pdf_path.stem}_results.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_path}")
    print(f"Visualizations saved to: {output_dir}/")


if __name__ == "__main__":
    # Test on the reference PDFs
    test_hybrid_on_pdf("Informe_CF_N_001-2016.pdf")
    test_hybrid_on_pdf("INFORME_N_002-2017-CF.pdf")
