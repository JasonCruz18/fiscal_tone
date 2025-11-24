"""
Debug why words are being filtered out on page 5
"""
import pdfplumber

pdf_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Pronunciamiento-DCRF-2020-publicar.pdf"

EXCLUDED_SIZES = [5.5, 6.0, 6.5, 7.0, 7.9, 8.4, 8.5, 9.5]

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[4]  # Page 5 (0-indexed)
    page_width = float(page.width)
    page_height = float(page.height)

    print(f"Page 5: {page_width}x{page_height}pt")
    print()

    # Extract words
    words = page.extract_words(extra_attrs=["size", "top", "fontname"])

    # Filter settings
    FONT_MIN = 11.0
    FONT_MAX = 12.5
    header_cutoff = 70
    footer_cutoff = page_height - 100
    left_margin = 70
    right_margin = page_width - 70

    print(f"Filter criteria:")
    print(f"  Font: {FONT_MIN} <= size <= {FONT_MAX}")
    print(f"  Vertical: {header_cutoff} < top < {footer_cutoff}")
    print(f"  Horizontal: {left_margin} < x0 < {right_margin}")
    print(f"  Excluded sizes: {EXCLUDED_SIZES}")
    print()

    # Analyze why words are filtered
    font_filtered = 0
    excluded_size_filtered = 0
    vertical_filtered = 0
    horizontal_filtered = 0
    passed = 0

    # Sample 11.0pt words for debugging
    sample_11pt_words = []

    for w in words:
        size = w["size"]
        top = w["top"]
        x0 = w.get("x0", 0)

        # Debug 11.0pt words specifically
        if round(size, 1) == 11.0 and len(sample_11pt_words) < 5:
            sample_11pt_words.append(f"'{w['text']}' size={size:.2f}, top={top:.1f}, x0={x0:.1f}")

        # Check each filter
        if not (FONT_MIN <= size <= FONT_MAX):
            font_filtered += 1
        elif round(size, 1) in EXCLUDED_SIZES:
            excluded_size_filtered += 1
        elif not (header_cutoff < top < footer_cutoff):
            vertical_filtered += 1
        elif not (left_margin < x0 < right_margin):
            horizontal_filtered += 1
        else:
            passed += 1

    print(f"Sample 11.0pt words:")
    for s in sample_11pt_words:
        print(f"  {s}")
    print()

    print(f"Filter results for {len(words)} words:")
    print(f"  Font range filter: {font_filtered} words filtered")
    print(f"  Excluded sizes filter: {excluded_size_filtered} words filtered")
    print(f"  Vertical position filter: {vertical_filtered} words filtered")
    print(f"  Horizontal position filter: {horizontal_filtered} words filtered")
    print(f"  PASSED all filters: {passed} words")
    print()

    # Show actual font sizes on this page
    font_sizes = {}
    for w in words:
        size = round(w["size"], 1)
        if size not in font_sizes:
            font_sizes[size] = 0
        font_sizes[size] += 1

    print("Actual font sizes on page 5:")
    for size in sorted(font_sizes.keys()):
        print(f"  {size}pt: {font_sizes[size]} words")
    print()

    # Show sample of filtered words
    if vertical_filtered > 0:
        print("Sample words filtered by vertical position:")
        count = 0
        for w in words:
            if not (header_cutoff < w["top"] < footer_cutoff):
                print(f"  '{w['text']}' at Y={w['top']:.1f}pt (size={w['size']:.1f}pt)")
                count += 1
                if count >= 10:
                    break
        print()

    if horizontal_filtered > 0:
        print("Sample words filtered by horizontal position:")
        count = 0
        for w in words:
            size = w["size"]
            top = w["top"]
            x0 = w.get("x0", 0)
            if (FONT_MIN <= size <= FONT_MAX and
                round(size, 1) not in EXCLUDED_SIZES and
                header_cutoff < top < footer_cutoff and
                not (left_margin < x0 < right_margin)):
                print(f"  '{w['text']}' at X={x0:.1f}pt (left_margin={left_margin:.1f}, right_margin={right_margin:.1f})")
                count += 1
                if count >= 10:
                    break
