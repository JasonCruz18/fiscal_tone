"""
Diagnostic script to understand pdfplumber word extraction behavior
"""

import pdfplumber

test_file = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Comunicado-Congreso-vf.pdf"

with pdfplumber.open(test_file) as pdf:
    page = pdf.pages[0]  # First page

    print(f"Page dimensions: {page.width}x{page.height}")
    print()

    # Extract words with attributes
    words = page.extract_words(extra_attrs=["size", "top", "fontname", "x0"])

    print(f"Total words extracted: {len(words)}")
    print()

    # Show first 20 words to understand structure
    print("First 20 words:")
    for i, word in enumerate(words[:20]):
        print(f"{i+1}. '{word['text']}' | size:{word['size']:.1f} | top:{word['top']:.1f} | x0:{word['x0']:.1f} | font:{word['fontname']}")

    print("\n" + "="*80)

    # Filter by 11.0pt size only (like v1)
    words_11pt = [w for w in words if 11.0 <= w["size"] <= 11.9]
    print(f"\nWords with size 11.0-11.9pt: {len(words_11pt)}")
    print("First 20:")
    for i, word in enumerate(words_11pt[:20]):
        print(f"{i+1}. '{word['text']}' | size:{word['size']:.1f} | top:{word['top']:.1f}")

    print("\n" + "="*80)

    # Filter by position (like v2)
    header_cutoff = 150
    footer_cutoff = page.height - 100
    left_margin = 70
    right_margin = page.width - 70

    words_positioned = [
        w for w in words
        if (
            11.0 <= w["size"] <= 11.9
            and header_cutoff < w["top"] < footer_cutoff
            and left_margin < w["x0"] < right_margin
        )
    ]

    print(f"\nWords with position filtering (11.0-11.9pt, Y: {header_cutoff}-{footer_cutoff:.1f}, X: {left_margin}-{right_margin:.1f}):")
    print(f"Total: {len(words_positioned)}")
    print("First 20:")
    for i, word in enumerate(words_positioned[:20]):
        print(f"{i+1}. '{word['text']}' | size:{word['size']:.1f} | top:{word['top']:.1f} | x0:{word['x0']:.1f}")

    print("\n" + "="*80)

    # Check word length distribution
    word_lengths = [len(w['text']) for w in words_positioned]
    single_char = sum(1 for length in word_lengths if length == 1)
    multi_char = sum(1 for length in word_lengths if length > 1)

    print(f"\nWord length distribution for positioned words:")
    print(f"  Single character: {single_char} ({100*single_char/len(words_positioned):.1f}%)")
    print(f"  Multiple characters: {multi_char} ({100*multi_char/len(words_positioned):.1f}%)")

    # Sample of single vs multi-character
    single_chars = [w['text'] for w in words_positioned if len(w['text']) == 1][:20]
    multi_chars = [w['text'] for w in words_positioned if len(w['text']) > 1][:20]

    print(f"\nSample single-char words: {single_chars}")
    print(f"Sample multi-char words: {multi_chars}")
