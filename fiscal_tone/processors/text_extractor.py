"""
Text Extraction from PDF Documents.

This module provides text extraction functionality for both editable (font-based)
and scanned (OCR) PDFs. It implements position-based filtering to exclude
headers, footers, and margin annotations.

Main Functions:
    extract_text_from_editable_pdf: Extract text using font-based filtering
    extract_text_from_editable_pdfs_batch: Batch extraction for all editable PDFs
    extract_text_from_scanned_pdf: Extract text using OCR (Tesseract)

Key Features:
    - Font size filtering (default 10.5-11.9pt for body text)
    - Position-based header/footer exclusion
    - "Opinión del CF" keyword detection for content start
    - Automatic stop at "Anexo" sections
    - Paragraph detection using vertical spacing

Example:
    >>> from fiscal_tone.processors.text_extractor import extract_text_from_editable_pdfs_batch
    >>> records = extract_text_from_editable_pdfs_batch("data/raw/editable")
"""

from __future__ import annotations

import codecs
import json
import os
import re
import sys
from pathlib import Path
from timeit import default_timer as timer
from typing import Any

# Fix Windows console encoding for UTF-8 output (handles accented characters)
if sys.platform == "win32":
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "replace")

import pdfplumber

# Default extraction parameters
DEFAULT_FONT_MIN = 10.5
DEFAULT_FONT_MAX = 11.9
DEFAULT_VERTICAL_THRESHOLD = 15
DEFAULT_HEADER_CUTOFF_FIRST = 100
DEFAULT_HEADER_CUTOFF_SUBSEQUENT = 70
DEFAULT_FOOTER_CUTOFF = 85
DEFAULT_FOOTER_CUTOFF_LAST = 120
DEFAULT_LEFT_MARGIN = 70
DEFAULT_RIGHT_MARGIN = 70

# Font sizes commonly used for footnotes, page numbers, superscripts
EXCLUDED_FONT_SIZES = {9.5, 8.5, 8.4, 7.9, 7.0, 6.5, 6.0, 5.5}


def find_opinion_keyword_position(
    pdf: pdfplumber.PDF,
    keywords: list[str],
    font_min: float = DEFAULT_FONT_MIN,
    font_max: float = DEFAULT_FONT_MAX,
) -> tuple[int, float]:
    """
    Search for 'Opinión del Consejo Fiscal' or 'Opinión del CF' keywords.

    The Fiscal Council's actual opinion often starts after introductory content,
    marked by these specific headers. This function locates where the opinion begins.

    Args:
        pdf: pdfplumber PDF object.
        keywords: List of regex patterns to search for.
        font_min: Minimum font size for body text reference.
        font_max: Maximum font size for body text reference.

    Returns:
        Tuple of (start_page, start_top_position) where extraction should begin.
        If keyword not found, returns (1, 0) to extract from beginning.
    """
    print("   Searching for 'Opinión del' keyword starting from page 2...")

    # Search from page 2 onwards (skip page 1 which may have summaries)
    for page_num, page in enumerate(pdf.pages[1:], start=2):
        words = page.extract_words(extra_attrs=["size", "top", "fontname"])

        # Check if PDF has font size metadata
        has_font_metadata = any("size" in w for w in words)

        if has_font_metadata:
            # Filter by broader font size range (keywords appear as section headers)
            candidate_words = [
                w for w in words
                if "size" in w and 11.0 <= w["size"] <= 15.0
            ]
        else:
            candidate_words = words

        if not candidate_words:
            continue

        # Group words by vertical position (same line)
        lines: dict[float, list[dict]] = {}
        for word in candidate_words:
            if "top" not in word:
                continue
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

            if not is_left_aligned:
                continue

            # Check if any keyword pattern matches at line start
            for keyword_pattern in keywords:
                if re.match(keyword_pattern, line_text):
                    print(f"      Found keyword on page {page_num}: '{line_text[:70]}...'")
                    return (page_num, top_pos)

    # Keyword not found - extract from beginning
    print("      Keyword not found. Extracting from page 1.")
    return (1, 0)


