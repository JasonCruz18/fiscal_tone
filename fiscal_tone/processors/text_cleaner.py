"""
Text Cleaning Pipeline for Fiscal Council Documents.

This module provides a multi-stage text cleaning pipeline for extracted
PDF text, removing artifacts like signatures, headers, footers, and
normalizing whitespace while preserving legitimate content.

Main Functions:
    clean_text: Apply all cleaning steps to a single text
    clean_texts_batch: Batch clean all records in a JSON file

Cleaning Pipeline (8 stages):
    1. Remove dotted signature lines
    2. Remove date + signature blocks ("Lima, DD de mes de YYYY")
    3. Remove standalone uppercase lines
    4. Remove section headers
    5. Remove graph/table titles
    6. Remove chart sub-labels
    7. Replace rare symbols
    8. Normalize whitespace

Example:
    >>> from fiscal_tone.processors.text_cleaner import clean_text
    >>> result = clean_text("Some extracted text...")
    >>> print(result['cleaned_text'])
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from timeit import default_timer as timer
from typing import Any


def clean_text(text: str, aggressive: bool = False) -> dict[str, Any]:
    """
    Apply the full text cleaning pipeline to a single text.

    Args:
        text: Raw text to clean.
        aggressive: If True, includes enumeration removal (not recommended).

    Returns:
        Dictionary with:
            - cleaned_text: The cleaned text
            - original_length: Original character count
            - cleaned_length: Cleaned character count
            - reduction_pct: Percentage reduction
            - steps_applied: List of cleaning steps applied

    Example:
        >>> result = clean_text("Lima, 23 de mayo de 2022\\n\\nSome content...")
        >>> "Lima" not in result['cleaned_text']
        True
    """
    original_length = len(text)
    steps_applied: list[str] = []

    # Step 1: Remove dotted signature lines
    text = _remove_dotted_signatures(text)
    steps_applied.append("Remove dotted signature lines")

    # Step 2: Remove date + signature blocks
    text = _remove_date_signature_blocks(text)
    steps_applied.append("Remove date + signature blocks")

    # Step 3: Remove standalone uppercase lines
    text = _remove_uppercase_lines(text)
    steps_applied.append("Remove standalone uppercase lines")

    # Step 4: Remove standalone section headers
    text = _remove_section_headers(text)
    steps_applied.append("Remove standalone section headers")

    # Step 5: Remove graph/table titles
    text = _remove_graph_table_titles(text)
    steps_applied.append("Remove graph/table titles")

    # Step 6: Remove chart sub-labels
    text = _remove_chart_labels(text)
    steps_applied.append("Remove chart sub-labels")

    # Step 7: Replace rare symbols
    text = _replace_rare_symbols(text)
    steps_applied.append("Replace rare symbols")

    # Step 8: Normalize whitespace
    text = _normalize_whitespace(text)
    steps_applied.append("Normalize whitespace")

    # Step 9: Remove enumeration (OPTIONAL - aggressive mode only)
    if aggressive:
        text = _remove_enumeration(text)
        steps_applied.append("Remove enumeration (aggressive)")

    # Step 10: Remove false paragraph breaks
    text = _remove_false_paragraph_breaks(text)
    steps_applied.append("Remove false paragraph breaks")

    cleaned_length = len(text)
    reduction_pct = (
        (original_length - cleaned_length) / original_length * 100
        if original_length > 0
        else 0.0
    )

    return {
        "cleaned_text": text,
        "original_length": original_length,
        "cleaned_length": cleaned_length,
        "reduction_pct": reduction_pct,
        "steps_applied": steps_applied,
    }


# =============================================================================
# Helper Functions for Each Cleaning Step
# =============================================================================


def _remove_dotted_signatures(text: str) -> str:
    """
    STEP 1: Remove lines with 5+ consecutive dots followed by uppercase names.

    Example: "\\n\\n................................... WALDO EPIFANIO MENDOZA BELLIDO"
    """
    pattern = r"\n*[\.…]{5,}[\s\n]*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+)(?=\n|$)"
    return re.sub(pattern, "", text)


def _remove_date_signature_blocks(text: str) -> str:
    """
    STEP 2: Remove Lima date patterns.

    Examples:
        - "Lima, 23 de mayo de 2022"
        - "Lima, 15 de agosto de 2019\\n\\nWALDO MENDOZA BELLIDO"
    """
    # Pattern: Lima, DD de mes de YYYY
    pattern = r"\n*Lima,?\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\.?[\s\n]*"
    text = re.sub(pattern, "\n\n", text)

    # Remove uppercase names/organizations that may follow
    pattern_legacy = r"\n\n([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{10,})\n\n"
    text = re.sub(pattern_legacy, "\n\n", text)

    return text


def _remove_uppercase_lines(text: str) -> str:
    """
    STEP 3: Remove lines with 3+ consecutive uppercase words.

    Examples:
        - "CONSEJO FISCAL DEL PERU"
        - "WALDO EPIFANIO MENDOZA BELLIDO"
    """
    pattern = r"\n\n([A-ZÁÉÍÓÚÑ]+(?:\s+[A-ZÁÉÍÓÚÑ]+){2,})\n\n"
    return re.sub(pattern, "\n\n", text)


def _remove_section_headers(text: str) -> str:
    """
    STEP 4: Remove section headers, titles, and chart/table labels.

    Uses helper functions to detect headers and labels.
    """
    paragraphs = text.split("\n\n")
    cleaned_paragraphs = []

    for para in paragraphs:
        para_stripped = para.strip()

        # Skip if it's a section header OR chart/table label
        if _is_section_header(para_stripped) or _is_chart_or_table_label(
            para_stripped
        ):
            continue
        else:
            cleaned_paragraphs.append(para)

    return "\n\n".join(cleaned_paragraphs)


def _is_section_header(line: str) -> bool:
    """
    Determine if a line is a section header (should be removed).

    Conditions:
        - Length < 150 characters
        - Word count < 20 words
        - Starts with uppercase letter or number
        - Does NOT end with period, exclamation mark, or question mark
        - Is NOT a date
    """
    if not line:
        return False

    words = line.split()

    return (
        len(line) > 0
        and len(line) < 150
        and len(words) > 0
        and len(words) < 20
        and line[0].isupper()
        and line[-1] not in ".!?"
        and not re.match(r"Lima,?\s+\d{1,2}\s+de", line)
    )


def _is_chart_or_table_label(line: str) -> bool:
    """
    Detect chart/table labels with numbered/lettered patterns.

    Patterns: "1: Title", "I. Section", "A) Item", "Grafico 1:", etc.
    """
    if not line or not line.strip():
        return False

    line = line.strip()

    # Pattern 1: Grafico/Tabla/Cuadro/Figura + number
    if re.match(
        r"^(Gráfico|Tabla|Cuadro|Figura|Gráf|Tab)\s+N?°?\s*\d+", line, re.IGNORECASE
    ):
        return True

    # Pattern 2: Number + colon (e.g., "1: Title")
    if re.match(r"^\d+\s*:\s*.+", line):
        return True

    # Pattern 3: Roman numeral + period or colon
    if re.match(r"^[IVXLCDM]+\s*[.:]", line):
        return True

    # Pattern 4: Letter + parenthesis (e.g., "A) Item")
    if re.match(r"^[A-Z]\s*\)\s*.+", line):
        return True

    # Pattern 5: Letter + period at start of short text
    if re.match(r"^[A-Z]\s*\.\s*.+", line) and len(line) < 100:
        return True

    return False


def _remove_graph_table_titles(text: str) -> str:
    """
    STEP 5: Remove lines starting with "Grafico", "Tabla", etc.
    """
    pattern = r"\n*(Gráfico|Tabla|Cuadro|Figura)\s+N?°?\s*\d+[^\n]*\n*"
    return re.sub(pattern, "\n", text, flags=re.IGNORECASE)


def _remove_chart_labels(text: str) -> str:
    """
    STEP 6: Remove chart panel labels like (A), (B), A), B).
    """
    # Multiple labels with parentheses on same line
    text = re.sub(r"\n+\([A-Z]\)\s[^\n]+\([A-Z]\)\s[^\n]*\n+", "\n", text)

    # Multiple labels without parentheses
    text = re.sub(r"\n+[A-Z]\)\s[^\n]+[A-Z]\)\s[^\n]*\n+", "\n", text)

    # Single chart label at start of short line
    text = re.sub(r"\n+\([A-Z]\)\s[^\n]{1,50}\n+", "\n", text)

    return text


def _replace_rare_symbols(text: str) -> str:
    """
    STEP 7: Replace rare symbols with spaces or normalized equivalents.
    """
    replacements = {
        "•": " ",
        "➢": " ",
        "►": " ",
        "■": " ",
        "▪": " ",
        "□": " ",
        "◼": " ",
        "○": " ",
        "●": " ",
        "▫": " ",
        "Ø": " ",
        "…": "...",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def _normalize_whitespace(text: str) -> str:
    """
    STEP 8: Normalize whitespace artifacts.

    Actions:
        1. Remove spaces before punctuation
        2. Replace multiple spaces with single space
        3. Replace 3+ newlines with 2 newlines
        4. Strip leading/trailing whitespace
    """
    # Remove spaces before punctuation
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)

    # Replace multiple spaces with single space
    text = re.sub(r" {2,}", " ", text)

    # Replace 3+ newlines with double newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def _remove_enumeration(text: str) -> str:
    """
    STEP 9: Remove standalone enumeration patterns (OPTIONAL).

    WARNING: This removes legitimate list items. Only use in aggressive mode.
    """
    pattern = r"\n\n([a-z]|[ivxIVX]+|\d+)\)\s*\n\n"
    return re.sub(pattern, "\n\n", text)


def _remove_false_paragraph_breaks(text: str) -> str:
    """
    STEP 10: Remove false paragraph breaks before lowercase letters.

    A paragraph NEVER starts with a lowercase letter in proper Spanish text.
    """
    # Remove \n\n before lowercase letters
    text = re.sub(r"\n\n([a-záéíóúñü])", r" \1", text)

    # Remove \n\n before years
    text = re.sub(r"\n\n([12]\d{3})", r" \1", text)

    # Remove \n\n before common connectors
    connectors = r"(?:de|del|la|el|los|las|un|una|en|con|por|para|que|se|y|o|su|sus|sobre|al|ha|han|lo|le)"
    text = re.sub(r"\n\n(" + connectors + r"\s)", r" \1", text)

    return text


# =============================================================================
# Batch Processing Functions
# =============================================================================


def clean_texts_batch(
    input_json_path: str | Path,
    output_json_path: str | Path,
    aggressive: bool = False,
    verbose: bool = True,
) -> list[dict[str, Any]]:
    """
    Apply text cleaning pipeline to all records in a JSON file.

    Args:
        input_json_path: Path to input JSON file with 'text' field.
        output_json_path: Path to output JSON file.
        aggressive: If True, includes enumeration removal.
        verbose: If True, prints detailed statistics.

    Returns:
        List of cleaned records.

    Example:
        >>> records = clean_texts_batch(
        ...     "data/raw/editable_pdfs_extracted_text.json",
        ...     "data/raw/editable_pdfs_clean_extracted_text.json"
        ... )
    """
    t0 = timer()
    input_path = Path(input_json_path)
    output_path = Path(output_json_path)

    print("=" * 70)
    print("TEXT CLEANING PIPELINE - BATCH PROCESSING")
    print("=" * 70)
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Aggressive mode: {aggressive}")
    print()

    # Load input JSON
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Loaded {len(data)} records")

    # Process each record
    cleaned_data: list[dict[str, Any]] = []

    for i, record in enumerate(data, 1):
        if verbose and i % 50 == 0:
            print(f"  Processing record {i}/{len(data)}...")

        # Clean the text
        original_text = record.get("text", "")
        result = clean_text(original_text, aggressive=aggressive)

        # Create cleaned record
        cleaned_record = {
            "pdf_filename": record.get("pdf_filename", ""),
            "page": record.get("page", 0),
            "text": result["cleaned_text"],
            "original_length": result["original_length"],
            "cleaned_length": result["cleaned_length"],
            "reduction_pct": result["reduction_pct"],
        }

        cleaned_data.append(cleaned_record)

    # Calculate statistics
    total_original = sum(r["original_length"] for r in cleaned_data)
    total_cleaned = sum(r["cleaned_length"] for r in cleaned_data)
    overall_reduction = (
        (total_original - total_cleaned) / total_original * 100
        if total_original > 0
        else 0
    )

    if verbose:
        print()
        print(f"Total records: {len(data)}")
        print(f"Original characters: {total_original:,}")
        print(f"Cleaned characters: {total_cleaned:,}")
        print(f"Characters removed: {total_original - total_cleaned:,}")
        print(f"Overall reduction: {overall_reduction:.2f}%")

    # Save output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(cleaned_data)} records to {output_path}")
    print(f"Time: {timer() - t0:.2f} seconds")

    return cleaned_data


def run_cleaning_stage(
    input_folder: str | Path = "data/raw",
    output_folder: str | Path = "data/raw",
    editable_input: str = "editable_pdfs_extracted_text.json",
    editable_output: str = "editable_pdfs_clean_extracted_text.json",
    scanned_input: str = "scanned_pdfs_extracted_text.json",
    scanned_output: str = "scanned_pdfs_clean_extracted_text.json",
) -> dict[str, list[dict[str, Any]]]:
    """
    Execute the complete text cleaning stage.

    Args:
        input_folder: Folder containing extracted text JSON files.
        output_folder: Folder to save cleaned JSON files.
        editable_input: Input filename for editable PDFs.
        editable_output: Output filename for cleaned editable PDFs.
        scanned_input: Input filename for scanned PDFs.
        scanned_output: Output filename for cleaned scanned PDFs.

    Returns:
        Dictionary with "editable" and "scanned" cleaned record lists.
    """
    print("=" * 70)
    print("STAGE 7: TEXT CLEANING")
    print("=" * 70)

    input_folder = Path(input_folder)
    output_folder = Path(output_folder)
    results: dict[str, list[dict[str, Any]]] = {}

    # Clean editable PDFs
    editable_input_path = input_folder / editable_input
    if editable_input_path.exists():
        print("\n[EDITABLE PDFs]")
        results["editable"] = clean_texts_batch(
            input_json_path=editable_input_path,
            output_json_path=output_folder / editable_output,
        )
    else:
        print(f"\n[WARN] Editable input not found: {editable_input_path}")
        results["editable"] = []

    # Clean scanned PDFs
    scanned_input_path = input_folder / scanned_input
    if scanned_input_path.exists():
        print("\n[SCANNED PDFs]")
        results["scanned"] = clean_texts_batch(
            input_json_path=scanned_input_path,
            output_json_path=output_folder / scanned_output,
        )
    else:
        print(f"\n[INFO] Scanned input not found: {scanned_input_path}")
        results["scanned"] = []

    print("\n[DONE] Cleaning stage complete")
    print(f"Editable records: {len(results['editable'])}")
    print(f"Scanned records: {len(results['scanned'])}")

    return results


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Clean extracted PDF text")
    parser.add_argument(
        "--input",
        "-i",
        default="data/raw",
        help="Input folder with extracted text JSON (default: data/raw)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="data/raw",
        help="Output folder for cleaned JSON (default: data/raw)",
    )
    parser.add_argument(
        "--aggressive",
        action="store_true",
        help="Enable aggressive cleaning (removes enumeration)",
    )

    args = parser.parse_args()

    results = run_cleaning_stage(
        input_folder=args.input,
        output_folder=args.output,
    )

    total = len(results.get("editable", [])) + len(results.get("scanned", []))
    print(f"\nCleaning complete. {total} records processed.")
