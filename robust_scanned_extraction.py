"""
Robust OCR extraction for scanned PDFs - Simplified raw text extraction.

Key features:
1. Red CF logo detection for page 2+ cropping
2. Dynamic content detection for page 1 (handles rotation)
3. Orientation filtering (exclude horizontal pages)
4. Footer line detection (primary strategy)
5. Raw text extraction with \n\n paragraph markers
6. No cleaning, no segmentation (deferred to next stage)
"""

import os
import re
import numpy as np
import cv2
import pandas as pd
import pytesseract
from pdf2image import convert_from_path
from PIL import Image
from typing import List, Dict, Tuple, Optional, Any


# === Configuration Parameters ===

OCR_DPI = 300
OCR_LANG = 'spa'

# Cropping parameters
PAGE_1_TOP_FALLBACK = 0.27      # Increased from 25% to 27% for rotation tolerance
PAGE_2_TOP_FALLBACK = 0.08      # Fallback if logo not detected

# Footer detection
FOOTER_SEARCH_MIN = 0.55
FOOTER_SEARCH_MAX = 0.90
FOOTER_FALLBACK = 0.70
FOOTER_SAFETY_MARGIN = 15

# Line detection (Hough)
MIN_LINE_LENGTH_RATIO = 0.17
HOUGH_THRESHOLD = 80
MAX_LINE_GAP = 5

# Logo detection (for page 2+)
LOGO_SEARCH_HEIGHT = 0.15       # Search top 15% for red logo
RED_HSV_LOWER = np.array([0, 100, 100])    # Red color range (HSV)
RED_HSV_UPPER = np.array([10, 255, 255])
RED_HSV_LOWER2 = np.array([170, 100, 100]) # Red wraps around in HSV
RED_HSV_UPPER2 = np.array([180, 255, 255])

# Paragraph detection
PARAGRAPH_SPACING_THRESHOLD = 20  # Pixels - vertical gap to insert \n\n


# === Utility Functions ===

def is_vertical_page(image: Image.Image) -> bool:
    """
    Checks if page is vertical/portrait orientation.

    Args:
        image: PIL Image

    Returns:
        True if portrait (height > width), False if landscape
    """
    return image.height > image.width


def detect_red_logo_baseline(image: Image.Image, debug_path: Optional[str] = None) -> Optional[int]:
    """
    Detects the red CF logo and returns its bottom Y-coordinate.

    Args:
        image: PIL Image
        debug_path: Optional path to save debug visualization

    Returns:
        Y-coordinate of logo bottom, or None if not detected
    """
    # Convert to numpy array and HSV color space
    img_array = np.array(image)
    hsv = cv2.cvtColor(img_array, cv2.COLOR_RGB2HSV)

    # Search only in top portion
    search_height = int(image.height * LOGO_SEARCH_HEIGHT)
    hsv_crop = hsv[:search_height, :, :]

    # Create mask for red color (two ranges due to HSV wrap-around)
    mask1 = cv2.inRange(hsv_crop, RED_HSV_LOWER, RED_HSV_UPPER)
    mask2 = cv2.inRange(hsv_crop, RED_HSV_LOWER2, RED_HSV_UPPER2)
    red_mask = cv2.bitwise_or(mask1, mask2)

    # Find contours in red regions
    contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    # Find the largest red contour (likely the logo)
    largest_contour = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest_contour)

    # Filter by minimum area (logo should be substantial)
    min_area = (image.width * image.height) * 0.0005  # At least 0.05% of page
    if area < min_area:
        return None

    # Get bounding box
    x, y, w, h = cv2.boundingRect(largest_contour)

    # Verify it's roughly square (logo is square)
    aspect_ratio = w / h if h > 0 else 0
    if not (0.7 <= aspect_ratio <= 1.5):  # Allow some tolerance
        return None

    # Return bottom Y-coordinate
    logo_bottom = y + h

    # Debug visualization
    if debug_path:
        vis_img = img_array[:search_height, :, :].copy()
        cv2.rectangle(vis_img, (x, y), (x+w, y+h), (0, 255, 0), 3)
        cv2.line(vis_img, (0, logo_bottom), (image.width, logo_bottom), (255, 0, 255), 3)

        os.makedirs(os.path.dirname(debug_path), exist_ok=True)
        cv2.imwrite(debug_path, cv2.cvtColor(vis_img, cv2.COLOR_RGB2BGR))

    return logo_bottom