def extract_text_from_editable_pdf(
    file_path: str | Path,
    font_min: float = DEFAULT_FONT_MIN,
    font_max: float = DEFAULT_FONT_MAX,
    exclude_bold: bool = False,
    vertical_threshold: int = DEFAULT_VERTICAL_THRESHOLD,
    first_page_header_cutoff: int = DEFAULT_HEADER_CUTOFF_FIRST,
    subsequent_header_cutoff: int = DEFAULT_HEADER_CUTOFF_SUBSEQUENT,
    footer_cutoff_distance: int = DEFAULT_FOOTER_CUTOFF,
    last_page_footer_cutoff: int = DEFAULT_FOOTER_CUTOFF_LAST,
    left_margin: int = DEFAULT_LEFT_MARGIN,
    right_margin: int = DEFAULT_RIGHT_MARGIN,
    exclude_specific_sizes: bool = True,
    search_opinion_keyword: bool = True,
) -> list[dict[str, Any]]:
    """
    Extract text from a single editable PDF with position-based filtering.

    This function uses font-based filtering and position-based exclusion to
    extract clean body text while excluding headers, footers, and footnotes.

    Args:
        file_path: Path to the PDF file.
        font_min: Minimum font size for body text (default 10.5pt).
        font_max: Maximum font size for body text (default 11.9pt).
        exclude_bold: Whether to exclude bold text (default False).
        vertical_threshold: Pixels between words to detect paragraph break.
        first_page_header_cutoff: Y-position cutoff for page 1.
        subsequent_header_cutoff: Y-position cutoff for pages 2+.
        footer_cutoff_distance: Distance from bottom to exclude.
        last_page_footer_cutoff: Footer cutoff for last page.
        left_margin: Left margin cutoff in points.
        right_margin: Right margin cutoff in points.
        exclude_specific_sizes: Exclude common footnote sizes.
        search_opinion_keyword: Search for "Opinión del CF" to start extraction.

    Returns:
        List of records: [{"pdf_filename": str, "page": int, "text": str}, ...]

    Example:
        >>> records = extract_text_from_editable_pdf("document.pdf")
        >>> len(records) > 0
        True
    """
    all_records: list[dict[str, Any]] = []
    excluded_sizes = EXCLUDED_FONT_SIZES if exclude_specific_sizes else set()

    try:
        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)

            # Search for "Opinión del" keyword
            start_page = 1
            start_top_position = 0.0

            if search_opinion_keyword:
                keywords = [
                    r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del? Consejo Fiscal\b",
                    r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del? CF\b"
                ]
                start_page, start_top_position = find_opinion_keyword_position(
                    pdf, keywords, font_min, font_max
                )

            # Extract text from determined starting point
            for page_num, page in enumerate(pdf.pages, start=1):
                # Skip pages before the keyword start page
                if page_num < start_page:
                    continue

                page_height = page.height
                page_width = page.width

                # Early Anexo detection
                raw_page_text = page.extract_text()
                if raw_page_text:
                    anexo_pattern = r"^\s*ANEXOS?(?:\s+(?:[IVXLCDM]+|\d+))?\s*:?"
                    if re.match(anexo_pattern, raw_page_text, re.IGNORECASE):
                        break

                # Determine cutoffs
                header_cutoff = first_page_header_cutoff if page_num == 1 else subsequent_header_cutoff
                footer_cutoff = page_height - (
                    last_page_footer_cutoff if page_num == total_pages else footer_cutoff_distance
                )

                # Adjust for keyword position
                effective_header_cutoff = header_cutoff
                if page_num == start_page and start_top_position > 0:
                    effective_header_cutoff = max(start_top_position - 5, 0)

                # Extract and filter words
                words = page.extract_words(extra_attrs=["size", "top", "fontname"])

                clean_words = [
                    w for w in words
                    if (
                        font_min <= w["size"] <= font_max
                        and (round(w["size"], 1) not in excluded_sizes if exclude_specific_sizes else True)
                        and ("Bold" not in w["fontname"] if exclude_bold else True)
                        and effective_header_cutoff < w["top"] < footer_cutoff
                        and left_margin < w.get("x0", 0) < (page_width - right_margin)
                    )
                ]

                if not clean_words:
                    continue

                # Paragraph detection
                page_text: list[str] = []
                paragraph_lines: list[str] = []
                last_top: float | None = None

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

                # Stop at "Anexo"
                anexo_detected = False
                match = re.search(r"(?mi)^ *Anexos?\b[\s\w]*:?", full_page_text)
                if match:
                    full_page_text = full_page_text[:match.start()].strip()
                    anexo_detected = True

                if full_page_text:
                    all_records.append({
                        "pdf_filename": os.path.basename(file_path),
                        "page": page_num,
                        "text": full_page_text
                    })

                if anexo_detected:
                    break

    except Exception as e:
        print(f"[ERROR] processing {file_path}: {e}")

    return all_records


