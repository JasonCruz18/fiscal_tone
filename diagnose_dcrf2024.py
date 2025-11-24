"""
Diagnostic: Check page 5 of Informe-DCRF2024-vf.pdf for keyword
"""

import sys
import pdfplumber

# Set UTF-8 encoding
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

test_file = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Informe-DCRF2024-vf.pdf"

with pdfplumber.open(test_file) as pdf:
    total_pages = len(pdf.pages)
    print(f"Total pages: {total_pages}\n")

    # Check pages 2-7 for "Opinión" keyword
    for page_idx in range(1, min(8, total_pages)):  # Pages 2-8
        page_num = page_idx + 1
        page = pdf.pages[page_idx]

        print(f"="*80)
        print(f"PAGE {page_num}")
        print(f"="*80)

        words = page.extract_words(extra_attrs=["size", "top", "fontname"])

        # Look for any text containing "Opinión" or "opinión"
        opinion_words = [w for w in words if "opinión" in w["text"].lower() or "opini" in w["text"].lower()]

        if opinion_words:
            print(f"\n✓ Found 'Opinión' on page {page_num}!\n")

            # Group by line to show full context
            lines = {}
            for word in opinion_words:
                top = round(word["top"], 1)
                if top not in lines:
                    lines[top] = []
                lines[top].append(word)

            for top_pos in sorted(lines.keys()):
                # Get all words at this vertical position
                all_words_at_top = [w for w in words if abs(w["top"] - top_pos) < 1.0]
                all_words_sorted = sorted(all_words_at_top, key=lambda w: w.get("x0", 0))
                line_text = " ".join([w["text"] for w in all_words_sorted])
                sizes = set([w["size"] for w in all_words_at_top])
                fonts = set([w["fontname"] for w in all_words_at_top])

                print(f"  Y={top_pos:6.1f}pt")
                print(f"  Sizes: {sorted(sizes)}")
                print(f"  Fonts: {fonts}")
                print(f"  Text: {line_text}")
                print(f"  First word X position: {all_words_sorted[0].get('x0', 'N/A')}")
                print()

        else:
            print(f"  ✗ No 'Opinión' found on page {page_num}\n")

        # Also show what font sizes are present on this page
        all_sizes = sorted(set([round(w["size"], 1) for w in words]))
        print(f"  Available font sizes: {all_sizes[:15]}...")
        print()
