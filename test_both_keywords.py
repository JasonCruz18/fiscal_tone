"""
Test keyword detection with updated regex on both PDFs
"""

import sys
import os
import re

# Set UTF-8 encoding
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

import pdfplumber

def find_opinion_keyword_position(pdf, keywords, font_min, font_max):
    """Updated version with flexible regex"""
    print("   🔍 Searching for 'Opinión del' keyword starting from page 2...")

    for page_num, page in enumerate(pdf.pages[1:], start=2):
        words = page.extract_words(extra_attrs=["size", "top", "fontname"])

        candidate_words = [
            w for w in words
            if 11.0 <= w["size"] <= 13.0
        ]

        if not candidate_words:
            continue

        # Reconstruct text line by line
        lines = {}
        for word in candidate_words:
            top = round(word["top"], 1)
            if top not in lines:
                lines[top] = []
            lines[top].append(word)

        # Check each line for keyword at the beginning
        for top_pos in sorted(lines.keys()):
            line_words = sorted(lines[top_pos], key=lambda w: w.get("x0", 0))
            line_text = " ".join([w["text"] for w in line_words]).strip()

            for keyword_pattern in keywords:
                if re.match(keyword_pattern, line_text, re.IGNORECASE):
                    print(f"      ✓ Found keyword on page {page_num}: '{line_text[:80]}...'")
                    print(f"      → Starting extraction from page {page_num}, position Y={top_pos}pt")
                    return (page_num, top_pos)

    print("      ℹ️ Keyword not found. Extracting from page 1.")
    return (1, 0)


# Test both PDFs
test_cases = [
    ("CF-Informe-IAPM21-vF.pdf", 2, "Opinión del Consejo Fiscal sobre las proyecciones..."),
    ("Informe-DCRF2024-vf.pdf", 5, "4. Opinión del Consejo Fiscal"),
]

base_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable"

# Updated keyword patterns with section number support
keywords = [
    r"^\s*\d*\.?\s*Opinión del Consejo Fiscal",
    r"^\s*\d*\.?\s*Opinión del CF"
]

print("\n" + "="*100)
print("TESTING KEYWORD DETECTION WITH UPDATED REGEX")
print("="*100)

for filename, expected_page, expected_text in test_cases:
    filepath = os.path.join(base_path, filename)

    if not os.path.exists(filepath):
        print(f"\n⚠️ Skipping {filename} (not found)")
        continue

    print(f"\n{'─'*100}")
    print(f"Test: {filename}")
    print(f"Expected: Find on page {expected_page} - '{expected_text}'")
    print('─'*100)

    with pdfplumber.open(filepath) as pdf:
        start_page, start_pos = find_opinion_keyword_position(pdf, keywords, 11.0, 11.9)

        if start_page == expected_page:
            print(f"\n✅ SUCCESS: Keyword detected on page {start_page} as expected!")
        elif start_page == 1:
            print(f"\n❌ FAILED: Keyword NOT found (would extract from page 1)")
        else:
            print(f"\n⚠️ UNEXPECTED: Found on page {start_page}, expected page {expected_page}")

print("\n" + "="*100)
print("TESTS COMPLETE")
print("="*100 + "\n")
