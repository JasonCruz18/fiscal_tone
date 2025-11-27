"""
Comprehensive Page-by-Page Analysis for Footer Detection

Strategy insights from user:
1. Page structure: main content (high blackness) → whitespace → footer line separator →
   short whitespace → footnotes → whitespace → page number (bottom right) →
   whitespace → addresses (1-2 lines) → whitespace

2. Key elements to identify:
   - Main content: concentrated black pixels (paragraphs)
   - Whitespace zones: gaps between sections
   - Footer line separator: thin horizontal line segments
   - Page number: bottom right corner
   - Addresses: "Av. República de Panamá 3531..." (last text, to discard)

3. Detection strategy:
   - Start from MID of page (skip institutional sign noise at ~50%)
   - Identify whitespace zones dynamically
   - Detect footer line separator in whitespace
   - Use page number and addresses as reference points to discard false positives
   - Combine line detection + whitespace analysis
"""

import cv2
import numpy as np
from pdf2image import convert_from_path
from pathlib import Path
import matplotlib.pyplot as plt

PDF_PATH = "data/raw/scanned/INFORME_N_002-2017-CF.pdf"
OUTPUT_DIR = Path("comprehensive_analysis")

def analyze_page_structure(binary_image, page_num):
    """
    Comprehensive analysis of page structure:
    - Blackness density by vertical position
    - Whitespace zones
    - Horizontal line positions
    - Text bounding boxes
    """
    height, width = binary_image.shape

    # 1. Calculate blackness density per row (vertical profile)
    row_blackness = []
    for y in range(height):
        row = binary_image[y, :]
        blackness = np.sum(row == 0) / width  # Fraction of black pixels
        row_blackness.append(blackness)

    row_blackness = np.array(row_blackness)

    # 2. Identify whitespace zones (low blackness)
    whitespace_threshold = 0.05  # Less than 5% black = whitespace
    is_whitespace = row_blackness < whitespace_threshold

    # 3. Find whitespace zones (consecutive whitespace rows)
    whitespace_zones = []
    in_zone = False
    zone_start = 0

    for y in range(height):
        if is_whitespace[y] and not in_zone:
            zone_start = y
            in_zone = True
        elif not is_whitespace[y] and in_zone:
            if y - zone_start > 20:  # At least 20 pixels tall
                whitespace_zones.append((zone_start, y, y - zone_start))
            in_zone = False

    # 4. Detect horizontal lines using Hough transform
    inverted = cv2.bitwise_not(binary_image)
    lines = cv2.HoughLinesP(
        inverted,
        rho=1,
        theta=np.pi/180,
        threshold=30,
        minLineLength=int(width * 0.02),  # 2% of width
        maxLineGap=10
    )

    horizontal_lines = []
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            if abs(y2 - y1) <= 3:  # Horizontal
                horizontal_lines.append({
                    'y': (y1 + y2) // 2,
                    'x1': min(x1, x2),
                    'x2': max(x1, x2),
                    'length': abs(x2 - x1),
                    'length_pct': abs(x2 - x1) / width * 100
                })

    # Sort lines by Y position
    horizontal_lines.sort(key=lambda l: l['y'])

    # 5. Detect text regions (dense black areas)
    # Divide page into bands and identify concentrated blackness
    band_height = 50
    num_bands = height // band_height
    band_blackness = []

    for i in range(num_bands):
        y_start = i * band_height
        y_end = min((i + 1) * band_height, height)
        band = binary_image[y_start:y_end, :]
        blackness = np.sum(band == 0) / band.size
        band_blackness.append({
            'band': i,
            'y_start': y_start,
            'y_end': y_end,
            'y_center': (y_start + y_end) // 2,
            'blackness': blackness,
            'pct_from_top': y_start / height * 100
        })

    # 6. Find page number region (bottom-right, specific pattern)
    # Check bottom 10% of page, right 20% of width
    bottom_region = binary_image[int(height * 0.90):, int(width * 0.80):]
    has_page_number = np.sum(bottom_region == 0) > 100  # Some text present

    return {
        'height': height,
        'width': width,
        'row_blackness': row_blackness,
        'whitespace_zones': whitespace_zones,
        'horizontal_lines': horizontal_lines,
        'band_blackness': band_blackness,
        'has_page_number': has_page_number
    }


