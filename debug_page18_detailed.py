"""
Detailed analysis of page 18 in Opinion-MMM2023-2026-cNotaAclaratoria
"""
import pdfplumber
import re

pdf_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Opinion-MMM2023-2026-cNotaAclaratoria.pdf"

print("Analyzing page 18 of Opinion-MMM2023-2026-cNotaAclaratoria")
print("="*80)

with pdfplumber.open(pdf_path) as pdf:
    page = pdf.pages[17]  # Page 18 (0-indexed)

    # Extract all text
    full_text = page.extract_text()

    print("Full page text (first 500 chars):")
    print(full_text[:500] if full_text else "NO TEXT")
    print()

    # Check for "ANEXO" in various forms
    if full_text:
        # Remove all spaces and check
        no_spaces = full_text.replace(" ", "")
        if "ANEXO" in no_spaces.upper():
            print("Found 'ANEXO' when spaces removed!")
            pos = no_spaces.upper().find("ANEXO")
            print(f"  Position: {pos}")
            print(f"  Context: {no_spaces[max(0, pos-20):pos+30]}")

        # Check with regex ignoring spaces
        # Pattern: A N E X O (with optional spaces between)
        spaced_pattern = r"A\s*N\s*E\s*X\s*O"
        match = re.search(spaced_pattern, full_text, re.IGNORECASE)
        if match:
            print(f"\nFound spaced 'ANEXO': '{match.group()}'")

        # Check if page starts with ANEXO-like text
        first_100 = full_text[:100].upper().replace(" ", "")
        if "ANEXO" in first_100:
            print(f"\nPage STARTS with ANEXO (in first 100 chars)")

    print("\n" + "="*80)
    print("Extracting with paragraph reconstruction:")
    print("="*80)

    words = page.extract_words(extra_attrs=["size", "top"])

    # Build paragraph (same as extraction code)
    FONT_MIN = 10.5
    FONT_MAX = 11.9
    clean_words = [w for w in words if FONT_MIN <= w.get("size", 0) <= FONT_MAX]

    page_text = []
    paragraph_lines = []
    last_top = None
    vertical_threshold = 15

    for word in clean_words:
        line_text = word["text"]
        top = word["top"]

        if last_top is not None and abs(top - last_top) > vertical_threshold:
            if paragraph_lines:
                page_text.append(" ".join(paragraph_lines))
                paragraph_lines = []

        paragraph_lines.append(line_text)
        last_top = top

    if paragraph_lines:
        page_text.append(" ".join(paragraph_lines))

    full_page_text = "\n\n".join(page_text)

    print("Reconstructed text (first 500 chars):")
    print(full_page_text[:500])
    print()

    # Test pattern
    pattern = r"(?mi)^ *Anexos?\b[\s\w]*:?"
    match = re.search(pattern, full_page_text)
    if match:
        print(f"Pattern MATCHED: '{match.group()}'")
    else:
        print("Pattern DID NOT MATCH")

        # Try to find any line starting with A
        lines = full_page_text.split('\n')
        for i, line in enumerate(lines[:10]):  # Check first 10 lines
            if line.strip().upper().startswith('A'):
                print(f"  Line {i}: '{line[:100]}'")
