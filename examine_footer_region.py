"""Examine the footer region visually to understand its structure"""

import cv2
import numpy as np
from pdf2image import convert_from_path
from pathlib import Path

PDF_PATH = "data/raw/scanned/INFORME_N_002-2017-CF.pdf"
PAGE_NUM = 1

# Convert to image
images = convert_from_path(PDF_PATH, first_page=PAGE_NUM, last_page=PAGE_NUM, dpi=300)
page_image = np.array(images[0])

# Binarize
gray = cv2.cvtColor(page_image, cv2.COLOR_RGB2GRAY)
_, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

height, width = binary.shape
print(f"Page size: {width}x{height}")

# Extract footer region (75-100% of page)
footer_start = int(height * 0.75)
footer_region = binary[footer_start:, :]

print(f"Footer region: {footer_region.shape}")

# Save for inspection
output_dir = Path("footer_region_inspection")
output_dir.mkdir(exist_ok=True)

cv2.imwrite(str(output_dir / "full_page.png"), binary)
cv2.imwrite(str(output_dir / "footer_region.png"), footer_region)

# Create annotated version with horizontal scan lines every 1%
annotated = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

for pct in range(75, 96):
    y = int(height * pct / 100)
    color = (0, 255, 0) if pct % 5 == 0 else (255, 0, 255)  # Green every 5%, magenta otherwise
    cv2.line(annotated, (0, y), (width, y), color, 1)
    cv2.putText(annotated, f"{pct}%", (10, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

cv2.imwrite(str(output_dir / "annotated_page.png"), annotated)

print(f"\nSaved to {output_dir}:")
print("  - full_page.png: Binarized full page")
print("  - footer_region.png: Footer region only (75-100%)")
print("  - annotated_page.png: Page with percentage markers")

# Also check specific Y positions where previous analysis found footer lines
print("\n Checking specific Y positions:")
for y_pct in [80.7, 82.5, 85.0, 90.0, 93.5]:
    y = int(height * y_pct / 100)
    # Sample a horizontal line
    line_sample = binary[y, :]
    # Find transitions from white to black
    transitions = np.diff((line_sample == 0).astype(int))
    start_positions = np.where(transitions == 1)[0]
    end_positions = np.where(transitions == -1)[0]

    print(f"\n  At Y={y} ({y_pct}%):")
    print(f"    Black segments: {len(start_positions)}")
    if len(start_positions) > 0 and len(start_positions) <= 10:
        for i in range(min(len(start_positions), len(end_positions))):
            segment_length = end_positions[i] - start_positions[i]
            print(f"      Segment {i+1}: X={start_positions[i]}-{end_positions[i]} (length={segment_length}px, {segment_length/width*100:.1f}%)")