def detect_content_start_y(image: Image.Image,
                          min_y_ratio: float = 0.20,
                          max_y_ratio: float = 0.35) -> int:
    """
    Dynamically detects where main content starts (for page 1).
    Uses OCR to find first substantial text block.

    Args:
        image: PIL Image
        min_y_ratio: Minimum Y position to search (skip institutional header)
        max_y_ratio: Maximum Y position to search

    Returns:
        Y-coordinate where content begins
    """
    try:
        # Get detailed OCR data with bounding boxes
        ocr_data = pytesseract.image_to_data(image, lang=OCR_LANG, output_type=pytesseract.Output.DICT)

        height = image.height
        min_y = int(height * min_y_ratio)
        max_y = int(height * max_y_ratio)

        # Find text blocks in search region
        text_blocks = []
        for i in range(len(ocr_data['text'])):
            text = ocr_data['text'][i].strip()
            conf = int(ocr_data['conf'][i])

            if text and conf > 30 and len(text) > 10:  # Substantial text
                top = ocr_data['top'][i]
                if min_y <= top <= max_y:
                    text_blocks.append(top)

        if text_blocks:
            # Use the first text block, with small buffer above
            first_block_y = min(text_blocks)
            return max(min_y, first_block_y - 20)  # 20px buffer

    except Exception:
        pass

    # Fallback to conservative fixed ratio
    return int(image.height * PAGE_1_TOP_FALLBACK)


def detect_footer_line_hough(image: Image.Image,
                             y_range: Tuple[float, float] = (FOOTER_SEARCH_MIN, FOOTER_SEARCH_MAX),
                             debug_path: Optional[str] = None) -> Optional[int]:
    """
    Detects horizontal footer separator line using Hough transform.

    Args:
        image: PIL Image
        y_range: Vertical search range (proportional)
        debug_path: Optional debug visualization path

    Returns:
        Y-coordinate of detected line, or None if not found
    """
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY_INV)

    lines = cv2.HoughLinesP(
        thresh, 1, np.pi / 180,
        threshold=HOUGH_THRESHOLD,
        minLineLength=int(image.width * MIN_LINE_LENGTH_RATIO),
        maxLineGap=MAX_LINE_GAP
    )

    if lines is None:
        return None

    height = image.height
    min_y, max_y = int(height * y_range[0]), int(height * y_range[1])

    # Filter horizontal lines in range
    horizontal_lines = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if abs(y2 - y1) < 10 and min_y <= y1 <= max_y:
            horizontal_lines.append((y1, x1, x2))

    if not horizontal_lines:
        return None

    # Use the first (topmost) line
    detected_line_y = min(horizontal_lines, key=lambda l: l[0])[0]

    # Debug visualization
    if debug_path:
        vis_img = np.array(image).copy()
        for y, x1, x2 in horizontal_lines:
            color = (255, 0, 0) if y == detected_line_y else (0, 255, 255)
            cv2.line(vis_img, (x1, y), (x2, y), color, 5)

        crop_y = detected_line_y - FOOTER_SAFETY_MARGIN
        cv2.line(vis_img, (0, crop_y), (image.width, crop_y), (255, 0, 255), 3)

        os.makedirs(os.path.dirname(debug_path), exist_ok=True)
        cv2.imwrite(debug_path, cv2.cvtColor(vis_img, cv2.COLOR_RGB2BGR))

    return detected_line_y


def get_crop_boundaries(image: Image.Image,
                       page_num: int,
                       debug_folder: Optional[str] = None,
                       filename_base: str = "page") -> Tuple[int, int]:
    """
    Determines optimal crop boundaries for a page.

    Args:
        image: PIL Image
        page_num: Page number (1-indexed)
        debug_folder: Optional folder for debug images
        filename_base: Base filename for debug outputs

    Returns:
        Tuple of (top_y, bottom_y) coordinates
    """
    height = image.height

    # === TOP CROPPING ===
    if page_num == 1:
        # Page 1: Detect content start dynamically
        debug_path = None
        if debug_folder:
            debug_path = os.path.join(debug_folder, f"{filename_base}_page1_content_detect.png")
        top_y = detect_content_start_y(image)
    else:
        # Pages 2+: Try to detect red CF logo
        debug_path = None
        if debug_folder:
            debug_path = os.path.join(debug_folder, f"{filename_base}_page{page_num}_logo.png")

        logo_bottom = detect_red_logo_baseline(image, debug_path=debug_path)

        if logo_bottom is not None:
            # Use logo baseline + small margin
            top_y = logo_bottom + 10
        else:
            # Fallback to fixed ratio
            top_y = int(height * PAGE_2_TOP_FALLBACK)

    # === BOTTOM CROPPING (FOOTER) ===
    debug_path = None
    if debug_folder:
        debug_path = os.path.join(debug_folder, f"{filename_base}_page{page_num}_footer_lines.png")

    footer_line_y = detect_footer_line_hough(image, debug_path=debug_path)

    if footer_line_y is not None:
        # Use detected line with safety margin
        bottom_y = footer_line_y - FOOTER_SAFETY_MARGIN
    else:
        # Fallback to safe default
        bottom_y = int(height * FOOTER_FALLBACK)

    # Ensure valid boundaries
    bottom_y = max(bottom_y, top_y + 100)

    return top_y, bottom_y


