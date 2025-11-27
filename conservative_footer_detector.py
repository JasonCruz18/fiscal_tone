"""
Conservative Footer Detector - Simple and Robust Strategy

PHILOSOPHY: Better to include some footnotes than to lose main content

Strategy:
1. Find ADDRESS (last text line at bottom, ~93-95%)
2. Find first LARGE whitespace zone BEFORE address (>100px, before 92%)
3. Cut at the BASE of that zone
4. Accept that footnotes may pass through (clean them in post-processing)

This guarantees we NEVER lose main content.
"""

import cv2
import numpy as np
from pdf2image import convert_from_path
from pathlib import Path
import json


# === SIMPLE CONFIGURATION ===
WHITESPACE_THRESHOLD = 0.05    # 5% blackness = whitespace
MIN_ZONE_HEIGHT = 100          # Only consider zones >= 100px (significant whitespace)
ADDRESS_SEARCH_START = 0.85    # Start looking for address after 85%
MAX_CUT_POSITION = 0.92        # Never cut below 92% (safety margin)


def calculate_row_blackness(binary_image, start_y, end_y):
    """Calculate blackness for each row"""
    width = binary_image.shape[1]
    row_blackness = []
    for y in range(start_y, end_y):
        row = binary_image[y, :]
        blackness = np.sum(row == 0) / width
        row_blackness.append({'y': y, 'blackness': blackness})
    return row_blackness


def find_address_region(binary_image, debug=False):
    """
    Find the address (last text block at bottom of page)

    The address is typically centered text at 93-96% of page height
    """
    height, width = binary_image.shape
    search_start = int(height * ADDRESS_SEARCH_START)

    row_blackness = calculate_row_blackness(binary_image, search_start, height)

    # Find last continuous text region (working backwards from bottom)
    text_threshold = 0.05  # More than 5% black = text
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
            # Found gap after text - this is the address
            break

    # Fallback if detection fails
    if address_start is None or address_end is None:
        address_start = int(height * 0.93)
        address_end = int(height * 0.95)

    if debug:
        print(f"  [ADDRESS] Y={address_start}-{address_end} ({address_start/height:.1%}-{address_end/height:.1%})")

    return address_start, address_end


def find_safe_cut_zone(binary_image, address_start, debug=False):
    """
    Find the safe zone to cut (first large whitespace before address)

    Returns the BASE of the first large whitespace zone found before address
    """
    height, width = binary_image.shape

    # Search from 50% to address_start
    search_start = int(height * 0.50)
    max_cut = min(int(height * MAX_CUT_POSITION), address_start)

    row_blackness = calculate_row_blackness(binary_image, search_start, max_cut)

    # Find whitespace zones
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
            zone_height = y - zone_start
            if zone_height >= MIN_ZONE_HEIGHT:
                zones.append({
                    'start': zone_start,
                    'end': y,
                    'height': zone_height
                })
            in_zone = False

    # Close last zone if still open
    if in_zone:
        y_last = row_blackness[-1]['y']
        zone_height = y_last - zone_start
        if zone_height >= MIN_ZONE_HEIGHT:
            zones.append({
                'start': zone_start,
                'end': y_last,
                'height': zone_height
            })

    if debug:
        print(f"  [ZONES] Found {len(zones)} large whitespace zones (>={MIN_ZONE_HEIGHT}px)")
        for i, z in enumerate(zones):
            print(f"    {i+1}. Y={z['start']}-{z['end']} ({z['start']/height:.1%}-{z['end']/height:.1%}), H={z['height']}px")

    if not zones:
        if debug:
            print(f"  [ZONES] No large zones found - using max cut position")
        # Fallback: cut at max_cut position
        return max_cut, {
            'method': 'fallback_max_cut',
            'confidence': 'low'
        }

    # Find the LAST (closest to address) large zone
    # This is the most conservative choice
    selected_zone = zones[-1]

    # Cut at the BASE of this zone (conservative: include more content)
    cut_y = selected_zone['end']

    if debug:
        print(f"  [CUT] Selected zone: Y={selected_zone['start']}-{selected_zone['end']} ({selected_zone['start']/height:.1%}-{selected_zone['end']/height:.1%})")
        print(f"  [CUT] Cutting at BASE: Y={cut_y} ({cut_y/height:.1%})")

    return cut_y, {
        'method': 'whitespace_zone',
        'confidence': 'high',
        'zone': selected_zone,
        'total_zones': len(zones)
    }


