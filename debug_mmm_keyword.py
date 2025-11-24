"""
Direct test of keyword detection on MMM PDF - minimal imports
"""
import sys
import codecs
import pdfplumber
import re

# Fix UTF-8 encoding
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Test file
pdf_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\CF-Informe-MMM2124-cNotaAclaratoria-28-de-agosto-VF-publicada.pdf"

# Keyword patterns
keywords = [
    r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del Consejo Fiscal\b",
    r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del CF\b"
]

print("="*80)
print("DEBUGGING MMM PDF KEYWORD DETECTION")
print("="*80)

with pdfplumber.open(pdf_path) as pdf:
    print(f"\nTotal pages: {len(pdf.pages)}")

    # Focus on page 7 (index 6)
    page_num = 7
    page = pdf.pages[6]

    print(f"\n{'='*80}")
    print(f"ANALYZING PAGE {page_num}")
    print(f"{'='*80}")

    # Extract words
    words = page.extract_words(extra_attrs=["size", "top", "fontname"])
    print(f"\n1. Extracted {len(words)} words from page {page_num}")

    # Check font metadata
    has_font_metadata = any("size" in w for w in words)
    words_with_size = [w for w in words if "size" in w]
    words_without_size = [w for w in words if "size" not in w]
    print(f"2. has_font_metadata = {has_font_metadata}")
    print(f"   Words WITH size: {len(words_with_size)}")
    print(f"   Words WITHOUT size: {len(words_without_size)}")

    # Find "Opinión" words specifically
    opinion_words = [w for w in words if "opinión" in w["text"].lower()]
    print(f"\n2b. Found {len(opinion_words)} words containing 'Opinión':")
    for w in opinion_words:
        print(f"   '{w['text']}' → size={w.get('size', 'N/A')}, x0={w.get('x0', 'N/A'):.1f}pt")

    # Determine candidate words
    if has_font_metadata:
        candidate_words = [
            w for w in words
            if "size" in w and 11.0 <= w["size"] <= 15.0  # FIXED: Expanded to 15.0pt
        ]
        print(f"3. Using font filtering: {len(candidate_words)} candidates (11.0-15.0pt)")
    else:
        candidate_words = words
        print(f"3. No font metadata → Using all words: {len(candidate_words)} candidates")

    # Group into lines
    lines = {}
    for word in candidate_words:
        if "top" not in word:
            continue
        top = round(word["top"], 1)
        if top not in lines:
            lines[top] = []
        lines[top].append(word)

    print(f"4. Reconstructed {len(lines)} lines")

    # Check lines containing "Opinión"
    print(f"\n5. Lines containing 'Opinión':")
    for top_pos in sorted(lines.keys()):
        line_words = sorted(lines[top_pos], key=lambda w: w.get("x0", 0))
        line_text = " ".join([w["text"] for w in line_words]).strip()

        if "opinión" in line_text.lower():
            first_word_x = line_words[0].get("x0", 0)
            is_left_aligned = first_word_x < 120

            print(f"\n   Line text: '{line_text}'")
            print(f"   Position: Y={top_pos:.1f}pt, X={first_word_x:.1f}pt")
            print(f"   LEFT-aligned (X < 120pt): {is_left_aligned}")

            if is_left_aligned:
                # Test patterns
                for i, keyword_pattern in enumerate(keywords, 1):
                    match = re.match(keyword_pattern, line_text, re.IGNORECASE)
                    print(f"   Pattern {i} match: {match is not None}")
                    if match:
                        print(f"      ✓✓✓ MATCH FOUND! ✓✓✓")
                        print(f"      Matched text: '{match.group()}'")
            else:
                print(f"   → SKIPPED (not left-aligned)")

print(f"\n{'='*80}")
print("END DEBUG")
print(f"{'='*80}")
