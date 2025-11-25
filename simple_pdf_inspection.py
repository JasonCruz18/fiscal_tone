"""
Simple PDF layout inspection without OCR dependency.
"""
import os
import numpy as np
import cv2
from pdf2image import convert_from_path
from PIL import Image

def inspect_layout(pdf_path, output_folder="pdf_layout", max_pages=3):
    """
    Inspects PDF layout by detecting lines and regions.
    """
    os.makedirs(output_folder, exist_ok=True)
    filename = os.path.basename(pdf_path)
    print(f"\n{'='*80}")
    print(f"Analyzing: {filename}")
    print(f"{'='*80}")

    try:
        images = convert_from_path(pdf_path, dpi=300)

        for page_num, image in enumerate(images[:max_pages], start=1):
            print(f"\n--- Page {page_num} (Size: {image.width}x{image.height}) ---")

            # Convert to numpy/OpenCV format
            img_array = np.array(image)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)

            # Create visualization with regions
            vis_img = img_array.copy()

            # Draw region boundaries
            h, w = image.height, image.width

            # Top region (0-15%): titles, headers, logos
            cv2.line(vis_img, (0, int(h*0.15)), (w, int(h*0.15)), (255, 0, 0), 3)
            cv2.putText(vis_img, "TOP (0-15%): SKIP", (10, int(h*0.08)),
                       cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 0, 0), 3)

            # Main content region (15-70%)
            cv2.line(vis_img, (0, int(h*0.70)), (w, int(h*0.70)), (0, 255, 0), 3)
            cv2.putText(vis_img, "MAIN CONTENT (15-70%)", (10, int(h*0.40)),
                       cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 255, 0), 3)

            # Footer region (70-100%)
            cv2.putText(vis_img, "FOOTER (70-100%): SKIP", (10, int(h*0.85)),
                       cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 0, 255), 3)

            # Detect horizontal lines (footer separators)
            _, thresh = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY_INV)
            lines = cv2.HoughLinesP(
                thresh, 1, np.pi / 180, threshold=80,
                minLineLength=int(w * 0.17), maxLineGap=5
            )

            detected_lines = []
            if lines is not None:
                for line in lines:
                    x1, y1, x2, y2 = line[0]
                    # Only horizontal lines
                    if abs(y2 - y1) < 10:
                        cv2.line(vis_img, (x1, y1), (x2, y2), (0, 0, 255), 5)
                        detected_lines.append((y1, x1, x2, x2-x1))

                detected_lines.sort()
                print(f"  [Lines] Detected {len(detected_lines)} horizontal lines:")
                for y, x1, x2, width in detected_lines:
                    rel_y = y / h
                    rel_width = width / w
                    print(f"    Y={y} ({rel_y:.1%}) | Width={width}px ({rel_width:.1%})")
                    if 0.55 <= rel_y <= 0.90:
                        print(f"      -> FOOTER SEPARATOR (in detection range)")

            # Analyze image darkness distribution
            gray_normalized = gray.astype(float) / 255.0

            regions = {
                'top_15': gray_normalized[:int(h*0.15), :],
                'main_15_70': gray_normalized[int(h*0.15):int(h*0.70), :],
                'bottom_70': gray_normalized[int(h*0.70):, :]
            }

            print(f"\n  [Density] Text density by region (lower = more text):")
            for region_name, region_data in regions.items():
                avg_brightness = np.mean(region_data)
                print(f"    {region_name:15s}: {avg_brightness:.3f}")

            # Save visualization
            output_path = os.path.join(output_folder, f"{filename[:-4]}_page{page_num}_layout.png")
            cv2.imwrite(output_path, cv2.cvtColor(vis_img, cv2.COLOR_RGB2BGR))
            print(f"\n  [Saved] {output_path}")

            # Also save a cropped version (simulating the extraction)
            cropped_img = image.crop((0, int(h*0.15), w, int(h*0.70)))
            crop_path = os.path.join(output_folder, f"{filename[:-4]}_page{page_num}_cropped.png")
            cropped_img.save(crop_path)
            print(f"  [Saved] {crop_path}")

    except Exception as e:
        print(f"[Error] {filename}: {e}")
        import traceback
        traceback.print_exc()


def main():
    scanned_folder = "data/raw/scanned"
    pdf_files = sorted([f for f in os.listdir(scanned_folder) if f.lower().endswith('.pdf')])

    print(f"Inspecting {len(pdf_files)} scanned PDFs")
    print(f"Analyzing first 5 PDFs (2 pages each)\n")

    for pdf_file in pdf_files[:5]:
        pdf_path = os.path.join(scanned_folder, pdf_file)
        inspect_layout(pdf_path, max_pages=2)

    print(f"\n{'='*80}")
    print("Complete! Check 'pdf_layout' folder for visualizations.")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
