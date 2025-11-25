"""
Debug why "Comunicado042024-VF" is matching keyword incorrectly
"""
import pdfplumber
import re

pdf_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Comunicado042024-VF.pdf"

keywords = [
    r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del? Consejo Fiscal\b",
    r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del? CF\b"
]

print("Testing keyword match on Comunicado042024-VF")
print("="*80)

with pdfplumber.open(pdf_path) as pdf:
    for page_num in range(2, min(6, len(pdf.pages) + 1)):  # Check pages 2-5
        page = pdf.pages[page_num - 1]
        words = page.extract_words(extra_attrs=["size", "fontname"])

        # Filter by font size 11.0-15.0pt
        candidate_words = [w for w in words if "size" in w and 11.0 <= w["size"] <= 15.0]

        # Group by Y-position
        lines = {}
        for word in candidate_words:
            if "top" not in word:
                continue
            top = round(word["top"], 1)
            if top not in lines:
                lines[top] = []
            lines[top].append(word)

        # Check each line
        for top_pos in sorted(lines.keys()):
            line_words = sorted(lines[top_pos], key=lambda w: w.get("x0", 0))
            line_text = " ".join([w.get("text", "") for w in line_words])

            # Check if any keyword pattern matches
            for i, keyword_pattern in enumerate(keywords, 1):
                if re.match(keyword_pattern, line_text, re.IGNORECASE):
                    first_word_x = line_words[0].get("x0", 0) if line_words else 0
                    print(f"\nPage {page_num}, Y={top_pos:.1f}pt, X={first_word_x:.1f}pt")
                    print(f"Pattern {i} MATCHED: '{line_text[:80]}...'")

                    # Show if it's truly left-aligned
                    if first_word_x < 120:
                        print(f"  → LEFT-aligned (X={first_word_x:.1f}pt)")
                    else:
                        print(f"  → CENTERED/RIGHT (X={first_word_x:.1f}pt) - should NOT match!")

                    # Show first few words
                    print(f"  Words: {[w.get('text') for w in line_words[:5]]}")

                    # Check case sensitivity
                    if line_text[0].islower():
                        print(f"  ⚠️ STARTS WITH LOWERCASE: '{line_text[0]}'")
