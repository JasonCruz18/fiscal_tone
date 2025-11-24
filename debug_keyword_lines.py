"""
Check if keyword words are grouped on the same line (by Y-position)
"""
import pdfplumber
import re

# Test files with their expected keyword pages
test_cases = [
    ("Pronunciamiento-DCRF-2020-publicar.pdf", 4),
    ("PronunciamientoDCRF-RFSN-2021-vf.pdf", 5),
    ("Pronunciamiento-DU-031-subnacionalvf.pdf", 2),
    ("Pronunciamiento-MMM2022-vf.pdf", 3),
]

base_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable"

keywords = [
    r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del Consejo Fiscal\b",
    r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del CF\b"
]

for pdf_filename, expected_page in test_cases:
    pdf_path = f"{base_path}\\{pdf_filename}"

    print("\n" + "="*80)
    print(f"{pdf_filename} - Page {expected_page}")
    print("="*80)

    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[expected_page - 1]  # 0-indexed
            words = page.extract_words(extra_attrs=["size", "fontname"])

            # Filter by font size 11.0-15.0pt (keyword detection range)
            candidate_words = [w for w in words if "size" in w and 11.0 <= w["size"] <= 15.0]

            # Group words by Y-position (same logic as keyword search)
            lines = {}
            for word in candidate_words:
                top_pos = round(word.get("top", 0), 1)  # Round to 0.1pt
                if top_pos not in lines:
                    lines[top_pos] = []
                lines[top_pos].append(word)

            # Look for lines containing keyword parts
            keyword_lines = []
            for top_pos in sorted(lines.keys()):
                line_words = sorted(lines[top_pos], key=lambda w: w.get("x0", 0))
                line_text = " ".join([w.get("text", "") for w in line_words])

                # Check if any keyword pattern matches
                matched = False
                for i, keyword_pattern in enumerate(keywords, 1):
                    if re.match(keyword_pattern, line_text, re.IGNORECASE):
                        matched = True
                        print(f"\n  MATCH (Pattern {i})! Y={top_pos:.1f}pt")
                        print(f"    Line: '{line_text[:80]}...'")
                        break

                # Check if line contains keyword parts (even if not matching)
                if any(part in line_text for part in ["Opinión", "Consejo", "Fiscal", "CF"]):
                    keyword_lines.append((top_pos, line_text, line_words))

            # Show keyword-related lines
            if keyword_lines:
                print(f"\n  Found {len(keyword_lines)} lines with keyword parts:")
                for top_pos, line_text, line_words in keyword_lines[:5]:
                    print(f"    Y={top_pos:.1f}pt: '{line_text[:70]}...'")
                    # Show individual words
                    for w in line_words[:8]:
                        if any(part in w.get("text", "") for part in ["Opinión", "Consejo", "Fiscal", "CF"]):
                            print(f"      - '{w.get('text', '')}' (Y={w.get('top', 0):.1f}pt, X={w.get('x0', 0):.1f}pt, size={w.get('size', 0):.1f}pt)")
            else:
                print(f"\n  NO keyword parts found in lines")

    except FileNotFoundError:
        print(f"  ERROR: File not found")
    except Exception as e:
        print(f"  ERROR: {e}")

print("\n" + "="*80)
