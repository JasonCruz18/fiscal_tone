"""
PDF Classification and Metadata Enrichment.

This module handles classification of PDFs into editable (font-based extraction)
vs scanned (OCR required) categories, and enriches document metadata.

Main Functions:
    is_editable_pdf: Check if a PDF contains extractable text
    classify_pdfs_by_type: Batch classify PDFs into editable/scanned folders
    metadata_enrichment: Add document type, number, year, month to metadata

Example:
    >>> from fiscal_tone.processors.pdf_classifier import classify_pdfs_by_type
    >>> classify_pdfs_by_type("data/raw")
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from timeit import default_timer as timer
from typing import Any

import fitz  # PyMuPDF
import pandas as pd


def is_editable_pdf(file_path: str | Path, min_text_length: int = 20) -> bool:
    """
    Check if a PDF contains extractable text (editable) vs scanned image.

    Uses PyMuPDF to extract text and checks if the total length exceeds
    the minimum threshold. PDFs with sufficient extractable text are
    considered "editable" and can use font-based extraction.

    Args:
        file_path: Path to PDF file.
        min_text_length: Minimum character count to consider as editable.

    Returns:
        True if PDF has extractable text, False if scanned/image-based.

    Example:
        >>> is_editable_pdf("document.pdf")
        True  # if it has extractable text
    """
    try:
        with fitz.open(file_path) as doc:
            total_text = "".join(page.get_text() for page in doc).strip()
            return len(total_text) >= min_text_length
    except Exception as e:
        print(f"[ERROR] reading {file_path}: {e}")
        return False


def classify_pdfs_by_type(
    classification_folder: str | Path | list[str | Path],
    editable_subfolder: str = "editable",
    scanned_subfolder: str = "scanned",
    min_text_length: int = 20,
) -> dict[str, int]:
    """
    Classify PDFs into 'editable' and 'scanned' subfolders.

    Moves all PDF files from the classification folder into two subfolders:
        - editable/: PDFs with extractable text (font-based extraction)
        - scanned/: PDFs without extractable text (require OCR)

    Args:
        classification_folder: Directory(ies) containing PDFs to classify.
        editable_subfolder: Name of subfolder for editable PDFs.
        scanned_subfolder: Name of subfolder for scanned PDFs.
        min_text_length: Minimum characters to consider PDF as editable.

    Returns:
        Dictionary with counts: {"total": N, "editable": N, "scanned": N}

    Example:
        >>> stats = classify_pdfs_by_type("data/raw")
        >>> print(f"Editable: {stats['editable']}, Scanned: {stats['scanned']}")
    """
    # Normalize to list for consistent processing
    if isinstance(classification_folder, (str, Path)):
        classification_folder = [classification_folder]

    base_folder = Path(classification_folder[0])

    # Create classification subfolders
    output_dir_editable = base_folder / editable_subfolder
    output_dir_scanned = base_folder / scanned_subfolder
    output_dir_editable.mkdir(parents=True, exist_ok=True)
    output_dir_scanned.mkdir(parents=True, exist_ok=True)

    total_files = 0
    scanned_count = 0
    editable_count = 0

    t0 = timer()
    print("[CLASSIFY] Starting PDF classification...")

    # Process all PDFs in provided folders
    for folder in classification_folder:
        folder_path = Path(folder)
        for filename in os.listdir(folder_path):
            if filename.lower().endswith(".pdf"):
                pdf_path = folder_path / filename

                # Skip if already in a subfolder
                if pdf_path.parent.name in [editable_subfolder, scanned_subfolder]:
                    continue

                total_files += 1

                # Classify and move to appropriate subfolder
                if is_editable_pdf(pdf_path, min_text_length):
                    dest = output_dir_editable / filename
                    if not dest.exists():
                        shutil.move(str(pdf_path), str(dest))
                    editable_count += 1
                else:
                    dest = output_dir_scanned / filename
                    if not dest.exists():
                        shutil.move(str(pdf_path), str(dest))
                    scanned_count += 1

    t1 = timer()

    # Print summary
    print("\n[SUMMARY]")
    print(f"Total PDFs processed: {total_files}")
    print(f"Editable PDFs: {editable_count}")
    print(f"Scanned PDFs: {scanned_count}")
    print(f"Editable folder: '{output_dir_editable}'")
    print(f"Scanned folder: '{output_dir_scanned}'")
    print(f"Time taken: {t1 - t0:.2f} seconds")

    return {
        "total": total_files,
        "editable": editable_count,
        "scanned": scanned_count,
    }


def metadata_enrichment(
    classification_folder: str | Path,
    metadata_folder: str | Path,
    metadata_json: str = "cf_metadata",
    editable_subfolder: str = "editable",
    scanned_subfolder: str = "scanned",
) -> pd.DataFrame:
    """
    Enrich metadata with extracted document information and PDF classification.

    Adds the following fields to the metadata:
        - pdf_type: "editable" or "scanned" based on folder location
        - doc_type: "Informe" or "Comunicado" extracted from doc_title
        - doc_number: Document number (leading zeros removed)
        - year: 4-digit year extracted from date
        - month: Month number (1-12) extracted from date

    Args:
        classification_folder: Directory with 'editable' and 'scanned' subfolders.
        metadata_folder: Folder containing the metadata JSON file.
        metadata_json: JSON filename without '.json' extension.
        editable_subfolder: Name of editable PDFs subfolder.
        scanned_subfolder: Name of scanned PDFs subfolder.

    Returns:
        DataFrame with enriched metadata.

    Example:
        >>> df = metadata_enrichment("data/raw", "metadata")
        >>> "pdf_type" in df.columns
        True
    """
    classification_folder = Path(classification_folder)
    metadata_folder = Path(metadata_folder)
    metadata_json_path = metadata_folder / f"{metadata_json}.json"

    # Load existing metadata
    if not metadata_json_path.exists():
        print(f"[ERROR] Metadata file not found: {metadata_json_path}")
        return pd.DataFrame()

    metadata_df = pd.read_json(metadata_json_path)

    # Initialize new columns if they don't exist
    for col in ["pdf_type", "doc_type", "doc_number", "year", "month"]:
        if col not in metadata_df.columns:
            metadata_df[col] = None

    # --- Extract Document Info from Title ---

    def extract_doc_info(row: pd.Series) -> pd.Series:
        """Extract doc_type, doc_number, and year from doc_title and date."""
        doc_title = str(row.get("doc_title", ""))

        # Regex: Capture "Informe" or "Comunicado" + optional "CF" + document number
        match = re.search(
            r"\b(Informe|Comunicado)\b(?:\s+CF)?(?:\s+(?:N[°ºo]|No))?\s*(\d{2,4})",
            doc_title,
            re.IGNORECASE,
        )
        doc_type = match.group(1).capitalize() if match else None
        doc_number = match.group(2) if match and match.lastindex >= 2 else None

        # Extract year from date column
        year_match = re.search(r"\b(\d{4})\b", str(row.get("date", "")))
        year = year_match.group(1) if year_match else None

        # Remove leading zeros from doc_number
        if doc_number:
            doc_number = int(doc_number)

        return pd.Series({"doc_type": doc_type, "doc_number": doc_number, "year": year})

    metadata_df[["doc_type", "doc_number", "year"]] = metadata_df.apply(
        extract_doc_info, axis=1
    )

    # --- Extract Month from Date ---

    def extract_month(row: pd.Series) -> int | None:
        """Extract month number from date field."""
        date_val = row.get("date")
        if pd.notna(date_val):
            # Handle pandas Timestamp objects
            if isinstance(date_val, pd.Timestamp):
                return date_val.month
            # Handle string dates (YYYY-MM-DD format)
            try:
                month = int(str(date_val).split("-")[1])
                return month
            except (IndexError, ValueError):
                return None
        return None

    metadata_df["month"] = metadata_df.apply(extract_month, axis=1)

    # --- Assign PDF Type Based on Folder Location ---

    editable_folder = classification_folder / editable_subfolder
    scanned_folder = classification_folder / scanned_subfolder

    # Map PDF filenames to their type
    for folder, file_type in [
        (editable_folder, "editable"),
        (scanned_folder, "scanned"),
    ]:
        if folder.is_dir():
            for filename in os.listdir(folder):
                if filename.lower().endswith(".pdf"):
                    metadata_df.loc[
                        metadata_df["pdf_filename"] == filename, "pdf_type"
                    ] = file_type

    # --- Reorder Columns ---

    column_order = [
        "date",
        "year",
        "month",
        "page_url",
        "pdf_url",
        "pdf_filename",
        "pdf_type",
        "doc_title",
        "doc_type",
        "doc_number",
    ]

    # Only include columns that exist
    existing_cols = [col for col in column_order if col in metadata_df.columns]
    extra_cols = [col for col in metadata_df.columns if col not in column_order]
    metadata_df = metadata_df[existing_cols + extra_cols]

    # Save enriched metadata
    metadata_df.to_json(
        metadata_json_path,
        orient="records",
        indent=2,
        force_ascii=False,
        date_format="iso",
    )

    print(f"[DONE] Metadata enriched and saved to: '{metadata_json_path}'")

    return metadata_df


def run_classification_stage(
    raw_pdf_folder: str | Path = "data/raw",
    metadata_folder: str | Path = "metadata",
    metadata_json: str = "cf_metadata",
) -> pd.DataFrame:
    """
    Execute the complete PDF classification and metadata enrichment stage.

    This is a high-level function that runs:
    1. Classify PDFs into editable/scanned subfolders
    2. Enrich metadata with document info and PDF types

    Args:
        raw_pdf_folder: Folder containing downloaded PDFs.
        metadata_folder: Folder for metadata JSON.
        metadata_json: JSON filename without extension.

    Returns:
        DataFrame with enriched metadata.

    Example:
        >>> df = run_classification_stage("data/raw", "metadata")
        >>> "pdf_type" in df.columns
        True
    """
    print("=" * 70)
    print("STAGE 3-4: PDF CLASSIFICATION & METADATA ENRICHMENT")
    print("=" * 70)

    # Step 1: Classify PDFs
    stats = classify_pdfs_by_type(raw_pdf_folder)

    # Step 2: Enrich metadata
    metadata_df = metadata_enrichment(
        classification_folder=raw_pdf_folder,
        metadata_folder=metadata_folder,
        metadata_json=metadata_json,
    )

    print("\n[DONE] Classification stage complete")
    print(f"Editable: {stats['editable']}, Scanned: {stats['scanned']}")

    return metadata_df


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Classify PDFs and enrich metadata"
    )
    parser.add_argument(
        "--input",
        "-i",
        default="data/raw",
        help="Input folder with PDFs (default: data/raw)",
    )
    parser.add_argument(
        "--metadata",
        "-m",
        default="metadata",
        help="Metadata folder (default: metadata)",
    )

    args = parser.parse_args()

    df = run_classification_stage(
        raw_pdf_folder=args.input,
        metadata_folder=args.metadata,
    )

    print(f"\nClassification complete. {len(df)} documents processed.")