def extract_text_from_editable_pdfs_batch(
    editable_folder: str | Path = "data/raw/editable",
    output_folder: str | Path = "data/raw",
    output_filename: str = "editable_pdfs_extracted_text.json",
    **extraction_kwargs: Any,
) -> list[dict[str, Any]]:
    """
    Extract text from ALL editable PDFs in a folder.

    Loops through all PDF files in the editable folder and saves results
    to a single consolidated JSON file.

    Args:
        editable_folder: Path to folder containing editable PDF files.
        output_folder: Path to folder where JSON will be saved.
        output_filename: Name of the output JSON file.
        **extraction_kwargs: Additional arguments passed to extract_text_from_editable_pdf.

    Returns:
        List of all extracted records.

    Example:
        >>> records = extract_text_from_editable_pdfs_batch("data/raw/editable")
        >>> len(records) > 0
        True
    """
    t0 = timer()
    editable_folder = Path(editable_folder)
    output_folder = Path(output_folder)

    all_records: list[dict[str, Any]] = []

    # Get list of PDF files
    pdf_files = sorted(editable_folder.glob("*.pdf"))
    print(f"[EXTRACT] Found {len(pdf_files)} PDF files in {editable_folder}")

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n[{i}/{len(pdf_files)}] Processing: {pdf_path.name}")

        records = extract_text_from_editable_pdf(pdf_path, **extraction_kwargs)
        all_records.extend(records)

        print(f"   Extracted {len(records)} page records")

    # Save consolidated output
    output_folder.mkdir(parents=True, exist_ok=True)
    output_path = output_folder / output_filename

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] Saved {len(all_records)} records to {output_path}")
    print(f"Time: {timer() - t0:.2f} seconds")

    return all_records


def run_extraction_stage(
    raw_pdf_folder: str | Path = "data/raw",
    output_folder: str | Path = "data/raw",
    editable_output: str = "editable_pdfs_extracted_text.json",
    scanned_output: str = "scanned_pdfs_extracted_text.json",
) -> dict[str, list[dict[str, Any]]]:
    """
    Execute the complete text extraction stage.

    Extracts text from both editable and scanned PDFs.

    Args:
        raw_pdf_folder: Base folder containing editable/ and scanned/ subfolders.
        output_folder: Folder to save extraction results.
        editable_output: Filename for editable PDF extraction results.
        scanned_output: Filename for scanned PDF extraction results.

    Returns:
        Dictionary with "editable" and "scanned" record lists.

    Example:
        >>> results = run_extraction_stage("data/raw")
        >>> "editable" in results
        True
    """
    print("=" * 70)
    print("STAGE 5-6: TEXT EXTRACTION")
    print("=" * 70)

    raw_pdf_folder = Path(raw_pdf_folder)
    results: dict[str, list[dict[str, Any]]] = {}

    # Extract from editable PDFs
    editable_folder = raw_pdf_folder / "editable"
    if editable_folder.exists():
        print("\n[EDITABLE PDFs]")
        results["editable"] = extract_text_from_editable_pdfs_batch(
            editable_folder=editable_folder,
            output_folder=output_folder,
            output_filename=editable_output,
        )
    else:
        print(f"\n[WARN] Editable folder not found: {editable_folder}")
        results["editable"] = []

    # Scanned PDFs would go here (OCR extraction)
    scanned_folder = raw_pdf_folder / "scanned"
    if scanned_folder.exists():
        print("\n[SCANNED PDFs] - OCR extraction not yet migrated")
        # TODO: Implement OCR extraction
        results["scanned"] = []
    else:
        results["scanned"] = []

    print("\n[DONE] Extraction stage complete")
    print(f"Editable records: {len(results['editable'])}")
    print(f"Scanned records: {len(results['scanned'])}")

    return results


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract text from PDF documents"
    )
    parser.add_argument(
        "--input",
        "-i",
        default="data/raw",
        help="Input folder with editable/scanned subfolders (default: data/raw)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="data/raw",
        help="Output folder for JSON files (default: data/raw)",
    )

    args = parser.parse_args()

    results = run_extraction_stage(
        raw_pdf_folder=args.input,
        output_folder=args.output,
    )

    total = len(results.get("editable", [])) + len(results.get("scanned", []))
    print(f"\nExtraction complete. {total} records extracted.")