def extract_text_with_paragraph_markers(image: Image.Image, lang: str = OCR_LANG) -> str:
    """
    Extracts text from image and inserts \\n\\n at paragraph boundaries.
    Uses OCR layout analysis to detect vertical spacing.

    Args:
        image: PIL Image (cropped region)
        lang: OCR language

    Returns:
        Raw text with \\n\\n paragraph markers
    """
    try:
        # Get detailed OCR data with line positions
        ocr_data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)

        # Group text by lines (by vertical position)
        lines = []
        current_line = {'text': '', 'top': 0, 'bottom': 0, 'conf': []}
        prev_top = -1

        for i in range(len(ocr_data['text'])):
            text = ocr_data['text'][i]
            conf = int(ocr_data['conf'][i])

            if conf < 30 or not text.strip():  # Skip low confidence
                continue

            top = ocr_data['top'][i]
            height = ocr_data['height'][i]
            bottom = top + height

            # Check if same line (within 10 pixels vertically)
            if prev_top >= 0 and abs(top - prev_top) > 10:
                # New line - save previous
                if current_line['text']:
                    lines.append(current_line)
                current_line = {'text': text, 'top': top, 'bottom': bottom, 'conf': [conf]}
            else:
                # Same line - append text
                current_line['text'] += ' ' + text
                current_line['bottom'] = max(current_line['bottom'], bottom)
                current_line['conf'].append(conf)

            prev_top = top

        # Add last line
        if current_line['text']:
            lines.append(current_line)

        # Build text with paragraph markers
        result_text = []
        prev_bottom = 0

        for line in lines:
            text = line['text'].strip()
            if not text:
                continue

            top = line['top']

            # Check vertical spacing from previous line
            if prev_bottom > 0:
                vertical_gap = top - prev_bottom

                # Insert \n\n for paragraph breaks (large vertical gaps)
                if vertical_gap > PARAGRAPH_SPACING_THRESHOLD:
                    result_text.append('\n\n')
                else:
                    result_text.append('\n')

            result_text.append(text)
            prev_bottom = line['bottom']

        return ''.join(result_text)

    except Exception as e:
        print(f"    [Warning] Layout-based extraction failed: {e}")
        # Fallback to simple extraction
        return pytesseract.image_to_string(image, lang=lang)


