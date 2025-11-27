"""
Analyze patterns to distinguish pages WITH footnotes vs WITHOUT footnotes

Strategy:
1. Find 1st largest zone from bottom (final margin - always discard)
2. Find address (last text element before 1st zone)
3. Find 2nd zone (whitespace above address)
4. Determine if footnote exists
5. If YES → cyan = 3rd largest zone from bottom
   If NO → cyan = 2nd zone
"""

import cv2
import numpy as np
from pdf2image import convert_from_path
from pathlib import Path
import matplotlib.pyplot as plt

PAGE_MID = 0.50
WHITESPACE_THRESHOLD = 0.05
MIN_ZONE_HEIGHT = 20


def calculate_row_blackness(binary_image, start_y, end_y):
    width = binary_image.shape[1]
    row_blackness = []
    for y in range(start_y, end_y):
        row = binary_image[y, :]
        blackness = np.sum(row == 0) / width
        row_blackness.append({'y': y, 'blackness': blackness})
    return row_blackness


def find_all_whitespace_zones(binary_image):
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


def find_address_region(binary_image, zone_1_start):
    """
    Find the address (last text element) which is just before zone 1.

    The address is the last group of text rows before the final margin.
    Returns: (address_start_y, address_end_y)
    """
    height, width = binary_image.shape

    # Start from just before zone 1 and go upward
    search_end = zone_1_start
    search_start = max(int(height * 0.80), zone_1_start - 200)  # Search up to 200px above

    # Find last text block
    row_blackness = []
    for y in range(search_start, search_end):
        row = binary_image[y, :]
        blackness = np.sum(row == 0) / width
        row_blackness.append({'y': y, 'blackness': blackness})

    # Find last continuous text region (working backwards)
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
            # Found gap after text - stop
            break

    return address_start, address_end


def find_zone_above_address(zones, address_start):
    """
    Find the 2nd zone - the whitespace zone just above the address.
    """
    # Find zone that ends near or at address_start
    for zone in zones:
        # Zone should end around where address starts
        if abs(zone['end'] - address_start) < 50:  # Within 50px
            return zone

    # Fallback: find zone closest to address_start
    closest = min(zones, key=lambda z: abs(z['end'] - address_start))
    return closest


