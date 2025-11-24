"""
Diagnostic script for CF-Informe-MMM2124 PDF
Analyzes page 7 to understand why keyword detection fails
"""
import sys
import codecs

# Fix UTF-8 encoding for Windows console
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

import pdfplumber
import re

pdf_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\CF-Informe-MMM2124-cNotaAclaratoria-28-de-agosto-VF-publicada.pdf"

# Current keyword patterns (from working code)
keywords = [
    r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del Consejo Fiscal",
    r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del CF"
]

print("=" * 80)
print("DIAGNOSTIC REPORT: CF-Informe-MMM2124 PDF - Page 7 Analysis")
print("=" * 80)

with pdfplumber.open(pdf_path) as pdf:
    print(f"\nTotal pages: {len(pdf.pages)}")

    # Analyze page 7 (index 6)
    if len(pdf.pages) >= 7:
        page = pdf.pages[6]  # 0-indexed
        print(f"\n{'='*80}")
        print(f"PAGE 7 ANALYSIS")
        print(f"{'='*80}")

        # Extract all words with details
        words = page.extract_words(x_tolerance=3, y_tolerance=3)

        # Find all text that contains "Opinión" or "CF"
        print("\n--- Text containing 'Opinión' or 'CF' ---")
        relevant_words = [w for w in words if 'opinión' in w['text'].lower() or w['text'].upper() == 'CF']

        for w in relevant_words:
            print(f"Text: '{w['text']}'")
            print(f"  Font: {w.get('fontname', 'N/A')}, Size: {w.get('size', 'N/A')}")
            if 'size' in w:
                print(f"  Size: {w['size']:.1f}pt")
            print(f"  Position: X={w.get('x0', 'N/A'):.1f}pt, Y={w.get('top', 'N/A'):.1f}pt" if 'x0' in w and 'top' in w else f"  Position: N/A")
            print(f"  Bold: {'Yes' if 'bold' in w.get('fontname', '').lower() else 'No'}")
            print()

        # Get full text lines
        print("\n--- All text lines on page 7 (first 1000 chars) ---")
        full_text = page.extract_text()
        print(full_text[:1000])
        print()

        # Find text in specific font size range (11.0-11.9)
        print("\n--- Text in 11.0-11.9pt font range containing 'Opinión' ---")
        body_words = [w for w in words if 'size' in w and 11.0 <= w['size'] <= 11.9 and 'opinión' in w['text'].lower()]
        for w in body_words:
            print(f"'{w['text']}' at X={w['x0']:.1f}pt, Size={w['size']:.1f}pt")

        # Find text in 11.0-13.0pt range (broader search)
        print("\n--- Text in 11.0-13.0pt font range containing 'Opinión' ---")
        broader_words = [w for w in words if 'size' in w and 11.0 <= w['size'] <= 13.0 and 'opinión' in w['text'].lower()]
        for w in broader_words:
            print(f"'{w['text']}' at X={w['x0']:.1f}pt, Size={w['size']:.1f}pt")

        # Check for left-aligned text (X < 120pt)
        print("\n--- Left-aligned text (X < 120pt) on page 7 ---")
        left_text = [w for w in words if 'x0' in w and 'size' in w and w['x0'] < 120 and w['size'] >= 10]
        print(f"Found {len(left_text)} left-aligned words")
        if left_text:
            print("First 20 left-aligned words:")
            for w in left_text[:20]:
                print(f"  '{w['text']}' (Size: {w['size']:.1f}pt, X: {w['x0']:.1f}pt)")

        # Try to reconstruct lines that might contain the keyword
        print("\n--- Reconstructed lines containing 'Opinión' or 'CF' ---")

        # Group words by approximate Y position (within 2 points)
        from itertools import groupby
        sorted_words = sorted([w for w in words if 'top' in w], key=lambda w: w['top'])

        for top_pos, line_words in groupby(sorted_words, key=lambda w: round(w['top'])):
            line_words_list = list(line_words)
            line_text = ' '.join([w['text'] for w in line_words_list])

            if 'opinión' in line_text.lower() or 'CF' in line_text:
                leftmost_x = min([w['x0'] for w in line_words_list if 'x0' in w])
                font_sizes = [w['size'] for w in line_words_list if 'size' in w]
                if font_sizes:
                    print(f"\nY={top_pos}pt, X_left={leftmost_x:.1f}pt, Fonts={min(font_sizes):.1f}-{max(font_sizes):.1f}pt")
                else:
                    print(f"\nY={top_pos}pt, X_left={leftmost_x:.1f}pt, Fonts=N/A")
                print(f"Text: {line_text[:100]}")

        # Test current keyword patterns
        print("\n" + "="*80)
        print("KEYWORD PATTERN TESTING")
        print("="*80)

        # Test with full text extraction
        for i, pattern in enumerate(keywords, 1):
            print(f"\nPattern {i}: {pattern}")
            matches = re.findall(pattern, full_text, re.IGNORECASE | re.MULTILINE)
            if matches:
                print(f"  ✓ MATCHES FOUND: {matches}")
            else:
                print(f"  ✗ NO MATCHES")

        # Test more flexible patterns
        print("\n--- Testing FLEXIBLE patterns (allow text after keyword) ---")
        flexible_keywords = [
            r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del Consejo Fiscal.*",
            r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del CF\b.*",
            r"Opinión del CF\b",
            r"Opinión del Consejo Fiscal"
        ]

        for i, pattern in enumerate(flexible_keywords, 1):
            print(f"\nFlexible Pattern {i}: {pattern}")
            matches = re.findall(pattern, full_text, re.IGNORECASE | re.MULTILINE)
            if matches:
                print(f"  ✓ MATCHES FOUND: {matches[:3]}")  # Show first 3
            else:
                print(f"  ✗ NO MATCHES")

print("\n" + "="*80)
print("END OF DIAGNOSTIC REPORT")
print("="*80)
