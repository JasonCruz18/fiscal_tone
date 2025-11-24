"""
Quick test of keyword detection on CF-Informe-IAPM21-vF.pdf
"""

import sys
import os
import re
import json
from time import time as timer

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

import pdfplumber

# Import the helper function
sys.path.insert(0, r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone")

# Inline the function for testing
def find_opinion_keyword_position(pdf, keywords, font_min, font_max):
    """Searches for 'Opinión del Consejo Fiscal' or 'Opinión del CF' keywords starting from page 2."""
    print("   🔍 Searching for 'Opinión del' keyword starting from page 2...")

    for page_num, page in enumerate(pdf.pages[1:], start=2):
        words = page.extract_words(extra_attrs=["size", "top", "fontname"])

        # Filter by broader font size range (keywords appear as section headers at 11-13pt)
        candidate_words = [
            w for w in words
            if 11.0 <= w["size"] <= 13.0  # Broader range to capture section headers
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


# Test file
test_file = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\CF-Informe-IAPM21-vF.pdf"

print("\n" + "="*100)
print("TESTING KEYWORD DETECTION")
print("="*100)
print(f"\nFile: {os.path.basename(test_file)}")
print("Expected: Should find 'Opinión del Consejo Fiscal' on page 2\n")

with pdfplumber.open(test_file) as pdf:
    keywords = [
        r"^Opinión del Consejo Fiscal",
        r"^Opinión del CF"
    ]

    start_page, start_pos = find_opinion_keyword_position(pdf, keywords, 11.0, 11.9)

    print(f"\nResult:")
    print(f"  Start page: {start_page}")
    print(f"  Start position: {start_pos}pt")

    if start_page > 1:
        print("\n✅ Keyword detection SUCCESSFUL!")
    else:
        print("\n⚠️ Keyword NOT found - will extract from beginning")

print("\n" + "="*100)