def analyze_page(pdf_path, page_num, has_footnote_label=None):
    """
    Analyze a page to understand the zone structure.

    has_footnote_label: True/False/None (user label for validation)
    """
    print(f"\n{'='*80}")
    print(f"PAGE: {pdf_path.name} - Page {page_num}")
    if has_footnote_label is not None:
        print(f"User label: {'HAS FOOTNOTE' if has_footnote_label else 'NO FOOTNOTE'}")
    print('='*80)

    images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=300)
    page_image = np.array(images[0])

    gray = cv2.cvtColor(page_image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    height, width = binary.shape

    # Step 1: Find all zones sorted by height
    zones = find_all_whitespace_zones(binary)

    print(f"\nAll {len(zones)} zones sorted by HEIGHT:")
    for i, zone in enumerate(zones, 1):
        pct_start = zone['start'] / height * 100
        pct_end = zone['end'] / height * 100
        print(f"  {i}. Y={zone['start']:4d}-{zone['end']:4d} ({pct_start:5.1f}%-{pct_end:5.1f}%), Height={zone['height']:3d}px")

    # Step 2: Identify 1st largest zone (final margin)
    zone_1_largest = zones[0]
    print(f"\n[1st LARGEST ZONE - FINAL MARGIN]")
    print(f"  Y={zone_1_largest['start']}-{zone_1_largest['end']} "
          f"({zone_1_largest['start']/height:.1%}-{zone_1_largest['end']/height:.1%}), "
          f"Height={zone_1_largest['height']}px")

    # Step 3: Find address
    addr_start, addr_end = find_address_region(binary, zone_1_largest['start'])
    if addr_start and addr_end:
        print(f"\n[ADDRESS REGION]")
        print(f"  Y={addr_start}-{addr_end} ({addr_start/height:.1%}-{addr_end/height:.1%}), "
              f"Height={addr_end - addr_start}px")
    else:
        print(f"\n[WARNING] Could not find address region")
        addr_start = zone_1_largest['start'] - 50

    # Step 4: Find 2nd zone (above address)
    zone_2 = find_zone_above_address(zones, addr_start)
    print(f"\n[2nd ZONE - ABOVE ADDRESS]")
    print(f"  Y={zone_2['start']}-{zone_2['end']} "
          f"({zone_2['start']/height:.1%}-{zone_2['end']/height:.1%}), "
          f"Height={zone_2['height']}px")

    # Step 5: Find 3rd largest zone
    if len(zones) >= 3:
        # Find 3rd largest (zones already sorted by height)
        zone_3_largest = zones[2]
        print(f"\n[3rd LARGEST ZONE]")
        print(f"  Y={zone_3_largest['start']}-{zone_3_largest['end']} "
              f"({zone_3_largest['start']/height:.1%}-{zone_3_largest['end']/height:.1%}), "
              f"Height={zone_3_largest['height']}px")
    else:
        zone_3_largest = None
        print(f"\n[WARNING] Less than 3 zones found")

    # Step 6: Analyze characteristics to detect footnote
    print(f"\n{'='*40}")
    print("FOOTNOTE DETECTION ANALYSIS")
    print('='*40)

    # Characteristic 1: Is there text between zone_2 and zone_1?
    if addr_start and addr_end:
        text_height = addr_end - addr_start
        gap_below_addr = zone_1_largest['start'] - addr_end
        gap_above_addr = addr_start - zone_2['end']

        print(f"\nAddress characteristics:")
        print(f"  Text height: {text_height}px")
        print(f"  Gap below address: {gap_below_addr}px")
        print(f"  Gap above address: {gap_above_addr}px")

    # Characteristic 2: Check region between zone_2 and address for footnote text
    if addr_start and zone_2['end'] < addr_start:
        footnote_region_start = zone_2['end']
        footnote_region_end = addr_start
        footnote_region_height = footnote_region_end - footnote_region_start

        # Calculate blackness in this region
        footnote_region = binary[footnote_region_start:footnote_region_end, :]
        footnote_blackness = np.sum(footnote_region == 0) / footnote_region.size

        print(f"\nRegion between zone_2 and address:")
        print(f"  Y={footnote_region_start}-{footnote_region_end} "
              f"({footnote_region_start/height:.1%}-{footnote_region_end/height:.1%})")
        print(f"  Height: {footnote_region_height}px")
        print(f"  Blackness: {footnote_blackness:.2%}")

        if footnote_blackness > 0.02:  # More than 2% black
            print(f"  -> Likely contains FOOTNOTE TEXT (blackness > 2%)")
        else:
            print(f"  -> Likely NO footnote (low blackness)")

    # Characteristic 3: Zone size comparison
    if zone_3_largest:
        print(f"\nZone size comparison:")
        print(f"  2nd zone: {zone_2['height']}px")
        print(f"  3rd largest zone: {zone_3_largest['height']}px")
        print(f"  Ratio (3rd/2nd): {zone_3_largest['height'] / zone_2['height']:.2f}")

        if zone_3_largest['height'] > zone_2['height'] * 1.5:
            print(f"  -> 3rd largest is MUCH bigger (>1.5x) -> Likely HAS FOOTNOTE")
        else:
            print(f"  -> Zones similar size -> Likely NO FOOTNOTE")

    # Summary
    print(f"\n{'='*40}")
    print("RECOMMENDATION")
    print('='*40)

    if has_footnote_label:
        print(f"User says: HAS FOOTNOTE -> Use 3rd largest zone")
        print(f"  Cyan zone: Y={zone_3_largest['start']}-{zone_3_largest['end']} "
              f"({zone_3_largest['start']/height:.1%}-{zone_3_largest['end']/height:.1%})")
    else:
        print(f"User says: NO FOOTNOTE -> Use 2nd zone")
        print(f"  Cyan zone: Y={zone_2['start']}-{zone_2['end']} "
              f"({zone_2['start']/height:.1%}-{zone_2['end']/height:.1%})")


# Test on specific pages
pdf1 = Path("data/raw/scanned/Informe_CF_N_001-2016.pdf")

print("\n" + "="*80)
print("ANALYZING PAGES TO UNDERSTAND FOOTNOTE PATTERNS")
print("="*80)

# Page 1 - user says HAS footnote
analyze_page(pdf1, 1, has_footnote_label=True)

# Page 2 - user says NO footnote
analyze_page(pdf1, 2, has_footnote_label=False)

# Let's also check a few more pages to find patterns
pdf2 = Path("data/raw/scanned/INFORME_N_002-2017-CF.pdf")
print("\n\nLet's check INFORME_N_002-2017-CF for comparison:")
analyze_page(pdf2, 1, has_footnote_label=True)  # Page 1 usually has footnotes
analyze_page(pdf2, 2, has_footnote_label=True)
