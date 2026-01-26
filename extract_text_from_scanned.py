"""
Extract Text from Cropped Scanned PDF Pages

Uses Tesseract OCR with automatic paragraph detection based on vertical spacing.
Generates JSON in same format as editable PDFs extraction.

Output: scanned_pdfs_extracted_text.json in data/raw/
"""

import pytesseract
from PIL import Image
from pathlib import Path
import json
import re
from tqdm import tqdm
import pandas as pd


# Configure Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def extract_text_with_paragraphs(image_path, lang='spa', min_paragraph_gap=30):
    """
    Extract text from image with automatic paragraph detection

    Uses Tesseract layout analysis to detect paragraph breaks based on
    vertical spacing between text blocks.

    Args:
        image_path: Path to cropped image
        lang: Language code (spa=Spanish)
        min_paragraph_gap: Minimum vertical gap (px) to consider new paragraph

    Returns:
        Text with paragraphs separated by double newlines
    """
    try:
        # Open image
        img = Image.open(image_path)

        # Get detailed OCR data with bounding boxes
        # This gives us line-by-line position data
        ocr_data = pytesseract.image_to_data(
            img,
            lang=lang,
            output_type=pytesseract.Output.DICT,
            config='--oem 3 --psm 6'
        )

        # Group text by lines with their Y positions
        lines = []
        current_line = {
            'text': '',
            'y_top': 0,
            'y_bottom': 0
        }

        for i in range(len(ocr_data['text'])):
            conf = int(ocr_data['conf'][i])
            text = ocr_data['text'][i].strip()

            # Skip low confidence or empty text
            if conf < 0 or not text:
                continue

            # Get position info
            x = ocr_data['left'][i]
            y = ocr_data['top'][i]
            h = ocr_data['height'][i]
            w = ocr_data['width'][i]
            block_num = ocr_data['block_num'][i]
            line_num = ocr_data['line_num'][i]

            # Check if this is a new line
            # (different block or line number, or significant Y jump)
            if current_line['text']:
                is_new_line = (
                    line_num != current_line.get('line_num') or
                    block_num != current_line.get('block_num') or
                    abs(y - current_line['y_top']) > h * 0.5
                )
            else:
                is_new_line = False

            if is_new_line and current_line['text']:
                # Save previous line
                lines.append(current_line)

                # Start new line
                current_line = {
                    'text': text,
                    'y_top': y,
                    'y_bottom': y + h,
                    'block_num': block_num,
                    'line_num': line_num
                }
            else:
                # Continue current line
                if current_line['text']:
                    current_line['text'] += ' ' + text
                else:
                    current_line['text'] = text
                    current_line['y_top'] = y
                    current_line['block_num'] = block_num
                    current_line['line_num'] = line_num

                current_line['y_bottom'] = max(current_line['y_bottom'], y + h)

        # Add last line
        if current_line['text']:
            lines.append(current_line)

        # Now detect paragraph breaks based on vertical spacing
        paragraphs = []
        current_paragraph = []

        for i, line in enumerate(lines):
            current_paragraph.append(line['text'])

            # Check if next line starts a new paragraph
            if i < len(lines) - 1:
                next_line = lines[i + 1]
                vertical_gap = next_line['y_top'] - line['y_bottom']

                # New paragraph if large vertical gap
                if vertical_gap > min_paragraph_gap:
                    # Save current paragraph
                    paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = []

        # Add last paragraph
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))

        # Join paragraphs with double newlines
        text = '\n\n'.join(paragraphs)

        return text.strip()

    except Exception as e:
        print(f"[ERROR] Failed to extract from {image_path.name}: {e}")
        return f"[EXTRACTION ERROR: {str(e)}]"


