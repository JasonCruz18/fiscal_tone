"""
Scanned PDF Text Extractor with OCR Best Practices

Key improvements:
1. Binarization for improved OCR quality
2. Density-based black square detection for logo (page 2+)
3. Enhanced footer detection: lines + density analysis (last 3/4 of page)
4. Debug folder for footer inspection
5. JSON output with page-level records
"""

import os
import json
import numpy as np
import cv2
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from typing import List, Dict, Tuple, Optional
from collections import defaultdict

# Configure Tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'


# === Configuration Parameters ===

OCR_DPI = 300
OCR_LANG = 'spa'

# Binarization parameters
BINARY_THRESHOLD = 127          # Otsu's method will be used (adaptive)
USE_ADAPTIVE_THRESHOLD = True   # More robust for scanned documents

# Logo detection (black square at top)
LOGO_SEARCH_HEIGHT = 0.12       # Search top 12% only
LOGO_MIN_SIZE = 30              # Minimum size in pixels
LOGO_MAX_SIZE = 150             # Maximum size in pixels
LOGO_DENSITY_THRESHOLD = 0.6    # At least 60% black pixels to be considered logo

# Footer detection (last 3/4 of page)
FOOTER_SEARCH_START = 0.25      # Start searching at 25% (last 3/4)
FOOTER_SEARCH_END = 0.95        # End at 95%
FOOTER_LINE_MIN_LENGTH = 0.15   # Minimum 15% of page width
FOOTER_LINE_MAX_LENGTH = 0.35   # Maximum 35% of page width (short lines)
FOOTER_TEXT_DENSITY_DROP = 0.15 # 15% density drop indicates footer region
FOOTER_SAFETY_MARGIN = 20       # Pixels above detected footer

# Page 1 cropping
PAGE_1_TOP_FALLBACK = 0.27

# Debug
DEBUG_FOOTER_FOLDER = "footer_inspection"


# === Binarization Functions ===

def binarize_image(image: Image.Image, method: str = 'otsu') -> np.ndarray:
    """
    Binarizes image using best practices for OCR.

    Args:
        image: PIL Image
        method: 'otsu' (adaptive) or 'fixed' threshold

    Returns:
        Binary image (numpy array)
    """
    # Convert to grayscale
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)

    if method == 'otsu':
        # Otsu's method - automatically finds optimal threshold
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif method == 'adaptive':
        # Adaptive threshold - handles varying lighting
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
    else:
        # Fixed threshold
        _, binary = cv2.threshold(gray, BINARY_THRESHOLD, 255, cv2.THRESH_BINARY)

    return binary


def denoise_binary(binary: np.ndarray) -> np.ndarray:
    """
    Removes noise from binary image.

    Args:
        binary: Binary image

    Returns:
        Denoised binary image
    """
    # Remove small noise with morphological operations
    kernel = np.ones((3, 3), np.uint8)

    # Opening: removes small white noise
    denoised = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=1)

    # Closing: fills small black holes
    denoised = cv2.morphologyEx(denoised, cv2.MORPH_CLOSE, kernel, iterations=1)

    return denoised


# === Logo Detection (Density-based Black Square) ===

