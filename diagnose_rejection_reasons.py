"""
Diagnostic script to understand why footer lines are being rejected.
Tests each filter stage separately to identify the bottleneck.
"""

import numpy as np
import cv2
from PIL import Image
from pdf2image import convert_from_path
import os


def binarize_image(image: Image.Image) -> np.ndarray:
    """Binarize image using Otsu's method."""
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary


def diagnose_filters(pdf_path, page_num):
    """
    Diagnoses why lines are rejected by testing each filter stage.
    """
    print(f"\n{'='*80}")
    print(f"DIAGNOSING: {os.path.basename(pdf_path)} - Page {page_num}")
    print(f"{'='*80}\n")

    images = convert_from_path(pdf_path, dpi=300)
    image = images[page_num - 1]

    height = image.height
    width = image.width

    binary = binarize_image(image)

    # Search region
    search_start_y = int(height * 0.75)
    search_end_y = int(height * 0.95)
    search_region = binary[search_start_y:search_end_y, :]
    inverted = cv2.bitwise_not(search_region)

    # Detect all lines
    min_line_length_px = int(width * 0.10)

    lines = cv2.HoughLinesP(
        inverted, rho=1, theta=np.pi/180, threshold=50,
        minLineLength=min_line_length_px, maxLineGap=10
    )

    if lines is None:
        print("No lines detected by Hough transform")
        return

    print(f"Total lines detected: {len(lines)}\n")

    # Test each line through all filters
    stage_stats = {
        'total': len(lines),
        'horizontal': 0,
        'length_ok': 0,
        'left_edge_ok': 0,
        'isolated_ok': 0
    }

    rejection_reasons = {
        'not_horizontal': [],
        'wrong_length': [],
        'not_from_left': [],
        'not_isolated': []
    }

    for idx, line in enumerate(lines):
        x1, y1, x2, y2 = line[0]
        actual_y = y1 + search_start_y
        line_length = abs(x2 - x1)
        line_length_ratio = line_length / width
        left_x = min(x1, x2)

        # Filter 1: Horizontal
        if abs(y2 - y1) > 5:
            rejection_reasons['not_horizontal'].append({
                'idx': idx, 'y_diff': abs(y2-y1), 'y': actual_y,
                'length_ratio': line_length_ratio, 'left_x': left_x
            })
            continue
        stage_stats['horizontal'] += 1

        # Filter 2: Length
        if not (0.10 <= line_length_ratio <= 0.40):
            rejection_reasons['wrong_length'].append({
                'idx': idx, 'length_ratio': line_length_ratio, 'y': actual_y, 'left_x': left_x
            })
            continue
        stage_stats['length_ok'] += 1

        # Filter 3: Left edge
        LEFT_EDGE_TOLERANCE = 50
        if left_x > LEFT_EDGE_TOLERANCE:
            rejection_reasons['not_from_left'].append({
                'idx': idx, 'left_x': left_x, 'y': actual_y,
                'length_ratio': line_length_ratio, 'y_ratio': actual_y/height
            })
            continue
        stage_stats['left_edge_ok'] += 1

        # Filter 4: Isolation
        ISOLATION_CHECK_HEIGHT = 30
        ISOLATION_MIN_WHITESPACE = 0.85

        x_min = min(x1, x2)
        x_max = max(x1, x2)

        # Check above
        y_above_start = max(0, actual_y - ISOLATION_CHECK_HEIGHT)
        y_above_end = actual_y
        region_above = binary[y_above_start:y_above_end, x_min:x_max]

        # Check below
        y_below_start = actual_y + 1
        y_below_end = min(height, actual_y + ISOLATION_CHECK_HEIGHT)
        region_below = binary[y_below_start:y_below_end, x_min:x_max]

        whitespace_above = np.sum(region_above == 255) / region_above.size if region_above.size > 0 else 1.0
        whitespace_below = np.sum(region_below == 255) / region_below.size if region_below.size > 0 else 1.0

        is_isolated = whitespace_above >= ISOLATION_MIN_WHITESPACE and whitespace_below >= ISOLATION_MIN_WHITESPACE

        if not is_isolated:
            rejection_reasons['not_isolated'].append({
                'idx': idx, 'left_x': left_x, 'y': actual_y, 'y_ratio': actual_y/height,
                'length_ratio': line_length_ratio,
                'whitespace_above': whitespace_above,
                'whitespace_below': whitespace_below
            })
            continue
        stage_stats['isolated_ok'] += 1

    # Print funnel statistics
    print("FILTER FUNNEL:")
    print(f"  Total detected:        {stage_stats['total']}")
    print(f"  -> Horizontal:         {stage_stats['horizontal']} ({stage_stats['horizontal']/stage_stats['total']*100:.1f}%)")
    print(f"  -> Length 10-40%:      {stage_stats['length_ok']} ({stage_stats['length_ok']/stage_stats['total']*100:.1f}%)")
    print(f"  -> From left edge:     {stage_stats['left_edge_ok']} ({stage_stats['left_edge_ok']/stage_stats['total']*100:.1f}%)")
    print(f"  -> Isolated:           {stage_stats['isolated_ok']} ({stage_stats['isolated_ok']/stage_stats['total']*100:.1f}%)")

    # Detailed rejection analysis
    print(f"\n{'='*80}")
    print("REJECTION DETAILS:")
    print(f"{'='*80}\n")

    # Not from left edge
    if rejection_reasons['not_from_left']:
        print(f"NOT FROM LEFT EDGE: {len(rejection_reasons['not_from_left'])} lines")
        print("(These passed horizontal and length filters but start too far right)")
        for r in rejection_reasons['not_from_left'][:5]:
            print(f"  Line at y={r['y']}px ({r['y_ratio']:.1%}), left_x={r['left_x']}px, length={r['length_ratio']:.1%}")
        if len(rejection_reasons['not_from_left']) > 5:
            print(f"  ... and {len(rejection_reasons['not_from_left'])-5} more")

    # Not isolated
    if rejection_reasons['not_isolated']:
        print(f"\nNOT ISOLATED: {len(rejection_reasons['not_isolated'])} lines")
        print("(These passed all filters except isolation check)")
        for r in rejection_reasons['not_isolated'][:5]:
            print(f"  Line at y={r['y']}px ({r['y_ratio']:.1%}), left_x={r['left_x']}px")
            print(f"    Whitespace above: {r['whitespace_above']:.2%}, below: {r['whitespace_below']:.2%}")
        if len(rejection_reasons['not_isolated']) > 5:
            print(f"  ... and {len(rejection_reasons['not_isolated'])-5} more")

    # Summary
    print(f"\n{'='*80}")
    print("BOTTLENECK ANALYSIS:")
    print(f"{'='*80}\n")

    total = stage_stats['total']
    horizontal = stage_stats['horizontal']
    length_ok = stage_stats['length_ok']
    left_ok = stage_stats['left_edge_ok']
    isolated_ok = stage_stats['isolated_ok']

    lost_at_horizontal = total - horizontal
    lost_at_length = horizontal - length_ok
    lost_at_left_edge = length_ok - left_ok
    lost_at_isolation = left_ok - isolated_ok

    print(f"Lost at horizontal filter:   {lost_at_horizontal} ({lost_at_horizontal/total*100:.1f}%)")
    print(f"Lost at length filter:       {lost_at_length} ({lost_at_length/total*100:.1f}%)")
    print(f"Lost at left-edge filter:    {lost_at_left_edge} ({lost_at_left_edge/total*100:.1f}%) <- BOTTLENECK" if lost_at_left_edge == max(lost_at_horizontal, lost_at_length, lost_at_left_edge, lost_at_isolation) else f"Lost at left-edge filter:    {lost_at_left_edge} ({lost_at_left_edge/total*100:.1f}%)")
    print(f"Lost at isolation filter:    {lost_at_isolation} ({lost_at_isolation/total*100:.1f}%) <- BOTTLENECK" if lost_at_isolation == max(lost_at_horizontal, lost_at_length, lost_at_left_edge, lost_at_isolation) else f"Lost at isolation filter:    {lost_at_isolation} ({lost_at_isolation/total*100:.1f}%)")


if __name__ == "__main__":
    # Test on the "perfect" cases user mentioned
    test_cases = [
        ("data/raw/scanned/INFORME_N_002-2017-CF.pdf", 2),  # Perfect case
        ("data/raw/scanned/INFORME_N_002-2017-CF.pdf", 3),  # Perfect case
        ("data/raw/scanned/Informe_CF_N_001-2016.pdf", 1),  # False positive case
    ]

    for pdf_path, page_num in test_cases:
        if os.path.exists(pdf_path):
            diagnose_filters(pdf_path, page_num)
