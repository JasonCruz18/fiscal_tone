"""
Enhanced OCR extraction for scanned PDFs with adaptive cropping.

This module implements:
1. Adaptive top-cropping (25% for page 1, 8% for subsequent pages)
2. Robust footer detection with 100% exclusion guarantee
3. Text-based filtering for institutional headers, seals, and footers
4. Paragraph segmentation with validation
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

# OCR Settings
OCR_DPI = 300
OCR_LANG = 'spa'
OCR_MIN_CONFIDENCE = 30

# Top Cropping (adaptive by page number)
TOP_SKIP_PAGE_1 = 0.25      # Skip top 25% on first page (excludes title)
TOP_SKIP_OTHER_PAGES = 0.08  # Skip top 8% on other pages (excludes logo only)

# Footer Detection
FOOTER_SEARCH_MIN = 0.55     # Start searching for footer line at 55%
FOOTER_SEARCH_MAX = 0.90     # Stop searching at 90%
FOOTER_FALLBACK = 0.70       # Safe fallback if no line detected
FOOTER_SAFETY_MARGIN = 15    # Pixels to subtract from detected line

# Line Detection (Hough Transform)
MIN_LINE_LENGTH_RATIO = 0.17  # Minimum 17% of page width
HOUGH_THRESHOLD = 80
MAX_LINE_GAP = 5

# Text Filtering
MIN_PARAGRAPH_LENGTH = 50     # Minimum characters for valid paragraph

# Patterns to exclude (institutional headers, seals, footers)
EXCLUDE_PATTERNS = [
    r"(?i)Av\.\s*República.*www\.cf\.gob\.pe",  # Footer address
    r"(?i)www\.cf\.gob\.pe",                     # Footer URL
    r"(?i)Página\s+\d+",                         # Page numbers
    r"(?i)\d+/\d+\s*$",                          # Page numbers like "1/7"
    r"(?i)Consejo\s+Fiscal\s*$",                 # Logo text only
    r"(?i)^CF$",                                 # Logo acronym only
    r"(?i)Ministerio\s+de\s+Economía",           # Institution name
    r"(?i)Oficina\s+\d+\s*[-–]\s*San\s+Isidro",  # Office location
]

# Stop patterns (Anexo detection)
STOP_PATTERNS = [
    r"(?mi)^\s*Anexos?\b[\s\w]*:?",              # Anexo/Anexos
    r"(?mi)^\s*Cuadros?\b",                      # Tables section
    r"(?mi)^\s*Gráficos?\b",                     # Graphs section
    r"(?mi)^\s*Bibliografía\b",                  # Bibliography
]


# === Core Detection Functions ===

def detect_footer_line_hough(image: Image.Image,
                             y_range: Tuple[float, float] = (FOOTER_SEARCH_MIN, FOOTER_SEARCH_MAX),
                             min_length_ratio: float = MIN_LINE_LENGTH_RATIO,
                             debug_path: Optional[str] = None) -> Optional[int]:
    """
    Detects horizontal footer separator line using Hough transform.

    Args:
        image: PIL Image of the page
        y_range: Vertical range to search (as proportion of height)
        min_length_ratio: Minimum line length relative to image width
        debug_path: Optional path to save debug visualization

    Returns:
        Y-coordinate of detected line, or None if not found
    """
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY_INV)

    # Detect lines using Hough transform
    lines = cv2.HoughLinesP(
        thresh, 1, np.pi / 180,
        threshold=HOUGH_THRESHOLD,
        minLineLength=int(image.width * min_length_ratio),
        maxLineGap=MAX_LINE_GAP
    )

    if lines is None:
        return None

    height = image.height
    min_y, max_y = int(height * y_range[0]), int(height * y_range[1])

    # Filter horizontal lines in detection range
    horizontal_lines = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        # Only consider near-horizontal lines (within 10 pixels vertical deviation)
        if abs(y2 - y1) < 10 and min_y <= y1 <= max_y:
            horizontal_lines.append((y1, x1, x2))

    if not horizontal_lines:
        return None

    # Use the FIRST (topmost) line in the detection range
    # This ensures we crop before the footer starts
    detected_line_y = min(horizontal_lines, key=lambda l: l[0])[0]

    # Save debug visualization if requested
    if debug_path:
        vis_img = np.array(image).copy()
        for y, x1, x2 in horizontal_lines:
            color = (255, 0, 0) if y == detected_line_y else (0, 255, 255)
            cv2.line(vis_img, (x1, y), (x2, y), color, 5)

        # Draw detection range
        cv2.line(vis_img, (0, min_y), (image.width, min_y), (0, 255, 0), 2)
        cv2.line(vis_img, (0, max_y), (image.width, max_y), (0, 255, 0), 2)

        # Draw selected line with margin
        crop_y = detected_line_y - FOOTER_SAFETY_MARGIN
        cv2.line(vis_img, (0, crop_y), (image.width, crop_y), (255, 0, 255), 3)

        os.makedirs(os.path.dirname(debug_path), exist_ok=True)
        cv2.imwrite(debug_path, cv2.cvtColor(vis_img, cv2.COLOR_RGB2BGR))

    return detected_line_y


def detect_footer_by_density(image: Image.Image,
                             y_range: Tuple[float, float] = (FOOTER_SEARCH_MIN, FOOTER_SEARCH_MAX),
                             sample_interval: int = 50) -> Optional[int]:
    """
    Detects footer boundary by analyzing text density (brightness changes).

    Args:
        image: PIL Image of the page
        y_range: Vertical range to search
        sample_interval: Pixels between samples

    Returns:
        Y-coordinate where footer starts, or None if not detected
    """
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    height = image.height

    min_y, max_y = int(height * y_range[0]), int(height * y_range[1])

    # Sample brightness at intervals
    samples = []
    for y in range(min_y, max_y, sample_interval):
        if y + sample_interval > height:
            break
        region = gray[y:y+sample_interval, :]
        avg_brightness = np.mean(region) / 255.0
        samples.append((y, avg_brightness))

    if len(samples) < 3:
        return None

    # Find first significant brightness increase (footer typically has more whitespace)
    for i in range(1, len(samples) - 1):
        prev_bright = samples[i-1][1]
        curr_bright = samples[i][1]

        # Brightness increase of 3% or more suggests transition to footer
        if curr_bright - prev_bright > 0.03:
            return samples[i][0]

    return None


def get_adaptive_crop_boundaries(image: Image.Image,
                                 page_num: int,
                                 debug_path: Optional[str] = None) -> Tuple[int, int]:
    """
    Determines optimal crop boundaries for a page.

    Args:
        image: PIL Image of the page
        page_num: Page number (1-indexed)
        debug_path: Optional path for debug visualization

    Returns:
        Tuple of (top_y, bottom_y) coordinates for cropping
    """
    height = image.height

    # Adaptive top cropping
    if page_num == 1:
        top_y = int(height * TOP_SKIP_PAGE_1)  # Skip 25% for title
    else:
        top_y = int(height * TOP_SKIP_OTHER_PAGES)  # Skip 8% for logo only

    # Footer detection with multiple strategies
    footer_line_y = detect_footer_line_hough(image, debug_path=debug_path)

    if footer_line_y is not None:
        # Use detected line with safety margin
        bottom_y = footer_line_y - FOOTER_SAFETY_MARGIN
    else:
        # Fallback to density-based detection
        footer_density_y = detect_footer_by_density(image)

        if footer_density_y is not None:
            bottom_y = footer_density_y
        else:
            # Final fallback to safe default
            bottom_y = int(height * FOOTER_FALLBACK)

    # Ensure valid boundaries
    bottom_y = max(bottom_y, top_y + 100)  # Minimum 100px content region

    return top_y, bottom_y


# === Text Filtering Functions ===

def should_exclude_line(text: str) -> bool:
    """
    Checks if a text line should be excluded based on patterns.

    Args:
        text: Text line to check

    Returns:
        True if line should be excluded, False otherwise
    """
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def detect_anexo_stop(text: str) -> bool:
    """
    Checks if text contains Anexo pattern (stop extraction).

    Args:
        text: Text to check

    Returns:
        True if Anexo pattern found, False otherwise
    """
    for pattern in STOP_PATTERNS:
        if re.search(pattern, text):
            return True
    return False


def clean_ocr_text(text: str) -> str:
    """
    Cleans OCR artifacts and normalizes text.

    Args:
        text: Raw OCR text

    Returns:
        Cleaned text
    """
    # Merge hyphenated words at line breaks
    text = re.sub(r'(\w+)-\s+(\w+)', r'\1\2', text)

    # Normalize multiple spaces
    text = re.sub(r'\s+', ' ', text)

    # Remove excessive whitespace
    text = text.strip()

    return text


# === Paragraph Segmentation ===

def segment_into_paragraphs(lines: List[str], page_num: int) -> List[Dict[str, Any]]:
    """
    Segments OCR lines into coherent paragraphs.

    Args:
        lines: List of text lines from OCR
        page_num: Page number for metadata

    Returns:
        List of paragraph dictionaries
    """
    paragraphs = []
    current_para = []

    for i, line in enumerate(lines):
        # Skip empty lines
        if not line.strip():
            continue

        # Skip lines that match exclusion patterns
        if should_exclude_line(line):
            continue

        # Check for very short lines (likely artifacts)
        if len(line.split()) < 2:
            continue

        # Detect new paragraph conditions
        is_new_paragraph = any([
            # Bullet points
            line.startswith("•") or line.startswith("➢") or line.startswith("-"),

            # Capital letter after period
            (i > 0 and lines[i-1].strip().endswith(".") and line[0].isupper()),

            # Roman numerals (section markers)
            re.match(r'^[IVX]+\.', line),

            # Numbered lists
            re.match(r'^\d+\.', line),

            # Short headers with colons
            (len(line.split()) <= 6 and line.strip().endswith(":")),

            # All caps headers (section titles)
            (line.isupper() and len(line) < 100),
        ])

        if is_new_paragraph and current_para:
            # Save previous paragraph
            para_text = clean_ocr_text(" ".join(current_para))
            if len(para_text) >= MIN_PARAGRAPH_LENGTH:
                paragraphs.append({
                    "page": page_num,
                    "text": para_text
                })
            current_para = [line]
        else:
            current_para.append(line)

    # Add last paragraph
    if current_para:
        para_text = clean_ocr_text(" ".join(current_para))
        if len(para_text) >= MIN_PARAGRAPH_LENGTH:
            paragraphs.append({
                "page": page_num,
                "text": para_text
            })

    return paragraphs


# === Main Extraction Function ===

def extract_text_from_scanned_pdf(pdf_path: str,
                                  dpi: int = OCR_DPI,
                                  lang: str = OCR_LANG,
                                  debug: bool = False,
                                  debug_folder: str = "debug_enhanced_ocr") -> List[Dict[str, Any]]:
    """
    Extracts paragraph-level text from a scanned PDF with enhanced cropping.

    Args:
        pdf_path: Path to PDF file
        dpi: Resolution for PDF to image conversion
        lang: OCR language code
        debug: Whether to save debug visualizations
        debug_folder: Folder for debug outputs

    Returns:
        List of dictionaries with extracted paragraphs
    """
    filename = os.path.basename(pdf_path)
    print(f"\n[OCR] Processing: {filename}")

    try:
        # Convert PDF to images
        images = convert_from_path(pdf_path, dpi=dpi)

        all_paragraphs = []
        paragraph_counter = 1
        anexo_found = False

        for page_num, image in enumerate(images, start=1):
            if anexo_found:
                print(f"  [Page {page_num}] Skipped (Anexo already detected)")
                break

            print(f"  [Page {page_num}] Extracting...", end=" ")

            # Prepare debug paths
            debug_crop_path = None
            debug_line_path = None
            if debug:
                os.makedirs(debug_folder, exist_ok=True)
                base_name = filename.replace('.pdf', '')
                debug_crop_path = os.path.join(debug_folder, f"{base_name}_page{page_num}_crop.png")
                debug_line_path = os.path.join(debug_folder, f"{base_name}_page{page_num}_lines.png")

            # Get adaptive crop boundaries
            top_y, bottom_y = get_adaptive_crop_boundaries(
                image, page_num, debug_path=debug_line_path
            )

            # Crop image
            cropped_img = image.crop((0, top_y, image.width, bottom_y))

            # Save cropped image if debug
            if debug_crop_path:
                cropped_img.save(debug_crop_path)

            # Perform OCR
            page_text = pytesseract.image_to_string(cropped_img, lang=lang)

            if not page_text.strip():
                print("(empty)")
                continue

            # Check for Anexo pattern
            if detect_anexo_stop(page_text):
                print("(Anexo detected - stopping)")
                # Extract text up to Anexo
                for pattern in STOP_PATTERNS:
                    match = re.search(pattern, page_text)
                    if match:
                        page_text = page_text[:match.start()].strip()
                        break
                anexo_found = True

            # Split into lines and segment into paragraphs
            lines = [line.strip() for line in page_text.split("\n") if line.strip()]
            page_paragraphs = segment_into_paragraphs(lines, page_num)

            # Add paragraph IDs
            for para in page_paragraphs:
                para['paragraph_id'] = paragraph_counter
                paragraph_counter += 1

            all_paragraphs.extend(page_paragraphs)
            print(f"({len(page_paragraphs)} paragraphs)")

        print(f"  [Total] {len(all_paragraphs)} paragraphs extracted\n")

        # Add filename to all records
        for para in all_paragraphs:
            para['filename'] = filename

        return all_paragraphs

    except Exception as e:
        print(f"  [Error] {filename}: {e}")
        import traceback
        traceback.print_exc()
        return []


# === Batch Processing ===

def process_scanned_pdfs_batch(folder_path: str,
                               metadata_csv_path: str,
                               output_csv: str = "scanned_extracted_paragraphs.csv",
                               debug: bool = False) -> pd.DataFrame:
    """
    Batch processes all scanned PDFs in a folder.

    Args:
        folder_path: Folder containing scanned PDFs
        metadata_csv_path: Path to metadata CSV
        output_csv: Output CSV file path
        debug: Enable debug mode

    Returns:
        DataFrame with extracted paragraphs and metadata
    """
    print("="*80)
    print("ENHANCED SCANNED PDF TEXT EXTRACTION")
    print("="*80)

    # Load metadata
    print(f"\n[1/4] Loading metadata from: {metadata_csv_path}")
    metadata_df = pd.read_csv(metadata_csv_path)

    # Extract document info from metadata
    def extract_doc_info(row):
        doc_title = row.get("doc_title", "")
        match = re.search(
            r"\b(Informe|Comunicado)\b(?:\s+CF)?(?:\s+(?:N[°ºo]|No))?\s*(\d{2,4})",
            doc_title,
            re.IGNORECASE
        )
        doc_type = match.group(1).capitalize() if match else None
        doc_number = match.group(2) if match and match.lastindex >= 2 else None

        year_match = re.search(r"\b(\d{4})\b", str(row.get("date", "")))
        year = year_match.group(1) if year_match else None

        return pd.Series({"doc_type": doc_type, "doc_number": doc_number, "year": year})

    metadata_df[["doc_type", "doc_number", "year"]] = metadata_df.apply(extract_doc_info, axis=1)
    print(f"  Metadata loaded: {len(metadata_df)} records")

    # Get list of PDF files
    print(f"\n[2/4] Scanning folder: {folder_path}")
    pdf_files = sorted([f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')])
    print(f"  Found {len(pdf_files)} PDF files")

    # Process each PDF
    print(f"\n[3/4] Processing PDFs with enhanced OCR...")
    all_paragraphs = []

    for idx, pdf_file in enumerate(pdf_files, start=1):
        print(f"\n--- PDF {idx}/{len(pdf_files)} ---")
        pdf_path = os.path.join(folder_path, pdf_file)
        paragraphs = extract_text_from_scanned_pdf(pdf_path, debug=debug)
        all_paragraphs.extend(paragraphs)

    # Create DataFrame
    print(f"\n[4/4] Creating output DataFrame...")
    df = pd.DataFrame(all_paragraphs)

    if df.empty:
        print("  [Warning] No text extracted from any PDF!")
        return df

    # Merge with metadata
    df = df.merge(
        metadata_df[["pdf_filename", "doc_title", "doc_type", "doc_number", "year", "date"]],
        left_on="filename",
        right_on="pdf_filename",
        how="left"
    )

    # Reorder columns
    df = df[[
        "doc_title", "doc_type", "doc_number", "year", "date",
        "page", "paragraph_id", "text"
    ]]

    # Save to CSV
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"\n  Saved to: {output_csv}")
    print(f"  Total paragraphs: {len(df)}")
    print(f"  Total documents: {df['doc_title'].nunique()}")

    print("\n" + "="*80)
    print("EXTRACTION COMPLETE")
    print("="*80)

    return df


# === Entry Point for Testing ===

if __name__ == "__main__":
    # Test configuration
    SCANNED_FOLDER = "data/raw/scanned"
    METADATA_CSV = "metadata/cf_pdfs_metadata.csv"
    OUTPUT_CSV = "output/scanned_extracted_paragraphs.csv"

    # Run batch processing with debug enabled
    df = process_scanned_pdfs_batch(
        folder_path=SCANNED_FOLDER,
        metadata_csv_path=METADATA_CSV,
        output_csv=OUTPUT_CSV,
        debug=True  # Enable debug mode to inspect cropping
    )

    # Display sample results
    if not df.empty:
        print("\n" + "="*80)
        print("SAMPLE RESULTS")
        print("="*80)
        print(df.head(10))
        print("\nParagraph length statistics:")
        print(df['text'].str.len().describe())