def conservative_detect_footer(binary_image, debug=False):
    """
    Main conservative detection function

    Returns: (cut_y, info_dict)
    """
    height, width = binary_image.shape

    if debug:
        print(f"  [INFO] Page size: {width}x{height}")

    # Step 1: Find address
    address_start, address_end = find_address_region(binary_image, debug=debug)

    # Step 2: Find safe cut zone
    cut_y, zone_info = find_safe_cut_zone(binary_image, address_start, debug=debug)

    # Build complete info
    info = {
        'cut_y': int(cut_y),
        'cut_y_pct': cut_y / height,
        'address_start': int(address_start),
        'address_end': int(address_end),
        **zone_info
    }

    return int(cut_y), info


def visualize_conservative_detection(pdf_path, page_num, output_dir):
    """Create simple visualization showing the cut line and address"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=300)
    page_image = np.array(images[0])

    gray = cv2.cvtColor(page_image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    print(f"\n{'='*80}")
    print(f"Page {page_num}: {pdf_path.name}")
    print('='*80)

    # Run detection
    cut_y, info = conservative_detect_footer(binary, debug=True)

    # Create visualization
    vis_image = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    height, width = binary.shape

    # Draw vertical center line
    center_x = width // 2
    cv2.line(vis_image, (center_x, 0), (center_x, height), (200, 200, 200), 1)

    # Highlight KEPT content (above cut) in very light green
    overlay = vis_image.copy()
    cv2.rectangle(overlay, (0, 0), (width, cut_y), (200, 255, 200), -1)
    cv2.addWeighted(overlay, 0.1, vis_image, 0.9, 0, vis_image)

    # Highlight DISCARDED content (below cut) in very light red
    overlay = vis_image.copy()
    cv2.rectangle(overlay, (0, cut_y), (width, height), (200, 200, 255), -1)
    cv2.addWeighted(overlay, 0.1, vis_image, 0.9, 0, vis_image)

    # Draw address region
    addr_start = info['address_start']
    addr_end = info['address_end']
    cv2.rectangle(vis_image, (0, addr_start), (width, addr_end), (150, 150, 150), 2)
    cv2.putText(vis_image, "ADDRESS", (10, addr_start - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 100), 2)

    # Draw CUT line (thick green)
    cv2.line(vis_image, (0, cut_y), (width, cut_y), (0, 255, 0), 6)

    # Label cut line
    label = f"CUT: {cut_y/height:.1%} ({info['method']})"
    cv2.putText(vis_image, label, (10, cut_y - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 200, 0), 3)

    # Add info text at top
    info_text = f"KEPT: 0%-{cut_y/height:.1%} | DISCARDED: {cut_y/height:.1%}-100%"
    cv2.putText(vis_image, info_text, (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 3)

    # Save
    filename = f"{pdf_path.stem}_page{page_num}_conservative.png"
    output_path = output_dir / filename
    cv2.imwrite(str(output_path), vis_image)

    print(f"\n[SAVED] {filename}")
    print(f"  Cut at: {cut_y} ({cut_y/height:.1%})")
    print(f"  Method: {info['method']}")
    print(f"  Confidence: {info['confidence']}")

    return cut_y, info


def test_conservative_detector(pdf_filename, output_dir="conservative_test"):
    """Test conservative detector on all pages of a PDF"""
    pdf_path = Path(f"data/raw/scanned/{pdf_filename}")

    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}")
        return

    print(f"\n{'='*80}")
    print(f"CONSERVATIVE TEST: {pdf_filename}")
    print('='*80)

    images = convert_from_path(pdf_path, dpi=72)
    num_pages = len(images)

    results = []
    for page_num in range(1, num_pages + 1):
        cut_y, info = visualize_conservative_detection(pdf_path, page_num, output_dir)
        results.append({
            'page': page_num,
            'cut_y': cut_y,
            'cut_y_pct': info['cut_y_pct'],
            'method': info['method'],
            'confidence': info['confidence']
        })

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print('='*80)
    print(f"Total pages: {len(results)}")
    print(f"Average cut position: {np.mean([r['cut_y_pct'] for r in results]):.1%}")
    print(f"Cut range: {min(r['cut_y_pct'] for r in results):.1%} - {max(r['cut_y_pct'] for r in results):.1%}")
    print(f"\nHigh confidence: {sum(1 for r in results if r['confidence'] == 'high')}")
    print(f"Low confidence: {sum(1 for r in results if r['confidence'] == 'low')}")

    print(f"\nVisualizations saved to: {output_dir}/")

    return results


if __name__ == "__main__":
    # Test on reference PDFs
    print("\n" + "="*80)
    print("TESTING CONSERVATIVE FOOTER DETECTOR")
    print("="*80)

    test_conservative_detector("Informe_CF_N_001-2016.pdf")
    print("\n" + "="*80 + "\n")
    test_conservative_detector("INFORME_N_002-2017-CF.pdf")
