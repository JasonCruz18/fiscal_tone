"""Inspect specific pages mentioned by user to understand zone patterns"""

import cv2
import numpy as np
from pdf2image import convert_from_path
from pathlib import Path

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

    # Sort from BOTTOM to TOP
    zones.sort(key=lambda z: z['end'], reverse=True)

    return zones

def inspect_page(pdf_path, page_num):
    print(f"\n{'='*80}")
    print(f"INSPECTING: {pdf_path.name} - Page {page_num}")
    print('='*80)

    images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=300)
    page_image = np.array(images[0])

    gray = cv2.cvtColor(page_image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    height, width = binary.shape
    print(f"Page size: {width}x{height}")

    zones = find_all_whitespace_zones(binary)

    print(f"\nFound {len(zones)} whitespace zones (from BOTTOM to TOP):")
    for i, zone in enumerate(zones, 1):
        pct_start = zone['start'] / height * 100
        pct_end = zone['end'] / height * 100
        print(f"  Zone {i}: Y={zone['start']:4d}-{zone['end']:4d} ({pct_start:5.1f}%-{pct_end:5.1f}%), Height={zone['height']:3d}px")

    if len(zones) >= 3:
        print(f"\nTop 3 zones from bottom:")
        print(f"  1st (discard): {zones[0]['height']}px")
        print(f"  2nd: {zones[1]['height']}px")
        print(f"  3rd: {zones[2]['height']}px")

        if zones[2]['height'] > zones[1]['height'] and zones[2]['height'] > zones[0]['height']:
            print(f"\n  -> 3rd is LARGEST -> Footnote exists -> Cyan = 3rd zone")
        else:
            print(f"\n  -> 3rd is NOT largest -> No footnote -> Cyan = 2nd zone")

# Test the two specific examples
pdf1 = Path("data/raw/scanned/Informe_CF_N_001-2016.pdf")
inspect_page(pdf1, 1)
inspect_page(pdf1, 2)
