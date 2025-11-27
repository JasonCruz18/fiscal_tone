"""Compare footer structure between page 1 and pages 2-3 to understand differences"""

import cv2
import numpy as np
from pdf2image import convert_from_path
from pathlib import Path

PDF_PATH = "data/raw/scanned/INFORME_N_002-2017-CF.pdf"

def extract_footer_region(page_num):
    """Extract and save footer region for a page"""
    images = convert_from_path(PDF_PATH, first_page=page_num, last_page=page_num, dpi=300)
    page_image = np.array(images[0])

    # Binarize
    gray = cv2.cvtColor(page_image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    height, width = binary.shape

    # Extract footer region (85-100% to see the footer clearly)
    footer_start = int(height * 0.85)
    footer_region = binary[footer_start:, :]

    output_dir = Path("footer_comparison")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / f"page{page_num}_footer.png"
    cv2.imwrite(str(output_path), footer_region)

    print(f"Page {page_num}: {width}x{height}, footer region: {footer_region.shape}")

    # Analyze horizontal line density in bottom 20% of page
    bottom_start = int(height * 0.80)
    bottom_region = binary[bottom_start:, :]

    # Count horizontal lines at each Y position
    for y_pct in [85, 88, 90, 92, 94, 96]:
        y_global = int(height * y_pct / 100)
        y_local = y_global - footer_start

        if 0 <= y_local < footer_region.shape[0]:
            row = footer_region[y_local, :]
            black_pixels = np.sum(row == 0)
            black_ratio = black_pixels / width

            print(f"  At {y_pct}%: {black_pixels} black pixels ({black_ratio:.1%})")

    return binary, footer_region

print("="*80)
print("COMPARING FOOTER STRUCTURES")
print("="*80)

for page_num in [1, 2, 3]:
    print(f"\n--- Page {page_num} ---")
    full_page, footer = extract_footer_region(page_num)

print(f"\nFooter regions saved to footer_comparison/")
print("\nUser said pages 2 and 3 have GOOD footer line detection.")
print("Let's compare their structure with page 1.")
