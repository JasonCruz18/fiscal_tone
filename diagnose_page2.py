"""
Diagnostic: See what text is actually on page 2
"""

import sys
import pdfplumber

# Set UTF-8 encoding
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

test_file = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\CF-Informe-IAPM21-vF.pdf"

with pdfplumber.open(test_file) as pdf:
    # Look at page 2 (index 1)
    page = pdf.pages[1]

    print(f"Page 2 dimensions: {page.width}x{page.height}\n")

    words = page.extract_words(extra_attrs=["size", "top", "fontname"])

    print(f"Total words on page 2: {len(words)}\n")

    # Filter by font sizes around 11pt to see headers
    sizes_of_interest = [10.0, 10.5, 11.0, 11.5, 12.0, 12.5, 13.0]

    for size in sizes_of_interest:
        words_at_size = [w for w in words if abs(w["size"] - size) < 0.2]
        if words_at_size:
            print(f"\n--- Font size {size}pt ({len(words_at_size)} words) ---")

            # Group by vertical position (lines)
            lines = {}
            for word in words_at_size:
                top = round(word["top"], 1)
                if top not in lines:
                    lines[top] = []
                lines[top].append(word)

            # Show first 5 lines
            for i, top_pos in enumerate(sorted(lines.keys())[:5]):
                line_words = sorted(lines[top_pos], key=lambda w: w.get("x0", 0))
                line_text = " ".join([w["text"] for w in line_words])
                print(f"  Y={top_pos:6.1f}pt: {line_text[:80]}")

    # Also show all text that contains "Opinión" or "opinión"
    print("\n\n--- Lines containing 'Opinión' or 'opinión' ---")
    opinion_words = [w for w in words if "opinión" in w["text"].lower() or "opini" in w["text"].lower()]

    if opinion_words:
        # Group by line
        lines = {}
        for word in opinion_words:
            top = round(word["top"], 1)
            if top not in lines:
                lines[top] = []
            lines[top].append((word, word))

        # Show context for each line with "Opinión"
        for top_pos in sorted(lines.keys()):
            # Get all words at this vertical position
            all_words_at_top = [w for w in words if abs(w["top"] - top_pos) < 1.0]
            all_words_sorted = sorted(all_words_at_top, key=lambda w: w.get("x0", 0))
            line_text = " ".join([w["text"] for w in all_words_sorted])
            sizes = set([w["size"] for w in all_words_at_top])
            print(f"\n  Y={top_pos:6.1f}pt | Sizes: {sorted(sizes)} | Font: {all_words_at_top[0]['fontname']}")
            print(f"  Text: {line_text}")
    else:
        print("  NO lines containing 'Opinión' found on page 2!")

    # Check page 3 and 4 too
    for page_num in [3, 4]:
        if page_num <= len(pdf.pages):
            page = pdf.pages[page_num - 1]
            words = page.extract_words(extra_attrs=["size", "top", "fontname"])
            opinion_words = [w for w in words if "opinión" in w["text"].lower() or "opini" in w["text"].lower()]

            if opinion_words:
                print(f"\n\n--- Found 'Opinión' on PAGE {page_num} ---")
                lines = {}
                for word in opinion_words:
                    top = round(word["top"], 1)
                    if top not in lines:
                        lines[top] = []
                    lines[top].append(word)

                for top_pos in sorted(lines.keys()):
                    all_words_at_top = [w for w in words if abs(w["top"] - top_pos) < 1.0]
                    all_words_sorted = sorted(all_words_at_top, key=lambda w: w.get("x0", 0))
                    line_text = " ".join([w["text"] for w in all_words_sorted])
                    sizes = set([w["size"] for w in all_words_at_top])
                    print(f"\n  Y={top_pos:6.1f}pt | Sizes: {sorted(sizes)}")
                    print(f"  Text: {line_text}")
