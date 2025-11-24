"""
Diagnostic script to analyze why Pronunciamiento PDFs are failing text extraction
"""
import pdfplumber

# Test files with their expected keyword pages
test_cases = [
    ("Pronunciamiento-DCRF-2020-publicar.pdf", 4, "Opinión del CF sobre la DCRF"),
    ("PronunciamientoDCRF-RFSN-2021-vf.pdf", 5, "Opinión del Consejo Fiscal"),
    ("Pronunciamiento-DU-031-subnacionalvf.pdf", 2, "Opinión del Consejo Fiscal"),
    ("Pronunciamiento-MMM2022-vf.pdf", 3, "Opinión del Consejo Fiscal"),
]

base_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable"

for pdf_filename, expected_page, expected_keyword in test_cases:
    pdf_path = f"{base_path}\\{pdf_filename}"

    print("\n" + "="*80)
    print(f"ANALYZING: {pdf_filename}")
    print(f"Expected keyword on page {expected_page}: '{expected_keyword}'")
    print("="*80)

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Analyze the expected keyword page
            page = pdf.pages[expected_page - 1]  # 0-indexed
            words = page.extract_words(extra_attrs=["size", "fontname"])

            print(f"\n1. FONT SIZE ANALYSIS (Page {expected_page}):")
            # Get unique font sizes
            font_sizes = {}
            for word in words:
                if "size" in word:
                    size = round(word["size"], 1)
                    if size not in font_sizes:
                        font_sizes[size] = 0
                    font_sizes[size] += 1

            # Sort by frequency
            sorted_sizes = sorted(font_sizes.items(), key=lambda x: x[1], reverse=True)
            print(f"   Font sizes found (sorted by frequency):")
            for size, count in sorted_sizes[:10]:  # Show top 10
                print(f"      {size}pt: {count} words")

            # Check if body text is in our extraction range (11.0-12.0pt)
            body_text_count = sum(count for size, count in sorted_sizes if 11.0 <= size <= 12.0)
            total_words = sum(count for _, count in sorted_sizes)
            print(f"\n   Words in extraction range (11.0-12.0pt): {body_text_count}/{total_words} ({100*body_text_count/total_words:.1f}%)")

            # 2. Search for keyword on expected page
            print(f"\n2. KEYWORD SEARCH (Page {expected_page}):")
            keyword_parts = ["Opinión", "Consejo", "Fiscal", "CF"]
            found_keywords = []
            for word in words:
                text = word.get("text", "")
                if any(part.lower() in text.lower() for part in keyword_parts):
                    found_keywords.append({
                        "text": text,
                        "size": word.get("size", 0),
                        "x": word.get("x0", 0),
                        "y": word.get("top", 0),
                        "font": word.get("fontname", "")
                    })

            if found_keywords:
                print(f"   Found {len(found_keywords)} keyword-related words:")
                for kw in found_keywords[:15]:  # Show first 15
                    print(f"      '{kw['text']}' - size={kw['size']:.1f}pt, x={kw['x']:.1f}pt, font={kw['font']}")
            else:
                print(f"   WARNING: No keyword parts found on page {expected_page}")

            # 3. Analyze a page after the keyword (to understand body text)
            if expected_page < len(pdf.pages):
                next_page = pdf.pages[expected_page]  # Page after keyword
                next_words = next_page.extract_words(extra_attrs=["size", "fontname"])

                print(f"\n3. BODY TEXT ANALYSIS (Page {expected_page + 1}):")
                body_font_sizes = {}
                for word in next_words:
                    if "size" in word:
                        size = round(word["size"], 1)
                        if size not in body_font_sizes:
                            body_font_sizes[size] = 0
                        body_font_sizes[size] += 1

                sorted_body = sorted(body_font_sizes.items(), key=lambda x: x[1], reverse=True)
                print(f"   Font sizes on next page:")
                for size, count in sorted_body[:8]:
                    print(f"      {size}pt: {count} words")

                # Sample first 200 characters of text
                if next_words:
                    sample_text = " ".join([w.get("text", "") for w in next_words[:30]])
                    print(f"\n   Sample text: {sample_text[:150]}...")

    except FileNotFoundError:
        print(f"   ERROR: File not found: {pdf_path}")
    except Exception as e:
        print(f"   ERROR: {e}")

print("\n" + "="*80)
print("DIAGNOSIS COMPLETE")
print("="*80)
