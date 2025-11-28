# === OCR Utilities ===

def detect_cut_line_y(image, min_length_ratio=0.2, y_range=(0.5, 0.85), debug_path=None):
    """
    Detects a horizontal line that likely marks the beginning of the footer in a scanned PDF page.
    
    Parameters:
        image (PIL.Image): Page image to analyze.
        min_length_ratio (float): Minimum line length relative to image width.
        y_range (tuple): Vertical range (as a proportion of image height) where footer lines are expected.
        debug_path (str): Optional path to save debug image with the detected line.
    
    Returns:
        int: Y-coordinate to crop the image above the footer line, or image height if no line is found.
    """
    gray = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)

    lines = cv2.HoughLinesP(
        thresh, 1, np.pi / 180, threshold=100,
        minLineLength=int(image.width * min_length_ratio), maxLineGap=5
    )

    if lines is not None:
        height = image.height
        min_y, max_y = int(height * y_range[0]), int(height * y_range[1])

        horizontal_lines = [
            (x1, y1, x2, y2) for x1, y1, x2, y2 in lines[:, 0]
            if abs(y1 - y2) <= 3 and min_y <= y1 <= max_y
        ]

        if horizontal_lines:
            best_line = min(horizontal_lines, key=lambda l: l[1])
            if debug_path:
                img_dbg = image.copy()
                dbg_np = np.array(img_dbg)
                cv2.line(dbg_np, (best_line[0], best_line[1]), (best_line[2], best_line[3]), (0, 0, 255), 2)
                cv2.imwrite(debug_path, cv2.cvtColor(dbg_np, cv2.COLOR_RGB2BGR))
            return best_line[1]

    return image.height  # Default: no footer line detected