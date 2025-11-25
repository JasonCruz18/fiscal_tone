"""
Script to inspect scanned PDF structure and layout patterns.
"""
import os
import numpy as np
import cv2
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import re

def analyze_pdf_structure(pdf_path, output_folder="pdf_inspection", max_pages=3):
    """
    Analyzes the structure of a scanned PDF by converting to images and detecting layout elements.

    Args:
        pdf_path (str): Path to the PDF file
        output_folder (str): Folder to save analysis images
        max_pages (int): Maximum number of pages to analyze
    """
    os.makedirs(output_folder, exist_ok=True)
    filename = os.path.basename(pdf_path)
    print(f"\n{'='*80}")
    print(f"[*] Analyzing: {filename}")
    print(f"{'='*80}")

    try:
        images = convert_from_path(pdf_path, dpi=300)

        for page_num, image in enumerate(images[:max_pages], start=1):
            print(f"\n--- Page {page_num} ---")

            # Convert to numpy array for OpenCV
            img_array = np.array(image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

            # Detect horizontal lines (potential separators/footers)
            _, thresh = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY_INV)
            lines = cv2.HoughLinesP(
                thresh, 1, np.pi / 180, threshold=80,
                minLineLength=int(image.width * 0.17), maxLineGap=5
            )

            # Create visualization
            vis_img = img_array.copy()
            line_positions = []

            if lines is not None:
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    # Only consider horizontal lines (within 5 degrees of horizontal)
                    if abs(y2 - y1) < 10:
                        cv2.line(vis_img, (x1, y1), (x2, y2), (255, 0, 0), 3)
                        line_positions.append((y1, x1, x2))

                line_positions.sort()
                print(f"  [Lines] Detected {len(line_positions)} horizontal lines:")
                for y, x1, x2 in line_positions:
                    rel_y = y / image.height
                    line_width = x2 - x1
                    rel_width = line_width / image.width
                    print(f"    Y={y} ({rel_y:.2%}), Width={line_width}px ({rel_width:.2%})")

            # Analyze text regions using OCR with bounding boxes
            ocr_data = pytesseract.image_to_data(image, lang='spa', output_type=pytesseract.Output.DICT)

            # Group text blocks by vertical position
            text_blocks = []
            for i, text in enumerate(ocr_data['text']):
                if text.strip():
                    conf = int(ocr_data['conf'][i])
                    if conf > 30:  # Only consider confident detections
                        x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
                        text_blocks.append({
                            'text': text,
                            'x': x, 'y': y, 'w': w, 'h': h,
                            'y_center': y + h/2,
                            'rel_y': (y + h/2) / image.height
                        })

            # Identify potential headers, titles, and footers by position
            if text_blocks:
                print(f"\n  [Text] Text regions detected: {len(text_blocks)}")

                # First 10% - likely title/header
                top_region = [b for b in text_blocks if b['rel_y'] < 0.10]
                if top_region:
                    print(f"    [Top] Top region (0-10%): {len(top_region)} text elements")
                    sample_texts = ' '.join([b['text'] for b in top_region[:10]])
                    print(f"       Sample: {sample_texts[:100]}...")

                # Middle region 10-70% - main content
                middle_region = [b for b in text_blocks if 0.10 <= b['rel_y'] < 0.70]
                if middle_region:
                    print(f"    [Main] Middle region (10-70%): {len(middle_region)} text elements")

                # Bottom region 70-100% - potential footer
                bottom_region = [b for b in text_blocks if b['rel_y'] >= 0.70]
                if bottom_region:
                    print(f"    [Bottom] Bottom region (70-100%): {len(bottom_region)} text elements")
                    sample_texts = ' '.join([b['text'] for b in bottom_region[:10]])
                    print(f"       Sample: {sample_texts[:100]}...")

            # Draw bounding boxes on visualization
            for block in text_blocks[:50]:  # Limit for clarity
                x, y, w, h = block['x'], block['y'], block['w'], block['h']
                color = (0, 255, 0) if 0.10 <= block['rel_y'] < 0.70 else (255, 165, 0)
                cv2.rectangle(vis_img, (x, y), (x+w, y+h), color, 2)

            # Save visualization
            output_path = os.path.join(output_folder, f"{filename[:-4]}_page{page_num}_analysis.png")
            cv2.imwrite(output_path, cv2.cvtColor(vis_img, cv2.COLOR_RGB2BGR))
            print(f"  [Save] Saved analysis image: {output_path}")

            # Detect common patterns
            full_text = pytesseract.image_to_string(image, lang='spa')

            # Check for institutional headers
            header_patterns = [
                r"Informe\s+(?:CF\s+)?N[°ºo\.]?\s*\d+",
                r"Comunicado\s+(?:CF\s+)?N[°ºo\.]?\s*\d+",
                r"CONSEJO\s+FISCAL",
                r"Ministerio\s+de\s+Economía"
            ]

            print(f"\n  [Pattern] Pattern detection:")
            for pattern in header_patterns:
                matches = re.findall(pattern, full_text, re.IGNORECASE)
                if matches:
                    print(f"    [+] Found: {pattern} -> {matches[:2]}")

            # Check for footer patterns
            footer_patterns = [
                r"Página\s+\d+",
                r"www\.cf\.gob\.pe",
                r"\d+\s+de\s+\d+"
            ]

            for pattern in footer_patterns:
                matches = re.findall(pattern, full_text, re.IGNORECASE)
                if matches:
                    print(f"    [Footer] Footer pattern: {pattern} -> {matches[:2]}")

    except Exception as e:
        print(f"[!] Error analyzing {filename}: {e}")


def main():
    scanned_folder = "data/raw/scanned"

    # Analyze first 3 PDFs as samples
    pdf_files = sorted([f for f in os.listdir(scanned_folder) if f.lower().endswith('.pdf')])

    print(f"[*] Inspecting {len(pdf_files)} scanned PDFs")
    print(f"[*] Will analyze first 3 PDFs in detail\n")

    for pdf_file in pdf_files[:3]:
        pdf_path = os.path.join(scanned_folder, pdf_file)
        analyze_pdf_structure(pdf_path, max_pages=2)

    print(f"\n{'='*80}")
    print("[+] Inspection complete! Check 'pdf_inspection' folder for visualizations.")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
