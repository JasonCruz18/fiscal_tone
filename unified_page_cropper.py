"""
Unified Page Cropper - Integrates 3 Perfect Cropping Strategies

Combines:
1. Top crop: Logo detection (binarization + contours)
2. Bottom crop: Footer line detection (detect_cut_line_y) + conservative fallback
3. Lateral crop: Fixed margins (detect_lateral_cut_x)

Author: Integration of existing perfect functions
"""
#%%
import os
import cv2
import numpy as np
import json
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image
from tqdm import tqdm


# =========================================================
# 1. TOP CROP: Logo Detection (Binarization + Contours)
# =========================================================
def detect_logo_bottom(image, logo_search_end=0.20, min_logo_area=500, max_logo_area=50000):
    """
    Detect logo at top of page using binarization

    Returns: Y coordinate of logo bottom (or 0 if not found)
    """
    img_np = np.array(image)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

    # Binarize using Otsu's thresholding
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    height, width = image.height, image.width
    search_end = int(height * logo_search_end)
    top_region = binary[0:search_end, :]

    # Invert to find black regions (logo is black after binarization)
    inverted = cv2.bitwise_not(top_region)
    contours, _ = cv2.findContours(inverted, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter by area and select largest
    valid_contours = [c for c in contours if min_logo_area <= cv2.contourArea(c) <= max_logo_area]

    if not valid_contours:
        return 0  # No logo found

    largest_contour = max(valid_contours, key=cv2.contourArea)
    _, _, _, h = cv2.boundingRect(largest_contour)
    logo_bottom = cv2.boundingRect(largest_contour)[1] + h

    return logo_bottom


# =========================================================
# 2. BOTTOM CROP: Footer Line Detection (from detect_cut_line_y.py)
# =========================================================
def detect_cut_line_y(image, min_length_ratio=0.16, y_range=(0.40, 0.95)):
    """
    Detect footer line using Hough transform (YOUR PERFECT FUNCTION)

    Returns: Y coordinate of cut line (or height if not found)
    """
    img_np = np.array(image)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    height, width = image.height, image.width
    half_width = int(width * 0.5)
    min_y, max_y = int(height * y_range[0]), int(height * y_range[1])

    # Only search left half
    thresh[:, half_width:] = 0

    lines = cv2.HoughLinesP(
        thresh, 1, np.pi / 180, threshold=50,
        minLineLength=int(width * min_length_ratio), maxLineGap=9
    )

    best_y = height  # Default: no line found
    candidate_lines = []

    if lines is not None:
        for line in lines[:, 0]:
            x1, y1, x2, y2 = line
            if abs(y1 - y2) <= 9 and min_y <= y1 <= max_y:
                candidate_lines.append((x1, y1, x2, y2))

        if candidate_lines:
            best_line = min(candidate_lines, key=lambda l: l[1])
            best_y = best_line[1]

    return best_y


# =========================================================
# 3. BOTTOM CROP FALLBACK: Conservative Whitespace Detection
# =========================================================
def detect_footer_conservative(image, whitespace_threshold=0.05, min_zone_height=100,
                               address_search_start=0.85, max_cut_position=0.92):
    """
    Conservative footer detection using whitespace zones (FALLBACK)

    Returns: Y coordinate of safe cut position
    """
    img_np = np.array(image)
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    height, width = image.height, image.width

    # Find address region (last text block at bottom)
    address_start = int(height * address_search_start)

    # Calculate row blackness
    row_blackness = []
    for y in range(height):
        row = binary[y, :]
        black_pixels = np.sum(row == 0)
        blackness = black_pixels / width
        row_blackness.append(blackness)

    # Find last text region working backwards from bottom
    last_text_y = address_start
    for y in range(height - 1, address_start, -1):
        if row_blackness[y] > whitespace_threshold:
            last_text_y = y
            break

    # Find large whitespace zone before address
    search_start = int(height * 0.50)
    zones = []
    zone_start = None

    for y in range(search_start, last_text_y):
        if row_blackness[y] <= whitespace_threshold:
            if zone_start is None:
                zone_start = y
        else:
            if zone_start is not None:
                zone_height = y - zone_start
                if zone_height >= min_zone_height:
                    zones.append((zone_start, y))
                zone_start = None

    # Use base of last large zone (closest to address)
    if zones:
        cut_y = zones[-1][1]  # Base of last zone
    else:
        cut_y = int(height * max_cut_position)  # Safety fallback

    return min(cut_y, int(height * max_cut_position))


# =========================================================
# 4. LATERAL CROP: Fixed Margins (from detect_lateral_cut_x.py)
# =========================================================
def detect_lateral_cuts(image, dpi=300, left_cm=2.25, right_cm=2.25):
    """
    Calculate lateral crop coordinates based on CM and DPI (YOUR PERFECT FUNCTION)

    Returns: (cut_x1, cut_x2)
    """
    height, width = image.height, image.width

    # Convert CM to pixels
    px_cut_left = int((left_cm / 2.54) * dpi)
    px_cut_right = int((right_cm / 2.54) * dpi)

    cut_x1 = px_cut_left
    cut_x2 = width - px_cut_right

    # Safety check
    if cut_x1 >= cut_x2:
        cut_x1, cut_x2 = 0, width

    return cut_x1, cut_x2


# =========================================================
# 5. UNIFIED CROPPING FUNCTION
# =========================================================
def unified_crop_page(image,
                     crop_top=True,
                     crop_bottom=True,
                     crop_lateral=True,
                     dpi=300,
                     left_cm=2.25,
                     right_cm=2.25,
                     debug_path=None):
    """
    Unified page cropping with all 3 strategies

    Args:
        image: PIL Image
        crop_top: Enable logo detection (top crop)
        crop_bottom: Enable footer line + conservative detection (bottom crop)
        crop_lateral: Enable lateral fixed margins
        dpi: DPI for lateral crop calculations
        left_cm: Left margin in CM
        right_cm: Right margin in CM
        debug_path: Path to save debug visualization

    Returns:
        crop_coords: dict with {top, bottom, left, right}
        metadata: dict with detection info
    """
    height, width = image.height, image.width

    # Initialize crop coordinates (no crop by default)
    crop_top_y = 0
    crop_bottom_y = height
    crop_left_x = 0
    crop_right_x = width

    metadata = {
        'logo_detected': False,
        'footer_line_detected': False,
        'conservative_fallback_used': False,
        'lateral_crop_applied': False
    }

    # === 1. TOP CROP: Logo Detection ===
    if crop_top:
        logo_bottom = detect_logo_bottom(image)
        if logo_bottom > 0:
            crop_top_y = logo_bottom
            metadata['logo_detected'] = True

    # === 2. BOTTOM CROP: Footer Line + Conservative Fallback ===
    if crop_bottom:
        # Try footer line detection first
        footer_y = detect_cut_line_y(image)

        if footer_y < height:
            # Footer line found!
            crop_bottom_y = footer_y
            metadata['footer_line_detected'] = True
        else:
            # No footer line found, use conservative fallback
            crop_bottom_y = detect_footer_conservative(image)
            metadata['conservative_fallback_used'] = True

    # === 3. LATERAL CROP: Fixed Margins ===
    if crop_lateral:
        crop_left_x, crop_right_x = detect_lateral_cuts(image, dpi, left_cm, right_cm)
        metadata['lateral_crop_applied'] = True

    crop_coords = {
        'top': crop_top_y,
        'bottom': crop_bottom_y,
        'left': crop_left_x,
        'right': crop_right_x
    }

    # === 4. DEBUG VISUALIZATION ===
    if debug_path:
        create_debug_visualization(image, crop_coords, metadata, debug_path)

    return crop_coords, metadata


def create_debug_visualization(image, crop_coords, metadata, debug_path):
    """
    Create comprehensive debug visualization showing all crop lines and ROIs
    """
    img_np = np.array(image)
    debug_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
    overlay = debug_img.copy()

    height, width = image.height, image.width
    top, bottom, left, right = crop_coords['top'], crop_coords['bottom'], crop_coords['left'], crop_coords['right']

    # Colors
    roi_color = (255, 102, 51)  # Orange (discarded regions)
    line_color = (76, 0, 230)   # Purple (cut lines)

    # === Draw discarded regions (semi-transparent orange) ===

    # Top region (logo area)
    if top > 0:
        cv2.rectangle(overlay, (0, 0), (width, top), roi_color, -1)

    # Bottom region (footer area)
    if bottom < height:
        cv2.rectangle(overlay, (0, bottom), (width, height), roi_color, -1)

    # Left margin
    if left > 0:
        cv2.rectangle(overlay, (0, 0), (left, height), roi_color, -1)

    # Right margin
    if right < width:
        cv2.rectangle(overlay, (right, 0), (width, height), roi_color, -1)

    # Apply transparency
    cv2.addWeighted(overlay, 0.3, debug_img, 0.7, 0, debug_img)

    # === Draw cut lines ===

    # Top cut line
    if top > 0:
        cv2.line(debug_img, (0, top), (width, top), line_color, 5)
        cv2.putText(debug_img, f"TOP: {top}px", (10, top - 15),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, line_color, 2)

    # Bottom cut line
    if bottom < height:
        cv2.line(debug_img, (0, bottom), (width, bottom), line_color, 5)
        label = "FOOTER LINE" if metadata['footer_line_detected'] else "CONSERVATIVE"
        cv2.putText(debug_img, f"{label}: {bottom}px", (10, bottom - 15),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, line_color, 2)

    # Left cut line
    if left > 0:
        cv2.line(debug_img, (left, 0), (left, height), line_color, 5)
        cv2.putText(debug_img, f"L: {left}px", (left + 10, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, line_color, 2)

    # Right cut line
    if right < width:
        cv2.line(debug_img, (right, 0), (right, height), line_color, 5)
        cv2.putText(debug_img, f"R: {right}px", (right - 120, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, line_color, 2)

    # === Add metadata labels ===
    y_offset = 30
    if metadata['logo_detected']:
        cv2.putText(debug_img, "[OK] Logo detected", (10, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        y_offset += 30

    if metadata['footer_line_detected']:
        cv2.putText(debug_img, "[OK] Footer line detected", (10, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    elif metadata['conservative_fallback_used']:
        cv2.putText(debug_img, "[FALLBACK] Conservative footer", (10, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    y_offset += 30

    if metadata['lateral_crop_applied']:
        cv2.putText(debug_img, "[OK] Lateral crop applied", (10, y_offset),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    cv2.imwrite(debug_path, debug_img)


# =========================================================
# 6. MAIN PROCESSING FUNCTION
# =========================================================
def process_all_pdfs_unified(input_folder="data/raw/scanned",
                             output_base="data/raw/scanned",
                             crop_top=True,
                             crop_bottom=True,
                             crop_lateral=True,
                             dpi=300,
                             left_cm=2.25,
                             right_cm=2.25):
    """
    Process all PDFs with unified cropping strategy

    Generates:
        - debug_lines/*.png: Debug visualizations with ROIs and cut lines
        - debug_lines/cropped/*.png: Final cropped pages
        - cropped_scanned_pdfs.json: Processing results
    """
    input_folder = Path(input_folder)
    output_base = Path(output_base)

    # Create output directories
    debug_dir = output_base / "debug_lines"
    cropped_dir = debug_dir / "cropped"
    debug_dir.mkdir(parents=True, exist_ok=True)
    cropped_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*80}")
    print(f"UNIFIED PAGE CROPPER")
    print('='*80)
    print(f"Input folder: {input_folder}")
    print(f"Output base: {output_base}")
    print(f"\nCrop settings:")
    print(f"  Top (logo):      {crop_top}")
    print(f"  Bottom (footer): {crop_bottom}")
    print(f"  Lateral:         {crop_lateral} (L={left_cm}cm, R={right_cm}cm)")
    print('='*80)

    # Get all PDFs
    pdf_files = sorted(input_folder.glob("*.pdf"))

    if not pdf_files:
        print(f"\n[ERROR] No PDF files found in {input_folder}")
        return

    print(f"\nFound {len(pdf_files)} PDF files\n")

    # Results tracking
    results = []
    total_pages = 0

    for pdf_path in tqdm(pdf_files, desc="Processing PDFs", ncols=80):
        try:
            # Convert PDF to images
            images = convert_from_path(str(pdf_path), dpi=dpi)

            for page_num, image in enumerate(images, start=1):
                total_pages += 1

                # Generate filenames
                base_name = pdf_path.stem
                debug_filename = f"{base_name}_p{page_num:02d}_debug.png"
                cropped_filename = f"{base_name}_p{page_num:02d}_cropped.png"

                debug_path = debug_dir / debug_filename
                cropped_path = cropped_dir / cropped_filename

                # Perform unified cropping
                crop_coords, metadata = unified_crop_page(
                    image,
                    crop_top=crop_top,
                    crop_bottom=crop_bottom,
                    crop_lateral=crop_lateral,
                    dpi=dpi,
                    left_cm=left_cm,
                    right_cm=right_cm,
                    debug_path=str(debug_path)
                )

                # Crop image
                cropped_img = image.crop((
                    crop_coords['left'],
                    crop_coords['top'],
                    crop_coords['right'],
                    crop_coords['bottom']
                ))

                # Save cropped image
                cropped_img.save(cropped_path)

            # Record success
            results.append({
                'filename': pdf_path.name,
                'cropped': 1,
                'pages': len(images)
            })

        except Exception as e:
            print(f"\n[ERROR] Failed to process {pdf_path.name}: {e}")
            results.append({
                'filename': pdf_path.name,
                'cropped': 0,
                'error': str(e)
            })

    # Save results JSON
    json_path = output_base / "cropped_scanned_pdfs.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\n{'='*80}")
    print("PROCESSING COMPLETE")
    print('='*80)
    print(f"Total PDFs: {len(pdf_files)}")
    print(f"Total pages: {total_pages}")
    print(f"Successful: {sum(r['cropped'] for r in results)}/{len(results)}")
    print(f"\nOutputs:")
    print(f"  Debug visualizations: {debug_dir}/ ({total_pages} files)")
    print(f"  Cropped pages: {cropped_dir}/ ({total_pages} files)")
    print(f"  Results JSON: {json_path}")
    print('='*80)


# =========================================================
# 7. RUNNER
# =========================================================
if __name__ == "__main__":
    process_all_pdfs_unified(
        input_folder="data/raw/scanned",
        output_base="data/raw/scanned",
        crop_top=True,           # Logo detection
        crop_bottom=True,        # Footer line + conservative fallback
        crop_lateral=True,       # Fixed lateral margins
        dpi=300,
        left_cm=2.75,
        right_cm=2.75
    )
