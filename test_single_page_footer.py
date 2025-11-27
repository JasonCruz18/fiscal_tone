"""Quick test on single problematic page to debug footer detection"""

import cv2
import numpy as np
from pdf2image import convert_from_path
from pathlib import Path

# Test parameters
PDF_PATH = "data/raw/scanned/INFORME_N_002-2017-CF.pdf"
PAGE_NUM = 1  # The page where we saw false positive at "habiles siguientes a"

FOOTER_SEARCH_START = 0.75
FOOTER_SEARCH_END = 0.95
LINE_MIN_LENGTH = 0.05  # Try 5% instead of 10%
LINE_MAX_LENGTH = 0.35

# Sample parameters
SAMPLE_DISTANCE = 50
SAMPLE_WIDTH = 30

def visualize_line_environment(binary, line_info, output_path):
    """Visualize what's around a detected line"""
    height, width = binary.shape
    y = line_info['y']
    x1 = line_info['x1']
    x2 = line_info['x2']

    # Create visualization
    vis = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    # Draw the line in blue
    cv2.line(vis, (x1, y), (x2, y), (255, 0, 0), 3)

    # Draw sampling regions
    # Left region
    left_x_start = max(0, x1 - SAMPLE_DISTANCE - SAMPLE_WIDTH)
    left_x_end = max(0, x1 - SAMPLE_DISTANCE)
    cv2.rectangle(vis, (left_x_start, y-5), (left_x_end, y+5), (0, 255, 0), 2)

    # Right region
    right_x_start = min(width, x2 + SAMPLE_DISTANCE)
    right_x_end = min(width, x2 + SAMPLE_DISTANCE + SAMPLE_WIDTH)
    cv2.rectangle(vis, (right_x_start, y-5), (right_x_end, y+5), (0, 255, 0), 2)

    # Save
    cv2.imwrite(output_path, vis)

def detect_lines(binary_image):
    """Detect horizontal lines"""
    height, width = binary_image.shape

    y_start = int(height * FOOTER_SEARCH_START)
    y_end = int(height * FOOTER_SEARCH_END)
    search_region = binary_image[y_start:y_end, :]

    inverted = cv2.bitwise_not(search_region)

    lines = cv2.HoughLinesP(
        inverted,
        rho=1,
        theta=np.pi/180,
        threshold=50,
        minLineLength=int(width * LINE_MIN_LENGTH),
        maxLineGap=15
    )

    if lines is None:
        return []

    horizontal_lines = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if abs(y2 - y1) <= 3:
            adjusted_y = y_start + y1
            line_length = abs(x2 - x1)
            if width * LINE_MIN_LENGTH <= line_length <= width * LINE_MAX_LENGTH:
                horizontal_lines.append({
                    'x1': min(x1, x2),
                    'x2': max(x1, x2),
                    'y': adjusted_y,
                    'length': line_length
                })

    horizontal_lines.sort(key=lambda l: l['y'], reverse=True)
    return horizontal_lines

def main():
    print(f"Testing: {PDF_PATH} - Page {PAGE_NUM}")

    # Convert to image
    images = convert_from_path(PDF_PATH, first_page=PAGE_NUM, last_page=PAGE_NUM, dpi=300)
    page_image = np.array(images[0])

    # Binarize
    gray = cv2.cvtColor(page_image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    height, width = binary.shape
    print(f"Page size: {width}x{height}")

    # Detect lines
    lines = detect_lines(binary)
    print(f"\nFound {len(lines)} candidate lines")

    # Create output directory
    output_dir = Path("footer_debug_single")
    output_dir.mkdir(exist_ok=True)

    # Analyze ALL lines to find the true footer separator
    for idx, line in enumerate(lines):
        print(f"\n[Line {idx+1}] Y={line['y']} ({line['y']/height:.1%}), Length={line['length']}px")

        # Sample left and right
        y = line['y']
        x1 = line['x1']
        x2 = line['x2']

        left_x_start = max(0, x1 - SAMPLE_DISTANCE - SAMPLE_WIDTH)
        left_x_end = max(0, x1 - SAMPLE_DISTANCE)
        right_x_start = min(width, x2 + SAMPLE_DISTANCE)
        right_x_end = min(width, x2 + SAMPLE_DISTANCE + SAMPLE_WIDTH)

        # Sample SINGLE ROW
        left_sample = binary[y, left_x_start:left_x_end]
        right_sample = binary[y, right_x_start:right_x_end]

        left_black = np.sum(left_sample == 0) / left_sample.size if left_sample.size > 0 else 0
        right_black = np.sum(right_sample == 0) / right_sample.size if right_sample.size > 0 else 0

        print(f"  Left blackness: {left_black:.3f}")
        print(f"  Right blackness: {right_black:.3f}")
        print(f"  Horizontally isolated: {left_black < 0.10 and right_black < 0.10}")

        # Visualize
        viz_path = str(output_dir / f"line_{idx+1}_y{line['y']}.png")
        visualize_line_environment(binary, line, viz_path)
        print(f"  Saved: {viz_path}")

if __name__ == "__main__":
    main()