def visualize_page_analysis(binary_image, analysis, page_num, output_dir):
    """Create comprehensive visualization of page analysis"""
    height = analysis['height']
    width = analysis['width']

    # Create figure with multiple subplots
    fig = plt.figure(figsize=(20, 12))

    # Subplot 1: Original page with annotations
    ax1 = plt.subplot(2, 3, 1)
    ax1.imshow(binary_image, cmap='gray')
    ax1.set_title(f'Page {page_num} - Annotated', fontsize=14, fontweight='bold')
    ax1.axis('off')

    # Draw whitespace zones
    for zone_start, zone_end, zone_height in analysis['whitespace_zones']:
        rect = plt.Rectangle((0, zone_start), width, zone_height,
                            facecolor='cyan', alpha=0.3, edgecolor='blue', linewidth=2)
        ax1.add_patch(rect)
        ax1.text(10, (zone_start + zone_end) // 2,
                f'WS: {zone_start}-{zone_end} ({zone_height}px)',
                color='blue', fontsize=10, fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # Draw horizontal lines
    for line in analysis['horizontal_lines']:
        ax1.plot([line['x1'], line['x2']], [line['y'], line['y']],
                'r-', linewidth=3, alpha=0.7)
        ax1.text(line['x2'] + 10, line['y'],
                f"{line['y']}px ({line['y']/height*100:.1f}%) L={line['length_pct']:.1f}%",
                color='red', fontsize=9, fontweight='bold',
                bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.8))

    # Mark page mid
    mid_y = height // 2
    ax1.axhline(y=mid_y, color='green', linestyle='--', linewidth=2, alpha=0.7)
    ax1.text(width - 200, mid_y - 20, 'PAGE MID (50%)',
            color='green', fontsize=12, fontweight='bold',
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.9))

    # Subplot 2: Blackness profile
    ax2 = plt.subplot(2, 3, 2)
    y_positions = np.arange(len(analysis['row_blackness']))
    ax2.plot(analysis['row_blackness'], y_positions, 'b-', linewidth=1)
    ax2.axvline(x=0.05, color='red', linestyle='--', label='Whitespace threshold (5%)')
    ax2.set_xlabel('Blackness (fraction of black pixels)', fontsize=12)
    ax2.set_ylabel('Y position (pixels)', fontsize=12)
    ax2.set_title('Vertical Blackness Profile', fontsize=14, fontweight='bold')
    ax2.invert_yaxis()
    ax2.grid(True, alpha=0.3)
    ax2.legend()

    # Mark important regions
    ax2.axhline(y=mid_y, color='green', linestyle='--', linewidth=2, alpha=0.7, label='Mid')

    # Subplot 3: Band blackness
    ax3 = plt.subplot(2, 3, 3)
    bands = [b['band'] for b in analysis['band_blackness']]
    blackness_values = [b['blackness'] for b in analysis['band_blackness']]
    colors = ['red' if b > 0.15 else 'green' if b < 0.05 else 'orange'
              for b in blackness_values]
    ax3.barh(bands, blackness_values, color=colors, alpha=0.7)
    ax3.set_xlabel('Blackness (fraction)', fontsize=12)
    ax3.set_ylabel('Band number (50px each)', fontsize=12)
    ax3.set_title('Band Blackness (Red=Dense, Green=Whitespace)', fontsize=14, fontweight='bold')
    ax3.axvline(x=0.05, color='blue', linestyle='--', linewidth=2, label='WS threshold')
    ax3.axvline(x=0.15, color='red', linestyle='--', linewidth=2, label='Dense threshold')
    ax3.invert_yaxis()
    ax3.grid(True, alpha=0.3, axis='x')
    ax3.legend()

    # Subplot 4: Bottom region (page number + address area)
    ax4 = plt.subplot(2, 3, 4)
    bottom_start = int(height * 0.85)
    bottom_region = binary_image[bottom_start:, :]
    ax4.imshow(bottom_region, cmap='gray')
    ax4.set_title(f'Bottom 15% (from {bottom_start}px = 85%)', fontsize=14, fontweight='bold')
    ax4.axis('off')

    # Subplot 5: Mid to bottom region (where footer separator should be)
    ax5 = plt.subplot(2, 3, 5)
    mid_to_bottom = binary_image[mid_y:, :]
    ax5.imshow(mid_to_bottom, cmap='gray')
    ax5.set_title(f'Mid to Bottom (from {mid_y}px = 50%)', fontsize=14, fontweight='bold')
    ax5.axis('off')

    # Subplot 6: Summary statistics
    ax6 = plt.subplot(2, 3, 6)
    ax6.axis('off')

    summary_text = f"""
PAGE {page_num} ANALYSIS SUMMARY

Dimensions: {width} x {height} pixels

WHITESPACE ZONES: {len(analysis['whitespace_zones'])}
"""

    for i, (start, end, h) in enumerate(analysis['whitespace_zones'], 1):
        summary_text += f"\n  Zone {i}: Y={start}-{end} ({h}px, {start/height*100:.1f}%-{end/height*100:.1f}%)"

    summary_text += f"\n\nHORIZONTAL LINES: {len(analysis['horizontal_lines'])}\n"

    for i, line in enumerate(analysis['horizontal_lines'][:10], 1):  # First 10
        summary_text += f"\n  Line {i}: Y={line['y']} ({line['y']/height*100:.1f}%), Length={line['length_pct']:.1f}%"

    if len(analysis['horizontal_lines']) > 10:
        summary_text += f"\n  ... and {len(analysis['horizontal_lines']) - 10} more"

    summary_text += f"\n\nDENSE TEXT BANDS (>15% blackness):\n"
    dense_bands = [b for b in analysis['band_blackness'] if b['blackness'] > 0.15]
    for band in dense_bands[:5]:
        summary_text += f"\n  Band {band['band']}: Y={band['y_start']}-{band['y_end']} ({band['pct_from_top']:.1f}%), Blackness={band['blackness']:.2%}"

    summary_text += f"\n\nPAGE NUMBER DETECTED: {analysis['has_page_number']}"

    ax6.text(0.05, 0.95, summary_text, transform=ax6.transAxes,
            fontsize=10, verticalalignment='top', family='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    plt.tight_layout()

    # Save
    output_path = output_dir / f'page_{page_num:02d}_analysis.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()

    return output_path


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    print("="*80)
    print(f"COMPREHENSIVE PAGE ANALYSIS: {PDF_PATH}")
    print("="*80)

    # Get all pages
    images = convert_from_path(PDF_PATH, dpi=300)
    num_pages = len(images)

    print(f"\nTotal pages: {num_pages}\n")

    all_analyses = []

    for page_num in range(1, num_pages + 1):
        print(f"\n{'='*80}")
        print(f"PAGE {page_num}")
        print('='*80)

        # Get page image
        page_image = np.array(images[page_num - 1])

        # Binarize
        gray = cv2.cvtColor(page_image, cv2.COLOR_RGB2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Analyze
        analysis = analyze_page_structure(binary, page_num)
        all_analyses.append(analysis)

        # Print summary
        print(f"Dimensions: {analysis['width']} x {analysis['height']}")
        print(f"\nWhitespace zones: {len(analysis['whitespace_zones'])}")
        for i, (start, end, h) in enumerate(analysis['whitespace_zones'], 1):
            print(f"  Zone {i}: Y={start:4d}-{end:4d} ({h:3d}px, {start/analysis['height']*100:5.1f}%-{end/analysis['height']*100:5.1f}%)")

        print(f"\nHorizontal lines: {len(analysis['horizontal_lines'])}")
        for i, line in enumerate(analysis['horizontal_lines'][:5], 1):
            print(f"  Line {i}: Y={line['y']:4d} ({line['y']/analysis['height']*100:5.1f}%), Length={line['length_pct']:5.1f}%")
        if len(analysis['horizontal_lines']) > 5:
            print(f"  ... and {len(analysis['horizontal_lines']) - 5} more")

        print(f"\nPage number detected: {analysis['has_page_number']}")

        # Visualize
        output_path = visualize_page_analysis(binary, analysis, page_num, OUTPUT_DIR)
        print(f"\n[+] Saved: {output_path.name}")

    print(f"\n{'='*80}")
    print("ANALYSIS COMPLETE")
    print(f"{'='*80}")
    print(f"\nAll visualizations saved to: {OUTPUT_DIR}/")
    print(f"\nNext step: Review visualizations to identify patterns for robust footer detection")


if __name__ == "__main__":
    main()