def detect_black_square_logo(image: Image.Image,
                             debug_path: Optional[str] = None) -> Optional[int]:
    """
    Detects black square logo at top of page using density analysis.

    Args:
        image: PIL Image
        debug_path: Optional path for debug visualization

    Returns:
        Y-coordinate of logo bottom, or None if not detected
    """
    # Binarize image
    binary = binarize_image(image, method='otsu')
    binary = denoise_binary(binary)

    # Search only in top region
    height = image.height
    search_height = int(height * LOGO_SEARCH_HEIGHT)
    top_region = binary[:search_height, :]

    # Invert for contour detection (find black regions on white background)
    inverted = cv2.bitwise_not(top_region)

    # Find contours
    contours, _ = cv2.findContours(inverted, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    # Filter contours by size and shape
    candidates = []
    for contour in contours:
        # Get bounding box
        x, y, w, h = cv2.boundingRect(contour)

        # Size filter
        if not (LOGO_MIN_SIZE <= w <= LOGO_MAX_SIZE and LOGO_MIN_SIZE <= h <= LOGO_MAX_SIZE):
            continue

        # Square shape filter (aspect ratio close to 1)
        aspect_ratio = w / h if h > 0 else 0
        if not (0.8 <= aspect_ratio <= 1.2):
            continue

        # Density filter: check if region is mostly black
        roi = inverted[y:y+h, x:x+w]
        black_pixel_ratio = np.sum(roi > 127) / (w * h)

        if black_pixel_ratio >= LOGO_DENSITY_THRESHOLD:
            candidates.append({
                'x': x, 'y': y, 'w': w, 'h': h,
                'bottom': y + h,
                'density': black_pixel_ratio,
                'area': w * h
            })

    if not candidates:
        return None

    # Select the candidate with highest density and largest area
    best_candidate = max(candidates, key=lambda c: (c['density'], c['area']))
    logo_bottom = best_candidate['bottom']

    # Debug visualization
    if debug_path:
        vis_img = cv2.cvtColor(top_region, cv2.COLOR_GRAY2BGR)

        # Draw all candidates in yellow
        for c in candidates:
            cv2.rectangle(vis_img, (c['x'], c['y']), (c['x']+c['w'], c['y']+c['h']),
                         (0, 255, 255), 2)

        # Draw selected logo in green
        cv2.rectangle(vis_img,
                     (best_candidate['x'], best_candidate['y']),
                     (best_candidate['x']+best_candidate['w'], best_candidate['y']+best_candidate['h']),
                     (0, 255, 0), 3)

        # Draw crop line
        cv2.line(vis_img, (0, logo_bottom), (image.width, logo_bottom), (255, 0, 255), 3)
        cv2.putText(vis_img, f"Logo: {best_candidate['density']:.2f} density",
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        os.makedirs(os.path.dirname(debug_path) or '.', exist_ok=True)
        cv2.imwrite(debug_path, vis_img)

    return logo_bottom


# === Footer Detection (Lines + Density) ===

def detect_footer_region(image: Image.Image,
                         filename_base: str = "page",
                         page_num: int = 1,
                         debug: bool = False) -> int:
    """
    Detects footer region using line detection + density analysis.
    Searches in the last 3/4 of the page.

    Args:
        image: PIL Image
        filename_base: Base name for debug files
        page_num: Page number
        debug: Enable debug visualizations

    Returns:
        Y-coordinate where footer starts
    """
    height = image.height
    width = image.width

    # Binarize image
    binary = binarize_image(image, method='otsu')

    # Search region: last 3/4 of page
    search_start_y = int(height * FOOTER_SEARCH_START)
    search_end_y = int(height * FOOTER_SEARCH_END)
    search_region = binary[search_start_y:search_end_y, :]

    # === STEP 1: Detect short horizontal lines (footer separators) ===

    # Use Hough line detection on inverted image
    inverted = cv2.bitwise_not(search_region)
    lines = cv2.HoughLinesP(
        inverted,
        rho=1,
        theta=np.pi/180,
        threshold=50,
        minLineLength=int(width * FOOTER_LINE_MIN_LENGTH),
        maxLineGap=10
    )

    detected_lines = []
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]

            # Filter: horizontal lines only
            if abs(y2 - y1) > 5:
                continue

            # Filter: short to medium lines (footer separators, not full-width lines)
            line_length = abs(x2 - x1)
            line_length_ratio = line_length / width

            if FOOTER_LINE_MIN_LENGTH <= line_length_ratio <= FOOTER_LINE_MAX_LENGTH:
                # Adjust Y to full image coordinates
                actual_y = y1 + search_start_y
                detected_lines.append({
                    'y': actual_y,
                    'x1': x1,
                    'x2': x2,
                    'length': line_length,
                    'length_ratio': line_length_ratio
                })

    # === STEP 2: Density analysis to find footer text region ===

    # Calculate text density by horizontal strips
    strip_height = 50  # Analyze in 50-pixel strips
    density_profile = []

    for y in range(search_start_y, search_end_y, strip_height):
        if y + strip_height > height:
            break

        strip = binary[y:y+strip_height, :]
        # Black pixel density (text)
        black_ratio = 1.0 - (np.sum(strip == 255) / strip.size)
        density_profile.append({
            'y': y,
            'density': black_ratio
        })

    # Find where density significantly drops (footer has sparser text)
    footer_by_density = None
    if len(density_profile) > 3:
        # Look for significant drop in density
        for i in range(len(density_profile) - 1):
            curr_density = density_profile[i]['density']
            next_density = density_profile[i+1]['density']

            # Significant drop indicates transition to footer
            if curr_density - next_density > FOOTER_TEXT_DENSITY_DROP:
                footer_by_density = density_profile[i]['y']
                break

    # === STEP 3: Combine line detection and density ===

    footer_y = None

    # Priority 1: If we found lines, use the topmost line
    if detected_lines:
        footer_y = min(detected_lines, key=lambda l: l['y'])['y']

    # Priority 2: If density drop found and no lines, use density
    elif footer_by_density is not None:
        footer_y = footer_by_density

    # Priority 3: Fallback to safe 70%
    else:
        footer_y = int(height * 0.70)

    # Apply safety margin
    footer_y = max(search_start_y, footer_y - FOOTER_SAFETY_MARGIN)

    # === DEBUG VISUALIZATION ===

    if debug:
        os.makedirs(DEBUG_FOOTER_FOLDER, exist_ok=True)

        # Create comprehensive debug image
        vis_img = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

        # Draw search region boundaries
        cv2.line(vis_img, (0, search_start_y), (width, search_start_y), (0, 255, 255), 2)
        cv2.line(vis_img, (0, search_end_y), (width, search_end_y), (0, 255, 255), 2)
        cv2.putText(vis_img, "Search Region (last 3/4)", (10, search_start_y - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        # Draw all detected lines
        if detected_lines:
            for line in detected_lines:
                color = (0, 255, 0) if line['y'] == min(detected_lines, key=lambda l: l['y'])['y'] else (255, 255, 0)
                cv2.line(vis_img, (line['x1'], line['y']), (line['x2'], line['y']), color, 3)
                cv2.putText(vis_img, f"{line['length_ratio']:.2f}",
                           (line['x1'], line['y'] - 10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

        # Draw density-based detection
        if footer_by_density:
            cv2.line(vis_img, (0, footer_by_density), (width, footer_by_density), (255, 0, 255), 2)
            cv2.putText(vis_img, "Density drop", (10, footer_by_density + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)

        # Draw final footer crop line
        cv2.line(vis_img, (0, footer_y), (width, footer_y), (0, 0, 255), 4)
        cv2.putText(vis_img, f"FOOTER CROP: {footer_y} ({footer_y/height*100:.1f}%)",
                   (10, footer_y - 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        # Save debug image
        debug_path = os.path.join(DEBUG_FOOTER_FOLDER,
                                 f"{filename_base}_page{page_num}_footer_analysis.png")
        cv2.imwrite(debug_path, vis_img)

        # Also save density profile visualization
        if density_profile:
            profile_img = np.ones((300, len(density_profile) * 10, 3), dtype=np.uint8) * 255
            for i, dp in enumerate(density_profile):
                bar_height = int(dp['density'] * 250)
                x = i * 10
                cv2.rectangle(profile_img, (x, 300 - bar_height), (x + 8, 300), (100, 100, 255), -1)

            profile_path = os.path.join(DEBUG_FOOTER_FOLDER,
                                       f"{filename_base}_page{page_num}_density_profile.png")
            cv2.imwrite(profile_path, profile_img)

    return footer_y


# === Content Start Detection (Page 1) ===

def detect_content_start_dynamic(image: Image.Image) -> int:
    """
    Dynamically detects where main content starts on page 1.

    Args:
        image: PIL Image

    Returns:
        Y-coordinate where content starts
    """
    try:
        # Binarize for better OCR
        binary = binarize_image(image, method='otsu')
        binary_pil = Image.fromarray(binary)

        # Get OCR data
        ocr_data = pytesseract.image_to_data(binary_pil, lang=OCR_LANG,
                                            output_type=pytesseract.Output.DICT)

        height = image.height
        min_y = int(height * 0.20)
        max_y = int(height * 0.35)

        # Find first substantial text block
        text_blocks = []
        for i in range(len(ocr_data['text'])):
            text = ocr_data['text'][i].strip()
            conf = int(ocr_data['conf'][i])

            if text and conf > 30 and len(text) > 10:
                top = ocr_data['top'][i]
                if min_y <= top <= max_y:
                    text_blocks.append(top)

        if text_blocks:
            first_block_y = min(text_blocks)
            return max(min_y, first_block_y - 30)  # 30px buffer

    except Exception:
        pass

    # Fallback
    return int(image.height * PAGE_1_TOP_FALLBACK)


# === Orientation Check ===

def is_vertical_page(image: Image.Image) -> bool:
    """Check if page is vertical/portrait."""
    return image.height > image.width


# === Cropping Logic ===

def get_crop_boundaries(image: Image.Image,
                       page_num: int,
                       filename_base: str,
                       debug: bool = False) -> Tuple[int, int]:
    """
    Determines crop boundaries for a page.

    Args:
        image: PIL Image
        page_num: Page number (1-indexed)
        filename_base: Base name for debug files
        debug: Enable debug mode

    Returns:
        (top_y, bottom_y) coordinates
    """
    height = image.height

    # === TOP CROPPING ===
    if page_num == 1:
        # Page 1: Dynamic content detection
        top_y = detect_content_start_dynamic(image)
    else:
        # Page 2+: Detect black square logo
        debug_path = None
        if debug:
            os.makedirs(DEBUG_FOOTER_FOLDER, exist_ok=True)
            debug_path = os.path.join(DEBUG_FOOTER_FOLDER,
                                     f"{filename_base}_page{page_num}_logo.png")

        logo_bottom = detect_black_square_logo(image, debug_path=debug_path)

        if logo_bottom is not None:
            top_y = logo_bottom + 10
        else:
            top_y = int(height * 0.08)  # Fallback

    # === BOTTOM CROPPING (FOOTER) ===
    bottom_y = detect_footer_region(image, filename_base, page_num, debug=debug)

    # Ensure valid boundaries
    bottom_y = max(bottom_y, top_y + 100)

    return top_y, bottom_y


# === Text Extraction ===

def extract_text_from_page(image: Image.Image, lang: str = OCR_LANG) -> str:
    """
    Extracts text from image using binarization for improved OCR.

    Args:
        image: PIL Image (cropped)
        lang: OCR language

    Returns:
        Extracted text
    """
    # Binarize for better OCR quality
    binary = binarize_image(image, method='otsu')
    binary = denoise_binary(binary)

    # Convert back to PIL Image
    binary_pil = Image.fromarray(binary)

    # Extract text
    text = pytesseract.image_to_string(binary_pil, lang=lang)

    return text.strip()


# === Main Extraction Function ===

def extract_from_pdf(pdf_path: str,
                    dpi: int = OCR_DPI,
                    lang: str = OCR_LANG,
                    debug: bool = False) -> List[Dict[str, any]]:
    """
    Extracts text from scanned PDF with page-level records.

    Args:
        pdf_path: Path to PDF
        dpi: Resolution
        lang: OCR language
        debug: Enable debug mode

    Returns:
        List of page records: [{"filename": ..., "page": ..., "text": ...}, ...]
    """
    filename = os.path.basename(pdf_path)
    filename_base = filename.replace('.pdf', '')

    print(f"\n[Processing] {filename}")

    try:
        # Convert PDF to images
        images = convert_from_path(pdf_path, dpi=dpi)

        page_records = []

        for page_num, image in enumerate(images, start=1):
            # Check orientation
            if not is_vertical_page(image):
                print(f"  [Page {page_num}] Skipped (horizontal)")
                continue

            print(f"  [Page {page_num}] Extracting...", end=" ")

            # Get crop boundaries
            top_y, bottom_y = get_crop_boundaries(image, page_num, filename_base, debug=debug)

            # Crop image
            cropped_img = image.crop((0, top_y, image.width, bottom_y))

            # Save cropped image if debug
            if debug:
                os.makedirs(DEBUG_FOOTER_FOLDER, exist_ok=True)
                crop_path = os.path.join(DEBUG_FOOTER_FOLDER,
                                        f"{filename_base}_page{page_num}_cropped.png")
                cropped_img.save(crop_path)

            # Extract text
            page_text = extract_text_from_page(cropped_img, lang=lang)

            if page_text:
                page_records.append({
                    "filename": filename,
                    "page": page_num,
                    "text": page_text
                })
                print(f"({len(page_text)} chars)")
            else:
                print("(empty)")

        print(f"  [Total] {len(page_records)} pages extracted\n")

        return page_records

    except Exception as e:
        print(f"  [Error] {e}\n")
        import traceback
        traceback.print_exc()
        return []


# === Batch Processing ===

def process_all_pdfs(folder_path: str,
                    output_json: str = "data/raw/scanned_pdfs_extracted_text.json",
                    debug: bool = False) -> List[Dict[str, any]]:
    """
    Processes all PDFs in folder and saves to JSON.

    Args:
        folder_path: Folder with scanned PDFs
        output_json: Output JSON file path
        debug: Enable debug mode

    Returns:
        List of all page records
    """
    print("="*80)
    print("SCANNED PDF TEXT EXTRACTION - OCR Best Practices")
    print("="*80)
    print("\nFeatures:")
    print("- Binarization with Otsu's method")
    print("- Density-based black square logo detection")
    print("- Enhanced footer detection (lines + density, last 3/4)")
    print("- Footer inspection debug folder")
    print("- JSON output with page-level records")
    print("="*80)

    # Get PDF files
    pdf_files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')])
    print(f"\n[Found] {len(pdf_files)} PDF files\n")

    # Process all PDFs
    all_records = []

    for idx, pdf_file in enumerate(pdf_files, start=1):
        print(f"--- PDF {idx}/{len(pdf_files)} ---")
        pdf_path = os.path.join(folder_path, pdf_file)
        page_records = extract_from_pdf(pdf_path, debug=debug)
        all_records.extend(page_records)

    # Save to JSON
    os.makedirs(os.path.dirname(output_json), exist_ok=True)
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print("\n" + "="*80)
    print("EXTRACTION COMPLETE")
    print("="*80)
    print(f"Output: {output_json}")
    print(f"Total pages extracted: {len(all_records)}")
    print(f"Total documents: {len(set(r['filename'] for r in all_records))}")

    if debug:
        print(f"\nDebug folder: {DEBUG_FOOTER_FOLDER}/")
        print("Review footer detection visualizations to verify accuracy")

    return all_records


# === Entry Point ===

if __name__ == "__main__":
    SCANNED_FOLDER = "data/raw/scanned"
    OUTPUT_JSON = "data/raw/scanned_pdfs_extracted_text.json"

    # Run extraction with debug enabled
    records = process_all_pdfs(
        folder_path=SCANNED_FOLDER,
        output_json=OUTPUT_JSON,
        debug=True
    )

    # Show sample
    if records:
        print("\n" + "="*80)
        print("SAMPLE OUTPUT")
        print("="*80)
        sample = records[0]
        print(f"\nFilename: {sample['filename']}")
        print(f"Page: {sample['page']}")
        print(f"\nFirst 500 characters:")
        print(sample['text'][:500])
