import os
import re
import pandas as pd
import numpy as np
import cv2
from pdf2image import convert_from_path
from PIL import Image

# === OCR Utilities (Keep this helper) ===

def detect_cut_line_y(image, min_length_ratio=0.17, y_range=(0.55, 0.90), debug_path=None):
    """
    Detects a horizontal line likely indicating the beginning of the footer in scanned PDFs.

    Args:
        image (PIL.Image): Page image.
        min_length_ratio (float): Minimum length of line relative to image width.
        y_range (tuple): Vertical range to search (proportional to height).
        debug_path (str): Optional file path to save a debug image with detected line.

    Returns:
        int: Y-coordinate of the detected line, or image height if none found.
    """
    # Convert PIL Image to OpenCV format (numpy array)
    # PIL image is RGB, but np.array() of a PIL image might be (W, H, 3)
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY_INV)

    # HoughLinesP to detect line segments
    lines = cv2.HoughLinesP(
        thresh, 1, np.pi / 180, threshold=80,
        minLineLength=int(image.width * min_length_ratio), maxLineGap=5
    )

    if lines is not None:
        height = image.height
        min_y, max_y = int(height * y_range[0]), int(height * y_range[1])

        # Filter for horizontal lines within the target vertical range
        horizontal_lines = [
            (x1, y1, x2, y2) for x1, y1, x2, y2 in lines[:, 0]
            if abs(y1 - y2) <= 5 and min_y <= y1 <= max_y
        ]

        if horizontal_lines:
            # Find the line with the smallest (highest) Y-coordinate
            best_line = min(horizontal_lines, key=lambda l: l[1])
            
            if debug_path:
                # Save debug image with the detected line drawn
                img_dbg = image.copy()
                dbg_np = np.array(img_dbg)
                # Convert back to BGR for cv2.imwrite
                cv2.line(dbg_np, (best_line[0], best_line[1]), (best_line[2], best_line[3]), (0, 0, 255), 2)
                cv2.imwrite(debug_path, cv2.cvtColor(dbg_np, cv2.COLOR_RGB2BGR))
            
            return best_line[1]

    return image.height  # No line detected → return full height

# ---

# === OCR Processing for Scanned PDFs (Revised) ===

def process_scanned_pdfs(folder_path, dpi=300, lang='spa', debug=True):
    """
    Converts scanned PDFs to images, detects the footer cut line, 
    and saves the cropped main content images.

    Args:
        folder_path (str): Folder with scanned PDFs.
        dpi (int): Resolution used to convert PDFs to images.
        lang (str): OCR language code (retained for function signature completeness, 
                    but not used in the current scope).
        debug (bool): Whether to save debug images with detected lines and cropped images.

    Returns:
        None: The function now focuses on file operations (saving cropped images).
    """
    
    # NOTE: The metadata loading and processing parts have been removed.
    print("📁 Starting PDF to Image Conversion and Cropping...")

    filenames = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    total_files = len(filenames)

    # Prepare debug directories
    if debug:
        os.makedirs("debug_lines", exist_ok=True)
        os.makedirs("debug_lines/cropped", exist_ok=True)
        
    for idx, filename in enumerate(sorted(filenames), start=1):
        file_path = os.path.join(folder_path, filename)
        print(f"🖼️ Processing ({idx}/{total_files}): {filename}")
        
        try:
            # Step 1: Convert PDF to images
            images = convert_from_path(file_path, dpi=dpi)
            
            for page_num, image in enumerate(images, start=1):
                
                debug_line_path = None
                cropped_img_path = None
                
                # Setup debug paths
                if debug:
                    base_name = os.path.splitext(filename)[0]
                    debug_line_path = f"debug_lines/{base_name}_page_{page_num}_lines.png"
                    cropped_img_path = f"debug_lines/cropped/{base_name}_page_{page_num}_cropped.png"

                # Step 2: Execute detect_cut_line_y() helper
                # This returns the Y-coordinate for cropping (or image height if no line is found)
                cut_y = detect_cut_line_y(image, debug_path=debug_line_path)

                # Step 3: Crop the image for each pdf
                # The cropped image includes everything from the top (0) down to cut_y
                cropped_img = image.crop((0, 0, image.width, cut_y))
                
                if debug:
                    cropped_img.save(cropped_img_path)
                    print(f"   -> Saved cropped image for page {page_num} to: {cropped_img_path}")
                
                # NOTE: The subsequent text extraction and paragraph segmentation logic is removed.

        except Exception as e:
            print(f"❌ Error processing {filename}: {e}")

    print(f"\n✅ Image processing complete. Cropped images saved in 'debug_lines/cropped'.")
    # Return nothing, as the goal is file operations.
    return None

# ---

# === Run and Save ===
# Example Usage:
# NOTE: Ensure the necessary dependencies (pdf2image, opencv-python, pandas, numpy, PIL) 
# and the required 'detect_cut_line_y' helper function are available in the execution environment.
process_scanned_pdfs(
    folder_path = f"data/raw/scanned",
    dpi = 400,
    lang = 'spa',
    debug = True
)