def extract_from_all_cropped_pages(cropped_folder="data/raw/scanned/cropped",
                                   output_json="data/raw/scanned_pdfs_extracted_text.json",
                                   lang='spa',
                                   min_paragraph_gap=30):
    """
    Extract text from all cropped pages

    Generates JSON with structure matching editable PDFs:
    [
        {
            "pdf_filename": "Informe_001.pdf",
            "page": 1,
            "text": "paragraph1\\n\\nparagraph2\\n\\n..."
        },
        ...
    ]

    Args:
        cropped_folder: Folder containing cropped PNG files
        output_json: Path for output JSON file
        lang: OCR language
        min_paragraph_gap: Minimum vertical gap for paragraph detection
    """
    cropped_folder = Path(cropped_folder)
    output_json = Path(output_json)

    print(f"\n{'='*80}")
    print("TEXT EXTRACTION FROM SCANNED PDFs")
    print('='*80)
    print(f"Input folder: {cropped_folder}")
    print(f"Output JSON: {output_json}")
    print(f"Language: {lang}")
    print(f"Min paragraph gap: {min_paragraph_gap}px")
    print('='*80)

    # Get all cropped PNG files
    png_files = sorted(cropped_folder.glob("*.png"))

    if not png_files:
        print(f"\n[ERROR] No PNG files found in {cropped_folder}")
        return

    print(f"\nFound {len(png_files)} cropped pages\n")

    # Extract text from each page
    results = []

    for png_path in tqdm(png_files, desc="Extracting text", ncols=80):
        # Parse filename: "Informe_CF_N_003-2016_p01_cropped.png"
        filename = png_path.stem.replace('_cropped', '')

        # Extract PDF name and page number
        # Pattern: {pdf_name}_p{page_num}
        match = re.match(r'(.+)_p(\d+)', filename)

        if match:
            pdf_name = match.group(1)
            page_num = int(match.group(2))
        else:
            # Fallback: treat whole name as PDF name, page = 1
            pdf_name = filename
            page_num = 1

        # Add .pdf extension to match editable format
        pdf_filename = f"{pdf_name}.pdf"

        # Extract text with paragraph detection
        text = extract_text_with_paragraphs(
            png_path,
            lang=lang,
            min_paragraph_gap=min_paragraph_gap
        )

        # Add to results
        results.append({
            'pdf_filename': pdf_filename,
            'page': page_num,
            'text': text
        })

    # Save JSON
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Generate statistics
    print(f"\n{'='*80}")
    print("EXTRACTION COMPLETE")
    print('='*80)
    print(f"Total pages processed: {len(results)}")
    print(f"Total characters extracted: {sum(len(r['text']) for r in results):,}")
    print(f"Average chars per page: {sum(len(r['text']) for r in results) // len(results):,}")

    # Count PDFs
    unique_pdfs = set(r['pdf_filename'] for r in results)
    print(f"Unique PDFs: {len(unique_pdfs)}")

    # Show sample
    print(f"\n{'='*80}")
    print("SAMPLE EXTRACTION (first page):")
    print('='*80)
    if results:
        sample = results[0]
        print(f"PDF: {sample['pdf_filename']}")
        print(f"Page: {sample['page']}")
        print(f"Text preview (first 300 chars):")
        print(sample['text'][:300] + "...")

    print(f"\n{'='*80}")
    print(f"Output saved to: {output_json}")
    print('='*80)

    return results


def preview_paragraph_detection(image_path, min_paragraph_gap=30):
    """
    Preview paragraph detection for a single image (debugging tool)

    Shows where paragraph breaks are detected
    """
    text = extract_text_with_paragraphs(image_path, min_paragraph_gap=min_paragraph_gap)

    print(f"\n{'='*80}")
    print(f"PARAGRAPH DETECTION PREVIEW: {Path(image_path).name}")
    print('='*80)

    paragraphs = text.split('\n\n')

    print(f"Total paragraphs detected: {len(paragraphs)}\n")

    for i, para in enumerate(paragraphs, 1):
        print(f"--- Paragraph {i} ({len(para)} chars) ---")
        print(para[:200] + ("..." if len(para) > 200 else ""))
        print()

    print('='*80)


if __name__ == "__main__":
    # Main extraction
    extract_from_all_cropped_pages(
        cropped_folder="data/raw/scanned/cropped",
        output_json="data/raw/scanned_pdfs_extracted_text.json",
        lang='spa',
        min_paragraph_gap=30  # 30px vertical gap = new paragraph
    )

    # Optional: Preview paragraph detection for first page
    # from pathlib import Path
    # first_page = next(Path("data/raw/scanned/cropped").glob("*.png"))
    # preview_paragraph_detection(first_page, min_paragraph_gap=30)
