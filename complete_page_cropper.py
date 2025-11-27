"""
Complete Page Cropper - Detects logo top + footer bottom, crops clean content

FINAL PRODUCTION SCRIPT
"""

import cv2
import numpy as np
from pdf2image import convert_from_path
from pathlib import Path
import json
from tqdm import tqdm


# === CONFIGURATION ===
# Footer detection
WHITESPACE_THRESHOLD = 0.05
MIN_ZONE_HEIGHT = 100
ADDRESS_SEARCH_START = 0.85
MAX_CUT_POSITION = 0.92

# Logo detection
LOGO_SEARCH_END = 0.20  # Search top 20% for logo
MIN_LOGO_AREA = 500     # Minimum area for logo (px²)
MAX_LOGO_AREA = 50000   # Maximum area for logo (px²)


def calculate_row_blackness(binary_image, start_y, end_y):
    """Calculate blackness for each row"""
    width = binary_image.shape[1]
    row_blackness = []
    for y in range(start_y, end_y):
        row = binary_image[y, :]
        blackness = np.sum(row == 0) / width
        row_blackness.append({'y': y, 'blackness': blackness})
    return row_blackness


def detect_logo_bottom(binary_image, debug=False):
    """
    Detect the logo/header at top and return its bottom Y coordinate

    Strategy: Find black contours in top 20% of page, select largest one
    """
    height, width = binary_image.shape
    search_end = int(height * LOGO_SEARCH_END)

    # Extract top region
    top_region = binary_image[0:search_end, :]

    # Invert to find black regions
    inverted = cv2.bitwise_not(top_region)

    # Find contours
    contours, _ = cv2.findContours(inverted, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        if debug:
            print(f"  [LOGO] No contours found, using default 5%")
        return int(height * 0.05)

    # Filter contours by area
    valid_contours = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if MIN_LOGO_AREA <= area <= MAX_LOGO_AREA:
            x, y, w, h = cv2.boundingRect(cnt)
            valid_contours.append({
                'contour': cnt,
                'x': x,
                'y': y,
                'w': w,
                'h': h,
                'area': area,
                'bottom': y + h
            })

    if not valid_contours:
        if debug:
            print(f"  [LOGO] No valid contours (area filter), using default 5%")
        return int(height * 0.05)

    # Select contour with largest area (most likely the logo)
    logo = max(valid_contours, key=lambda c: c['area'])
    logo_bottom = logo['bottom']

    if debug:
        print(f"  [LOGO] Detected at Y=0-{logo_bottom} (0.0%-{logo_bottom/height:.1%})")
        print(f"         Area={logo['area']}px², Box=({logo['x']},{logo['y']},{logo['w']},{logo['h']})")

    return logo_bottom


def detect_footer_top(binary_image, debug=False):
    """
    Detect footer start using conservative whitespace strategy

    Returns Y coordinate where footer begins
    """
    height, width = binary_image.shape

    # Find address
    search_start = int(height * ADDRESS_SEARCH_START)
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

    if address_start is None:
        address_start = int(height * 0.93)

    # Find large whitespace zones before address
    search_start = int(height * 0.50)
    max_cut = min(int(height * MAX_CUT_POSITION), address_start)

    row_blackness = calculate_row_blackness(binary_image, search_start, max_cut)

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

    if in_zone:
        y_last = row_blackness[-1]['y']
        zone_height = y_last - zone_start
        if zone_height >= MIN_ZONE_HEIGHT:
            zones.append({
                'start': zone_start,
                'end': y_last,
                'height': zone_height
            })

    if not zones:
        footer_top = max_cut
        if debug:
            print(f"  [FOOTER] No zones found, using max_cut at {footer_top/height:.1%}")
    else:
        # Use last (closest to address) zone
        selected_zone = zones[-1]
        footer_top = selected_zone['end']
        if debug:
            print(f"  [FOOTER] Cut at Y={footer_top} ({footer_top/height:.1%})")

    return footer_top


def crop_page_content(binary_image, debug=False):
    """
    Crop page to main content only (between logo and footer)

    Returns: (cropped_image, crop_info)
    """
    height, width = binary_image.shape

    # Detect boundaries
    logo_bottom = detect_logo_bottom(binary_image, debug=debug)
    footer_top = detect_footer_top(binary_image, debug=debug)

    # Safety check
    if logo_bottom >= footer_top:
        if debug:
            print(f"  [WARNING] Logo bottom >= Footer top, using defaults")
        logo_bottom = int(height * 0.05)
        footer_top = int(height * 0.90)

    # Crop
    cropped = binary_image[logo_bottom:footer_top, :]

    crop_info = {
        'logo_bottom': int(logo_bottom),
        'footer_top': int(footer_top),
        'logo_bottom_pct': logo_bottom / height,
        'footer_top_pct': footer_top / height,
        'original_height': int(height),
        'cropped_height': int(footer_top - logo_bottom),
        'kept_pct': (footer_top - logo_bottom) / height
    }

    if debug:
        print(f"  [CROP] Logo: 0-{logo_bottom} (0.0%-{logo_bottom/height:.1%})")
        print(f"         Content: {logo_bottom}-{footer_top} ({logo_bottom/height:.1%}-{footer_top/height:.1%})")
        print(f"         Footer: {footer_top}-{height} ({footer_top/height:.1%}-100.0%)")
        print(f"         Kept: {crop_info['kept_pct']:.1%} of page")

    return cropped, crop_info


def visualize_and_crop_page(pdf_path, page_num, vis_dir, crop_dir):
    """
    Process one page: create visualization + save cropped image

    Returns crop_info dict
    """
    images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num, dpi=300)
    page_image = np.array(images[0])

    gray = cv2.cvtColor(page_image, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Crop content
    cropped, info = crop_page_content(binary, debug=False)

    # === SAVE VISUALIZATION ===
    vis_image = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
    height, width = binary.shape

    logo_bottom = info['logo_bottom']
    footer_top = info['footer_top']

    # Highlight DISCARDED regions (light red)
    overlay = vis_image.copy()
    cv2.rectangle(overlay, (0, 0), (width, logo_bottom), (200, 200, 255), -1)
    cv2.rectangle(overlay, (0, footer_top), (width, height), (200, 200, 255), -1)
    cv2.addWeighted(overlay, 0.15, vis_image, 0.85, 0, vis_image)

    # Highlight KEPT region (light green)
    overlay = vis_image.copy()
    cv2.rectangle(overlay, (0, logo_bottom), (width, footer_top), (200, 255, 200), -1)
    cv2.addWeighted(overlay, 0.1, vis_image, 0.9, 0, vis_image)

    # Draw cut lines
    cv2.line(vis_image, (0, logo_bottom), (width, logo_bottom), (0, 0, 255), 5)  # Red top
    cv2.line(vis_image, (0, footer_top), (width, footer_top), (0, 255, 0), 5)    # Green bottom

    # Labels
    cv2.putText(vis_image, f"DISCARD TOP: 0%-{logo_bottom/height:.1%}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 200), 2)
    cv2.putText(vis_image, f"KEEP: {logo_bottom/height:.1%}-{footer_top/height:.1%} ({info['kept_pct']:.1%})",
                (10, logo_bottom + 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 150, 0), 3)
    cv2.putText(vis_image, f"DISCARD BOTTOM: {footer_top/height:.1%}-100%",
                (10, footer_top - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 150, 0), 2)

    # Save visualization
    vis_filename = f"{pdf_path.stem}_page{page_num:02d}_vis.png"
    vis_path = vis_dir / vis_filename
    cv2.imwrite(str(vis_path), vis_image)

    # === SAVE CROPPED PAGE ===
    crop_filename = f"{pdf_path.stem}_page{page_num:02d}_cropped.png"
    crop_path = crop_dir / crop_filename
    cv2.imwrite(str(crop_path), cropped)

    return info


def process_all_pdfs(pdf_dir="data/raw/scanned", output_base="cropped_output"):
    """
    Process all 13 PDFs: generate visualizations + cropped pages
    """
    pdf_dir = Path(pdf_dir)
    output_base = Path(output_base)

    vis_dir = output_base / "visualizations"
    crop_dir = output_base / "cropped_pages"
    vis_dir.mkdir(parents=True, exist_ok=True)
    crop_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(pdf_dir.glob("*.pdf"))

    print(f"\n{'='*80}")
    print(f"PROCESSING {len(pdf_files)} PDFs")
    print(f"{'='*80}\n")

    all_results = {}

    for pdf_path in pdf_files:
        print(f"\n[PDF] {pdf_path.name}")

        # Get page count
        images = convert_from_path(pdf_path, dpi=72)
        num_pages = len(images)

        pdf_results = []

        # Process each page with progress bar
        for page_num in tqdm(range(1, num_pages + 1), desc=f"  Pages", ncols=80):
            try:
                info = visualize_and_crop_page(pdf_path, page_num, vis_dir, crop_dir)
                pdf_results.append({
                    'page': page_num,
                    **info
                })
            except Exception as e:
                print(f"    [ERROR] Page {page_num}: {e}")
                pdf_results.append({
                    'page': page_num,
                    'error': str(e)
                })

        all_results[pdf_path.stem] = pdf_results

        # Summary for this PDF
        successful = [r for r in pdf_results if 'error' not in r]
        if successful:
            avg_kept = np.mean([r['kept_pct'] for r in successful])
            print(f"  [OK] {len(successful)}/{num_pages} pages | Avg kept: {avg_kept:.1%}")

    # Save comprehensive results
    results_file = output_base / "crop_results.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        # Convert numpy types to native Python types
        def convert(obj):
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            return obj

        clean_results = {k: [{key: convert(val) for key, val in item.items()}
                             for item in v] for k, v in all_results.items()}
        json.dump(clean_results, f, indent=2)

    # Final summary
    total_pages = sum(len(v) for v in all_results.values())
    total_successful = sum(len([r for r in v if 'error' not in r]) for v in all_results.values())

    print(f"\n{'='*80}")
    print("FINAL SUMMARY")
    print('='*80)
    print(f"Total PDFs: {len(pdf_files)}")
    print(f"Total pages: {total_pages}")
    print(f"Successful: {total_successful}/{total_pages}")
    print(f"\nOutputs:")
    print(f"  Visualizations: {vis_dir}/ ({total_successful} images)")
    print(f"  Cropped pages: {crop_dir}/ ({total_successful} images)")
    print(f"  Results JSON: {results_file}")
    print('='*80)


if __name__ == "__main__":
    process_all_pdfs()
