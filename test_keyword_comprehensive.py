"""
Comprehensive test for keyword detection with:
1. Arabic numerals (1, 2, 3, 4...)
2. Roman numerals (I, II, III, IV...)
3. Left-alignment filtering (reject centered titles)
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

def find_opinion_keyword_position(pdf, keywords):
    """Updated version with left-alignment check"""
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

            # Get x position of first word to check alignment
            first_word_x = line_words[0].get("x0", 0)

            # Check if text is LEFT-ALIGNED (not centered)
            is_left_aligned = first_word_x < 120

            # For debugging, show all "Opinión" matches with their alignment
            if "opinión" in line_text.lower():
                alignment = "LEFT" if is_left_aligned else "CENTER/RIGHT"
                print(f"      Found 'Opinión' on page {page_num}: X={first_word_x:.1f}pt [{alignment}]")
                print(f"         Text: '{line_text[:70]}...'")

            if not is_left_aligned:
                continue

            # Check if any keyword pattern matches at line start
            for keyword_pattern in keywords:
                if re.match(keyword_pattern, line_text, re.IGNORECASE):
                    print(f"\n      ✓ MATCHED KEYWORD on page {page_num}: '{line_text[:70]}...'")
                    print(f"      ✓ Position: Y={top_pos:.1f}pt, X={first_word_x:.1f}pt (LEFT-aligned)")
                    print(f"      → Starting extraction from page {page_num}, position Y={top_pos}pt\n")
                    return (page_num, top_pos)

    print("      ℹ️ Keyword not found. Extracting from page 1.")
    return (1, 0)


# Test cases
test_cases = [
    ("CF-Informe-IAPM21-vF.pdf", 2, "Plain keyword"),
    ("Informe-DCRF2024-vf.pdf", 5, "Arabic numeral: 4."),
]

base_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable"

# Updated keyword patterns with Roman numeral support and optional numbers
keywords = [
    r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del Consejo Fiscal",  # Optional number
    r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del CF"                # Optional number
]

print("\n" + "="*100)
print("COMPREHENSIVE KEYWORD DETECTION TEST")
print("="*100)
print("\nFeatures being tested:")
print("  ✓ Arabic numerals (1, 2, 3, 4...)")
print("  ✓ Roman numerals (I, II, III, IV...)")
print("  ✓ Left-alignment filtering (X < 120pt)")
print("="*100)

for filename, expected_page, description in test_cases:
    filepath = os.path.join(base_path, filename)

    if not os.path.exists(filepath):
        print(f"\n⚠️ Skipping {filename} (not found)")
        continue

    print(f"\n{'─'*100}")
    print(f"Test: {filename}")
    print(f"Expected: Page {expected_page} ({description})")
    print('─'*100)

    with pdfplumber.open(filepath) as pdf:
        start_page, start_pos = find_opinion_keyword_position(pdf, keywords)

        if start_page == expected_page:
            print(f"✅ SUCCESS: Keyword detected on page {start_page} as expected!")
        elif start_page == 1:
            print(f"❌ FAILED: Keyword NOT found (would extract from page 1)")
        else:
            print(f"⚠️ UNEXPECTED: Found on page {start_page}, expected page {expected_page}")

print("\n" + "="*100)
print("TEST VALIDATION PATTERNS")
print("="*100)

# Show which patterns the regex will match
test_patterns = [
    "Opinión del Consejo Fiscal",
    "4. Opinión del Consejo Fiscal",
    "II. Opinión del CF",
    "  Opinión del CF",
    "III. Opinión del Consejo Fiscal sobre",
    "10. Opinión del CF",
]

print("\nPattern matching validation:")
for pattern in test_patterns:
    matches = any(re.match(kw, pattern, re.IGNORECASE) for kw in keywords)
    status = "✓" if matches else "✗"
    print(f"  {status} '{pattern}'")

print("\n" + "="*100 + "\n")
