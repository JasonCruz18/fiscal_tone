"""
Test script for comparing extract_text_from_single_pdf vs extract_text_from_single_pdf_v2

This script isolates and tests only the text extraction functions to validate
the improvements in v2 (position-based filtering for headers/footers/footnotes).
"""

import os
import sys
import re
import json
import pdfplumber
from time import time as timer

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


def extract_text_from_single_pdf(file_path, FONT_MIN=11.0, FONT_MAX=11.9, exclude_bold=True, vertical_threshold=10):
    """Original extraction function (v1)"""
    t0 = timer()
    print("🧠 Starting text extraction (v1 - original)...\n")
    all_records = []

    try:
        print(f"📄 Processing: {file_path}")
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                words = page.extract_words(extra_attrs=["size", "top", "fontname"])
                clean_words = [w for w in words if FONT_MIN <= w["size"] <= FONT_MAX and ("Bold" not in w["fontname"] if exclude_bold else True)]

                if not clean_words:
                    continue

                page_text = []
                paragraph_lines = []
                last_top = None

                for word in clean_words:
                    line_text = word["text"]
                    top = word["top"]

                    if last_top is not None and top - last_top > vertical_threshold:
                        if paragraph_lines:
                            page_text.append(" ".join(paragraph_lines))
                        paragraph_lines = [line_text]
                    else:
                        paragraph_lines.append(line_text)

                    last_top = top

                if paragraph_lines:
                    page_text.append(" ".join(paragraph_lines))

                full_page_text = "\n\n".join(page_text)

                match = re.search(r"(?mi)^ *Anexos?\b[\s\w]*:?", full_page_text)
                if match:
                    full_page_text = full_page_text[:match.start()].strip()
                    print(f"🛑 'Anexo' detected on page {page_num}. Truncating content.")

                all_records.append({
                    "filename": os.path.basename(file_path),
                    "page": page_num,
                    "text": full_page_text
                })

        if not all_records:
            print("⚠️ No text extracted from the PDF.")
            return []

        # Save to JSON
        json_filename = os.path.splitext(os.path.basename(file_path))[0] + "_v1_test.json"
        json_file_path = os.path.join(os.path.dirname(file_path), json_filename)
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(all_records, f, ensure_ascii=False, indent=4)

        print(f"📂 Text saved to: {json_file_path}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return []

    t1 = timer()
    print(f"✅ Extraction complete. Pages: {len(all_records)}, Time: {t1 - t0:.2f}s")
    return all_records


def extract_text_from_single_pdf_v2(
    file_path,
    FONT_MIN=10.5,
    FONT_MAX=11.5,
    exclude_bold=False,
    vertical_threshold=10,
    first_page_header_cutoff=150,
    subsequent_header_cutoff=100,
    footer_cutoff_distance=100,
    left_margin=70,
    right_margin=70,
    exclude_specific_sizes=True
):
    """Enhanced extraction function (v2) with position-based filtering"""
    t0 = timer()
    print("🧠 Starting enhanced text extraction (v2)...\n")
    all_records = []

    EXCLUDED_SIZES = {9.5, 8.5, 8.4, 7.9, 7.0, 6.5, 6.0, 5.5} if exclude_specific_sizes else set()

    try:
        print(f"📄 Processing: {file_path}")
        print(f"   Font range: {FONT_MIN}pt - {FONT_MAX}pt")
        print(f"   Position filtering: ENABLED")
        print(f"   Excluded sizes: {sorted(EXCLUDED_SIZES)}")
        print()

        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_height = page.height
                page_width = page.width

                header_cutoff = first_page_header_cutoff if page_num == 1 else subsequent_header_cutoff
                footer_cutoff = page_height - footer_cutoff_distance

                print(f"   Page {page_num}: {page_width:.1f}x{page_height:.1f}pt (header>{header_cutoff}pt, footer<{footer_cutoff:.1f}pt)")

                # NOTE: Do NOT request "x0" in extra_attrs as it causes character-level extraction in some PDFs
                words = page.extract_words(extra_attrs=["size", "top", "fontname"])

                clean_words = [
                    w for w in words
                    if (
                        FONT_MIN <= w["size"] <= FONT_MAX
                        and (round(w["size"], 1) not in EXCLUDED_SIZES if exclude_specific_sizes else True)
                        and ("Bold" not in w["fontname"] if exclude_bold else True)
                        and header_cutoff < w["top"] < footer_cutoff
                        # x0 is available by default in word dict
                        and left_margin < w.get("x0", 0) < (page_width - right_margin)
                    )
                ]

                if not clean_words:
                    print(f"      ⚠️ No words matched filters on page {page_num}")
                    continue

                print(f"      ✓ Filtered: {len(words)} words → {len(clean_words)} words")

                page_text = []
                paragraph_lines = []
                last_top = None

                for word in clean_words:
                    line_text = word["text"]
                    top = word["top"]

                    if last_top is not None and top - last_top > vertical_threshold:
                        if paragraph_lines:
                            page_text.append(" ".join(paragraph_lines))
                        paragraph_lines = [line_text]
                    else:
                        paragraph_lines.append(line_text)

                    last_top = top

                if paragraph_lines:
                    page_text.append(" ".join(paragraph_lines))

                full_page_text = "\n\n".join(page_text)

                match = re.search(r"(?mi)^ *Anexos?\b[\s\w]*:?", full_page_text)
                if match:
                    full_page_text = full_page_text[:match.start()].strip()
                    print(f"      🛑 'Anexo' detected. Truncating.")

                print(f"      ✓ Extracted {len(page_text)} paragraphs ({len(full_page_text)} chars)")

                all_records.append({
                    "filename": os.path.basename(file_path),
                    "page": page_num,
                    "text": full_page_text
                })

        if not all_records:
            print("⚠️ No text extracted.")
            return []

        # Save to JSON
        json_filename = os.path.splitext(os.path.basename(file_path))[0] + "_v2_test.json"
        json_file_path = os.path.join(os.path.dirname(file_path), json_filename)
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(all_records, f, ensure_ascii=False, indent=4)

        print(f"📂 Text saved to: {json_file_path}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return []

    t1 = timer()
    print(f"✅ Extraction complete. Pages: {len(all_records)}, Time: {t1 - t0:.2f}s")
    return all_records


def compare_extractions(v1_records, v2_records):
    """Compare extraction results and identify key differences"""
    print("\n" + "="*100)
    print("EXTRACTION COMPARISON ANALYSIS")
    print("="*100)

    print(f"\n📊 Statistics:")
    print(f"   v1 pages: {len(v1_records)}")
    print(f"   v2 pages: {len(v2_records)}")

    # Combine all text for pattern checking
    v1_text = " ".join([r['text'] for r in v1_records])
    v2_text = " ".join([r['text'] for r in v2_records])

    print(f"\n   v1 total chars: {len(v1_text):,}")
    print(f"   v2 total chars: {len(v2_text):,}")
    print(f"   Reduction: {len(v1_text) - len(v2_text):,} chars ({100*(1-len(v2_text)/len(v1_text)):.1f}%)")

    # Check for footer contamination
    print(f"\n📋 Footer Detection:")
    v1_footer = "www.cf.gob.pe" in v1_text
    v2_footer = "www.cf.gob.pe" in v2_text
    print(f"   'www.cf.gob.pe' in v1: {'❌ YES (contaminated)' if v1_footer else '✓ NO'}")
    print(f"   'www.cf.gob.pe' in v2: {'❌ YES (contaminated)' if v2_footer else '✓ NO'}")

    # Check for page numbers
    v1_pages = re.findall(r'\b\d+\s*/\s*\d+\b', v1_text)
    v2_pages = re.findall(r'\b\d+\s*/\s*\d+\b', v2_text)
    print(f"\n📋 Page Number Detection:")
    print(f"   Page numbers in v1: {len(v1_pages)} matches {v1_pages[:3] if v1_pages else '[]'}")
    print(f"   Page numbers in v2: {len(v2_pages)} matches {v2_pages[:3] if v2_pages else '[]'}")

    # Show sample text comparison
    print(f"\n📄 Sample Text (first 400 chars):")
    print(f"\n   v1:")
    print(f"   {v1_text[:400]}...")
    print(f"\n   v2:")
    print(f"   {v2_text[:400]}...")

    print("\n" + "="*100)


if __name__ == "__main__":
    # Test file path
    test_file = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Comunicado-Congreso-vf.pdf"

    print("\n" + "="*100)
    print("PDF TEXT EXTRACTION COMPARISON TEST")
    print("="*100)
    print(f"\nTest file: {os.path.basename(test_file)}")

    # Test v1
    print("\n" + "-"*100)
    print("RUNNING v1 (original)")
    print("-"*100)
    v1_results = extract_text_from_single_pdf(
        test_file,
        FONT_MIN=11.0,
        FONT_MAX=11.9,
        exclude_bold=False,
        vertical_threshold=15
    )

    # Test v2
    print("\n" + "-"*100)
    print("RUNNING v2 (enhanced)")
    print("-"*100)
    v2_results = extract_text_from_single_pdf_v2(
        test_file,
        FONT_MIN=10.5,
        FONT_MAX=11.5,
        exclude_bold=False,
        vertical_threshold=10
    )

    # Compare results
    if v1_results and v2_results:
        compare_extractions(v1_results, v2_results)

    print("\n✅ Test complete!")