def extract_from_scanned_pdf(pdf_path: str,
                             dpi: int = OCR_DPI,
                             lang: str = OCR_LANG,
                             debug: bool = False,
                             debug_folder: str = "debug_extraction") -> Dict[str, Any]:
    """
    Extracts raw text from a scanned PDF with paragraph markers.

    Args:
        pdf_path: Path to PDF file
        dpi: Resolution for conversion
        lang: OCR language
        debug: Enable debug visualizations
        debug_folder: Folder for debug outputs

    Returns:
        Dictionary with extracted data
    """
    filename = os.path.basename(pdf_path)
    filename_base = filename.replace('.pdf', '')

    print(f"\n[Processing] {filename}")

    try:
        # Convert PDF to images
        images = convert_from_path(pdf_path, dpi=dpi)

        page_texts = []
        pages_processed = []

        for page_num, image in enumerate(images, start=1):
            # Check orientation - skip horizontal pages
            if not is_vertical_page(image):
                print(f"  [Page {page_num}] Skipped (horizontal orientation)")
                continue

            print(f"  [Page {page_num}] Extracting...", end=" ")

            # Get crop boundaries
            top_y, bottom_y = get_crop_boundaries(
                image, page_num,
                debug_folder=debug_folder if debug else None,
                filename_base=filename_base
            )

            # Crop image
            cropped_img = image.crop((0, top_y, image.width, bottom_y))

            # Save cropped image if debug
            if debug:
                os.makedirs(debug_folder, exist_ok=True)
                crop_path = os.path.join(debug_folder, f"{filename_base}_page{page_num}_cropped.png")
                cropped_img.save(crop_path)

            # Extract text with paragraph markers
            page_text = extract_text_with_paragraph_markers(cropped_img, lang=lang)

            if page_text.strip():
                page_texts.append(page_text)
                pages_processed.append(page_num)
                print(f"({len(page_text)} chars)")
            else:
                print("(empty)")

        # Combine all pages with page separators
        full_text = '\n\n--- PAGE BREAK ---\n\n'.join(page_texts)

        print(f"  [Total] {len(pages_processed)} pages, {len(full_text)} characters\n")

        return {
            'filename': filename,
            'pages_processed': pages_processed,
            'total_pages': len(images),
            'text': full_text,
            'success': True
        }

    except Exception as e:
        print(f"  [Error] {e}\n")
        import traceback
        traceback.print_exc()
        return {
            'filename': filename,
            'pages_processed': [],
            'total_pages': 0,
            'text': '',
            'success': False,
            'error': str(e)
        }


def process_folder(folder_path: str,
                  metadata_csv: Optional[str] = None,
                  output_csv: str = "raw_extracted_text.csv",
                  debug: bool = False) -> pd.DataFrame:
    """
    Batch processes all scanned PDFs in a folder.

    Args:
        folder_path: Folder with scanned PDFs
        metadata_csv: Optional metadata CSV path
        output_csv: Output CSV file path
        debug: Enable debug mode

    Returns:
        DataFrame with extracted text
    """
    print("="*80)
    print("ROBUST SCANNED PDF TEXT EXTRACTION")
    print("="*80)
    print("\nFeatures:")
    print("- Red CF logo detection for page 2+ cropping")
    print("- Dynamic content detection for page 1")
    print("- Horizontal page filtering")
    print("- Footer line detection with fallback")
    print("- Raw text extraction with \\n\\n paragraph markers")
    print("="*80)

    # Get PDF files
    pdf_files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')])
    print(f"\n[Found] {len(pdf_files)} PDF files")

    # Process each PDF
    results = []
    for idx, pdf_file in enumerate(pdf_files, start=1):
        print(f"\n--- PDF {idx}/{len(pdf_files)} ---")
        pdf_path = os.path.join(folder_path, pdf_file)
        result = extract_from_scanned_pdf(pdf_path, debug=debug)
        results.append(result)

    # Create DataFrame
    df = pd.DataFrame(results)

    # Merge with metadata if provided
    if metadata_csv and os.path.exists(metadata_csv):
        print(f"\n[Merging] with metadata from {metadata_csv}")
        metadata_df = pd.read_csv(metadata_csv)
        df = df.merge(
            metadata_df[['pdf_filename', 'doc_title', 'date']],
            left_on='filename',
            right_on='pdf_filename',
            how='left'
        )

    # Save to CSV
    os.makedirs(os.path.dirname(output_csv) if os.path.dirname(output_csv) else '.', exist_ok=True)
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')

    print("\n" + "="*80)
    print("EXTRACTION COMPLETE")
    print("="*80)
    print(f"Output saved: {output_csv}")
    print(f"Total documents: {len(df)}")
    print(f"Successful: {df['success'].sum()}")
    print(f"Failed: {(~df['success']).sum()}")

    return df


if __name__ == "__main__":
    # Test configuration
    SCANNED_FOLDER = "data/raw/scanned"
    METADATA_CSV = "metadata/cf_pdfs_metadata.csv"
    OUTPUT_CSV = "output/raw_extracted_text.csv"

    # Run extraction
    df = process_folder(
        folder_path=SCANNED_FOLDER,
        metadata_csv=METADATA_CSV,
        output_csv=OUTPUT_CSV,
        debug=True
    )

    # Show sample
    if not df.empty and df['success'].any():
        print("\n" + "="*80)
        print("SAMPLE OUTPUT")
        print("="*80)
        sample = df[df['success']].iloc[0]
        print(f"\nDocument: {sample['filename']}")
        print(f"Pages processed: {sample['pages_processed']}")
        print(f"\nFirst 500 characters of text:")
        print(sample['text'][:500])
        print("\n...")
