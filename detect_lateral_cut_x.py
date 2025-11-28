#%%
import os
import cv2
import numpy as np
from pdf2image import convert_from_path
from PIL import Image

# =========================================================
# 1. THE HELPER: Fixed Lateral Crop & Visualize
# =========================================================
def apply_fixed_lateral_crop(image, dpi=300, left_cm=2.5, right_cm=2.5, debug_path=None):
    """
    Calculates fixed crop coordinates based on CM and DPI, 
    and generates a debug visualization showing the removed areas.
    """
    height, width = image.height, image.width
    
    # --- 1. Math: Convert CM to Pixels ---
    # Formula: (CM / 2.54) * DPI
    px_cut_left = int((left_cm / 2.54) * dpi)
    px_cut_right = int((right_cm / 2.54) * dpi)
    
    # Calculate absolute X coordinates
    cut_x1 = px_cut_left
    cut_x2 = width - px_cut_right

    # Safety Check: If cuts overlap, default to no crop
    if cut_x1 >= cut_x2:
        cut_x1, cut_x2 = 0, width

    # =========================================================
    # 2. DEBUG VISUALIZATION
    # =========================================================
    if debug_path:
        img_np = np.array(image)
        # BGR conversion for OpenCV
        debug_img = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        overlay = debug_img.copy()
        
        roi_color_bgr = (255, 102, 51) # The "Nice Blue"

        # --- Draw the "Trash" Areas (The parts being removed) ---
        
        # Left Margin (Filled)
        cv2.rectangle(overlay, (0, 0), (cut_x1, height), roi_color_bgr, -1)
        
        # Right Margin (Filled)
        cv2.rectangle(overlay, (cut_x2, 0), (width, height), roi_color_bgr, -1)

        # === OPACITY: 75% Overlay ===
        cv2.addWeighted(overlay, 0.75, debug_img, 0.25, 0, debug_img)

        # --- Draw Cut Lines (Pink) ---
        pink_color = (76, 0, 230)
        
        # Left Cut Line
        cv2.line(debug_img, (cut_x1, 0), (cut_x1, height), pink_color, 5)
        
        # Right Cut Line
        cv2.line(debug_img, (cut_x2, 0), (cut_x2, height), pink_color, 5)

        # --- Add Labels ---
        font = cv2.FONT_HERSHEY_SIMPLEX
        
        # Left Label
        cv2.putText(debug_img, f"REMOVE {left_cm}cm", (10, int(height/2)), font, 1.0, (255, 255, 255), 2)
        cv2.putText(debug_img, f"({px_cut_left}px)", (10, int(height/2) + 40), font, 0.8, (255, 255, 255), 2)
        
        # Right Label
        cv2.putText(debug_img, f"REMOVE {right_cm}cm", (width - 350, int(height/2)), font, 1.0, (255, 255, 255), 2)
        cv2.putText(debug_img, f"({px_cut_right}px)", (width - 350, int(height/2) + 40), font, 0.8, (255, 255, 255), 2)

        # Save Debug
        cv2.imwrite(debug_path, debug_img)

    return cut_x1, cut_x2

# =========================================================
# 2. THE RUNNER
# =========================================================
def process_lateral_fixed_crops(folder_path, dpi=300, left_cm=2.5, right_cm=2.5, debug=True):
    print(f"📁 Starting Fixed Lateral Cropping in: {folder_path}")
    print(f"   - Left Cut:  {left_cm} cm")
    print(f"   - Right Cut: {right_cm} cm")
    
    if debug:
        os.makedirs("debug_lateral_fixed", exist_ok=True)
        os.makedirs("debug_lateral_fixed/cropped", exist_ok=True)

    filenames = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf")]
    total_files = len(filenames)
    
    for idx, filename in enumerate(sorted(filenames), start=1):
        file_path = os.path.join(folder_path, filename)
        print(f"🖼️ Processing ({idx}/{total_files}): {filename}")
        
        try:
            images = convert_from_path(file_path, dpi=dpi)
            
            for page_num, image in enumerate(images, start=1):
                base_name = os.path.splitext(filename)[0]
                
                # Paths
                debug_path = f"debug_lateral_fixed/{base_name}_p{page_num}_debug.png"
                cropped_path = f"debug_lateral_fixed/cropped/{base_name}_p{page_num}_cropped.png"

                # 1. Calculate Cuts & Visualize
                cut_x1, cut_x2 = apply_fixed_lateral_crop(
                    image, 
                    dpi=dpi, 
                    left_cm=left_cm, 
                    right_cm=right_cm, 
                    debug_path=debug_path
                )

                # 2. Perform Crop
                # Tuple: (left, top, right, bottom)
                cropped_img = image.crop((cut_x1, 0, cut_x2, image.height))
                
                # 3. Save Final
                cropped_img.save(cropped_path)
                
        except Exception as e:
            print(f"❌ Error processing {filename}: {e}")

    print(f"\n✅ Processing complete.")

# =========================================================
# 3. CALIBRATION ZONE
# =========================================================
if __name__ == "__main__":
    
    # === PARAMETERS TO CALIBRATE ===
    LEFT_MARGIN_CM = 2.75
    RIGHT_MARGIN_CM = 2.75
    DPI = 300 # Must match the DPI used to load the PDF
    # ===============================

    RAW_DATA_FOLDER = "data/raw/scanned"
    
    if os.path.exists(RAW_DATA_FOLDER):
        process_lateral_fixed_crops(
            folder_path=RAW_DATA_FOLDER, 
            dpi=DPI, 
            left_cm=LEFT_MARGIN_CM, 
            right_cm=RIGHT_MARGIN_CM, 
            debug=True
        )
    else:
        print(f"❌ Error: Folder '{RAW_DATA_FOLDER}' not found.")