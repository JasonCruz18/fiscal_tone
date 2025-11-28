#%%
import os
import cv2
import numpy as np
from pdf2image import convert_from_path
from PIL import Image

# =========================================================
# 1. THE DETECTION LOGIC (No changes needed here)
# =========================================================
def detect_cut_line_y(image, min_length_ratio=0.16, y_range=(0.40, 0.95), debug_path=None):
    img_np = np.array(image) 
    gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

    height, width = image.height, image.width
    half_width = int(width * 0.5)
    min_y, max_y = int(height * y_range[0]), int(height * y_range[1])

    thresh[:, half_width:] = 0 

    lines = cv2.HoughLinesP(
        thresh, 1, np.pi / 180, threshold=50,
        minLineLength=int(width * min_length_ratio), maxLineGap=9
    )
    
    best_y = height 
    best_line_coords = None
    candidate_lines = []

    if lines is not None:
        for line in lines[:, 0]:
            x1, y1, x2, y2 = line
            if abs(y1 - y2) <= 9 and min_y <= y1 <= max_y:
                candidate_lines.append((x1, y1, x2, y2))

        if candidate_lines:
            best_line = min(candidate_lines, key=lambda l: l[1])
            best_y = best_line[1]
            best_line_coords = best_line

    if debug_path:
        roi_color_bgr = (255, 102, 51)
        debug_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        overlay = debug_img.copy()

        cv2.rectangle(overlay, (0, min_y), (half_width, max_y), roi_color_bgr, -1)
        cv2.addWeighted(overlay, 0.25, debug_img, 0.75, 0, debug_img)
        cv2.rectangle(debug_img, (0, min_y), (half_width, max_y), roi_color_bgr, 2)
        
        if candidate_lines:
            for line in candidate_lines:
                if line != best_line_coords: 
                    cv2.line(debug_img, (line[0], line[1]), (line[2], line[3]), (150, 150, 150), 1)

        if best_line_coords is not None:
            bx1, by1, bx2, by2 = best_line_coords
            cv2.line(debug_img, (bx1, by1), (bx2, by2), (76, 0, 230), 8)
            label = f"CUT Y: {best_y}"
            cv2.putText(debug_img, label, (bx1, by1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (76, 0, 230), 2)
        else:
            cv2.putText(debug_img, "NO CUT LINE FOUND", (50, int(height/2)), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)

        cv2.imwrite(debug_path, debug_img)

    return best_y

# =========================================================
# 2. THE DIAGNOSTIC RUNNER
# =========================================================
def process_scanned_pdfs(folder_path, dpi=300, lang='spa', debug=True):
    print(f"📁 Scanning Folder: {folder_path}")
    
    if debug:
        os.makedirs("debug_lines", exist_ok=True)
        os.makedirs("debug_lines/cropped", exist_ok=True)

    filenames = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    total_files = len(filenames)
    
    successful_files = []
    failed_files = []

    print(f"📄 Found {total_files} PDF files.")

    for idx, filename in enumerate(sorted(filenames), start=1):
        file_path = os.path.join(folder_path, filename)
        # print(f"Processing ({idx}/{total_files}): {filename}") # Commented out to reduce noise
        
        try:
            # 1. Attempt to convert PDF
            images = convert_from_path(file_path, dpi=dpi)
            
            # 2. If successful, process pages
            for page_num, image in enumerate(images, start=1):
                base_name = os.path.splitext(filename)[0]
                debug_line_path = f"debug_lines/{base_name}_p{page_num}_debug.png"
                cropped_img_path = f"debug_lines/cropped/{base_name}_p{page_num}_cropped.png"

                cut_y = detect_cut_line_y(image, debug_path=debug_line_path)
                cropped_img = image.crop((0, 0, image.width, cut_y))
                cropped_img.save(cropped_img_path)
            
            successful_files.append(filename)
            print(f"   ✅ Success: {filename}")

        except Exception as e:
            # 3. Catch errors and Log them
            error_msg = str(e)
            failed_files.append((filename, error_msg))
            print(f"   ❌ FAILED: {filename} | Error: {error_msg}")

    # =========================================================
    # 3. FINAL REPORT
    # =========================================================
    print(f"\n{'='*40}")
    print(f"PROCESSING COMPLETE")
    print(f"{'='*40}")
    print(f"Total PDFs found: {total_files}")
    print(f"Successful:       {len(successful_files)}")
    print(f"Failed:           {len(failed_files)}")
    
    if failed_files:
        print(f"\n⚠️ LIST OF FAILED FILES:")
        with open("processing_errors.txt", "w", encoding="utf-8") as f:
            f.write(f"Failed Files Report ({len(failed_files)} files)\n")
            f.write("="*50 + "\n")
            for fname, err in failed_files:
                line = f"• {fname} \n  -> Reason: {err}\n"
                print(line)
                f.write(line + "\n")
        print(f"\n📄 A full error report has been saved to 'processing_errors.txt'")
    else:
        print("\n🎉 All files processed successfully!")

# =========================================================
# 4. EXECUTION
# =========================================================
if __name__ == "__main__":
    process_scanned_pdfs(
        folder_path = f"data/raw/_scanned_aux",
        dpi = 300,
        lang = 'spa',
        debug = True
    )

