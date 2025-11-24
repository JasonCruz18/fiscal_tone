"""
Direct test of extraction function - bypasses pipeline initialization
"""

import sys
import os
import re
import json

# Set UTF-8 encoding
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

import pdfplumber

# Copy the helper function directly
def find_opinion_keyword_position(pdf, keywords, font_min, font_max):
    """
    Searches for 'Opinión del Consejo Fiscal' or 'Opinión del CF' keywords starting from page 2.
    """
    print("   🔍 Searching for 'Opinión del' keyword starting from page 2...")
    print("      Requirements: LEFT-aligned (x < 120pt), font 11-13pt, from page 2+")

    for page_num, page in enumerate(pdf.pages[1:], start=2):
        words = page.extract_words(extra_attrs=["size", "top", "fontname"])

        candidate_words = [
            w for w in words
            if 11.0 <= w["size"] <= 13.0
        ]

        if not candidate_words:
            continue

        lines = {}
        for word in candidate_words:
            top = round(word["top"], 1)
            if top not in lines:
                lines[top] = []
            lines[top].append(word)

        for top_pos in sorted(lines.keys()):
            line_words = sorted(lines[top_pos], key=lambda w: w.get("x0", 0))
            line_text = " ".join([w["text"] for w in line_words]).strip()
            first_word_x = line_words[0].get("x0", 0)

            is_left_aligned = first_word_x < 120

            if not is_left_aligned:
                continue

            for keyword_pattern in keywords:
                if re.match(keyword_pattern, line_text, re.IGNORECASE):
                    print(f"      ✓ Found keyword on page {page_num}: '{line_text[:70]}...'")
                    print(f"      ✓ Position: Y={top_pos:.1f}pt, X={first_word_x:.1f}pt (LEFT-aligned)")
                    print(f"      → Starting extraction from page {page_num}, position Y={top_pos}pt")
                    return (page_num, top_pos)

    print("      ℹ️ Keyword not found. Extracting from page 1.")
    return (1, 0)


# Test file
test_file = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Informe-DCRF2024-vf.pdf"

print("\n" + "="*100)
print("KEYWORD DETECTION TEST WITH ACTUAL EXTRACTION PREVIEW")
print("="*100)
print(f"\nFile: {os.path.basename(test_file)}")
print("Expected: Should find '4. Opinión del Consejo Fiscal' on page 5")
print("\n" + "="*100 + "\n")

with pdfplumber.open(test_file) as pdf:
    # Test keyword detection
    keywords = [
        r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del Consejo Fiscal",
        r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del CF"
    ]

    start_page, start_top_position = find_opinion_keyword_position(pdf, keywords, 11.0, 11.9)

    print(f"\n{'─'*100}")
    print("KEYWORD DETECTION RESULT")
    print('─'*100)
    print(f"  Start page: {start_page}")
    print(f"  Start Y position: {start_top_position}pt")

    if start_page == 5:
        print("\n✅ CORRECT: Keyword found on page 5 as expected!")
    elif start_page == 1:
        print("\n❌ FAILED: Keyword NOT detected - would extract from page 1")
    else:
        print(f"\n⚠️ UNEXPECTED: Found on page {start_page}, expected page 5")

    # Show pages to be processed
    print(f"\n{'─'*100}")
    print("PAGES TO BE PROCESSED:")
    print('─'*100)
    if start_page == 1:
        print("  Pages 1-10 (all pages - no keyword found)")
    else:
        print(f"  Pages {start_page}-{len(pdf.pages)} (starting from keyword)")
        print(f"  Pages 1-{start_page-1} will be SKIPPED")

    # Show preview of first few words that would be extracted
    print(f"\n{'─'*100}")
    print("EXTRACTION PREVIEW (first 50 words from start page):")
    print('─'*100)

    page = pdf.pages[start_page - 1]  # 0-indexed
    words = page.extract_words(extra_attrs=["size", "top"])

    # Filter by font range 11.0-11.9
    body_words = [w for w in words if 11.0 <= w["size"] <= 11.9]

    # Filter by position (after keyword position if applicable)
    if start_top_position > 0:
        body_words = [w for w in body_words if w["top"] >= start_top_position - 5]

    # Get first 50 words
    preview_words = body_words[:50]
    preview_text = " ".join([w["text"] for w in preview_words])

    print(f"\n{preview_text}...\n")

print("\n" + "="*100 + "\n")
