# ═════════════════════════════════════════════════════════════════════════════════════════════
#  FISCAL TONE - DATA CURATION PIPELINE
# ═════════════════════════════════════════════════════════════════════════════════════════════
#
#   Program       : data_curation.py
#   Project       : Fiscal Tone
#   Author        : Jason Cruz
#   Last updated  : 11/22/2025
#   Python        : 3.12
#
#   Overview:
#       Interactive pipeline for scraping, downloading, classifying, and extracting text from
#       Peru's Fiscal Council (Consejo Fiscal) PDF documents for fiscal tone sentiment analysis.
#
#   Main Sections:
#       1. ENVIRONMENT SETUP ............................................................ Line 30
#       2. WEB SCRAPING UTILITIES ....................................................... Line 67
#       3. PDF DOWNLOAD PIPELINE ........................................................ Line 208
#       4. PDF CLASSIFICATION ........................................................... Line 394
#       5. METADATA ENRICHMENT .......................................................... Line 472
#       6. TEXT EXTRACTION FROM EDITABLE PDFS ........................................... Line 588
#       7. TEXT EXTRACTION FROM SCANNED PDFS (OCR) ...................................... Line 876
#
#   Workflow:
#       1. Scrape PDF links from cf.gob.pe (informes & comunicados)
#       2. Download PDFs incrementally with multiple fallback strategies
#       3. Classify PDFs as editable vs scanned
#       4. Enrich metadata with document type, number, year, month
#       5. Extract text from editable PDFs using font-based filtering
#       6. Extract text from scanned PDFs using Tesseract OCR with region-based cropping
#
#   Key Features:
#       - Incremental scraping (skips already processed pages)
#       - Rate limiting (1-second delay between downloads)
#       - Multi-fallback PDF URL detection (iframes, embeds, Google Docs viewer)
#       - Font-based text extraction with header/footer filtering (editable PDFs)
#       - OCR-based text extraction with ROI cropping (scanned PDFs)
#       - Stops extraction at "Anexo" sections
#       - Multi-stage text cleaning (headers, footers, footnotes, section headers)
#       - Paragraph-level extraction with quality validation
#
# ═════════════════════════════════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 1. ENVIRONMENT SETUP
# ═══════════════════════════════════════════════════════════════════════════════════════════

import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows console output
if sys.platform == 'win32' and hasattr(sys.stdout, 'buffer'):
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


# --- Project Root and User Input ---

PROJECT_ROOT = Path.cwd()

user_input = input("Enter relative path (default='.'): ").strip() or "."
target_path = (PROJECT_ROOT / user_input).resolve()

target_path.mkdir(parents=True, exist_ok=True)
print(f"Using path: {target_path}")


# --- Define Folder Structure ---

data_folder = "data"
raw_data_subfolder = os.path.join(data_folder, "raw")  # Raw PDFs as downloaded
input_data_subfolder = os.path.join(data_folder, "input")  # Preprocessed PDFs
output_data_subfolder = os.path.join(data_folder, "output")  # Final processed data
metadata_folder = "metadata"  # Metadata JSON files


# --- Create Required Folders ---

for folder in [
    data_folder,
    raw_data_subfolder,
    input_data_subfolder,
    output_data_subfolder,
    metadata_folder,
]:
    os.makedirs(folder, exist_ok=True)
    print(f"[CREATED] {folder}")


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 2. WEB SCRAPING UTILITIES
# ═══════════════════════════════════════════════════════════════════════════════════════════

import time
from timeit import default_timer as timer
import glob
import requests
import pandas as pd
from urllib.parse import urlparse, parse_qs, unquote
from bs4 import BeautifulSoup


# --- Presentation Detection ---


def is_presentation_pdf(url_or_text):
    """
    Detects if a URL or text indicates a PowerPoint presentation file.

    Args:
        url_or_text: str, URL or link text to check

    Returns:
        bool: True if presentation-related keywords found, False otherwise
    """
    if not url_or_text:
        return False

    s = url_or_text.lower()
    ppt_keywords = [
        "ppt",
        "presentacion",
        "presentación",
        "diapositiva",
        "slides",
        "conferencia",
        "powerpoint",
    ]
    return any(kw in s for kw in ppt_keywords)


# --- PDF Link Extraction ---


def extract_pdf_links(dsoup):
    """
    Extracts all PDF links from a BeautifulSoup parsed HTML page.

    Args:
        dsoup: BeautifulSoup object of the detail page

    Returns:
        list of tuples: [(href, link_text), ...] for all PDF links found
    """
    pdf_links = []
    for a in dsoup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" in href.lower():
            txt = a.text.strip() if a.text else ""
            pdf_links.append((href, txt))
    return pdf_links


# --- PDF Selection Heuristic ---


def select_appropriate_pdf(pdf_links):
    """
    Selects the most appropriate PDF from multiple candidates using keyword scoring.

    Filters out presentations first, then scores remaining PDFs by priority keywords
    (comunicado, informe, nota, reporte, documento, pronunciamiento).

    Args:
        pdf_links: list of tuples [(href, link_text), ...]

    Returns:
        str: URL of the selected PDF, or None if no candidates
    """
    if not pdf_links:
        return None

    # Filter out presentations
    filtered = [
        (href, txt)
        for href, txt in pdf_links
        if not is_presentation_pdf(href) and not is_presentation_pdf(txt)
    ]

    candidates = filtered if filtered else pdf_links

    # Priority keywords for document type identification
    priority_keywords = [
        "comunicado",
        "informe",
        "nota",
        "reporte",
        "documento",
        "pronunciamiento",
    ]

    def score(x):
        href, _ = x
        h = href.lower()
        return sum(kw in h for kw in priority_keywords)

    return max(candidates, key=score)[0]


# --- Main Scraper Function ---


def scrape_cf(url, already_scraped_pages):
    """
    Scrapes a Consejo Fiscal list page (informes or comunicados) and extracts PDF metadata.

    Implements incremental scraping by skipping detail pages already in already_scraped_pages.
    Uses multiple fallback strategies to find PDF URLs:
        A) Direct <a> tag PDF links
        B) iframe src attributes
        C) Google Docs viewer URL extraction
        D) Download button with "Guardar" text

    Args:
        url: str, URL of the list page to scrape (e.g., cf.gob.pe/p/informes/)
        already_scraped_pages: set, URLs of detail pages already processed

    Returns:
        tuple: (list_records, new_records)
            - list_records: all entries from the list page (date, title, page_url)
            - new_records: only new entries with PDF metadata extracted
    """
    t0 = timer()

    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    rows = soup.select("table.table tbody tr")
    new_records = []
    list_records = []

    for row in rows:
        try:
            date = row.select_one("td.size100 p").text.strip()
            link_tag = row.select_one("td a")
            doc_title = link_tag.text.strip()
            page_url = link_tag["href"]

            list_records.append(
                {"date": date, "doc_title": doc_title, "page_url": page_url}
            )

            # Skip if already scraped (incremental scraping)
            if page_url in already_scraped_pages:
                continue

            # Fetch detail page
            detail = requests.get(page_url, timeout=15)
            dsoup = BeautifulSoup(detail.text, "html.parser")

            pdf_url = None

            # Strategy A) Direct <a> tag PDF links
            pdf_links = extract_pdf_links(dsoup)
            if pdf_links:
                pdf_url = select_appropriate_pdf(pdf_links)

            # Strategy B) iframe src with .pdf
            if not pdf_url:
                iframe = dsoup.find("iframe", src=lambda x: x and ".pdf" in x.lower())
                if iframe:
                    src = iframe["src"]
                    if src.startswith("//"):
                        src = "https:" + src
                    pdf_url = src

            # Strategy C) Google Docs viewer URL extraction
            if not pdf_url:
                iframe = dsoup.find(
                    "iframe", src=lambda x: x and "docs.google.com" in x.lower()
                )
                if iframe:
                    parsed = urlparse(iframe["src"])
                    q = parse_qs(parsed.query)
                    if "url" in q:
                        pdf_url = unquote(q["url"][0])

            # Strategy D) PDF viewer "Guardar" button
            if not pdf_url:
                button = dsoup.find("button", id="downloadButton") or dsoup.find(
                    "span", string="Guardar"
                )
                if button:
                    parent = button.find_parent("a")
                    if parent and parent.has_attr("href"):
                        pdf_url = parent["href"]

            filename = pdf_url.split("/")[-1] if pdf_url else None

            new_records.append(
                {
                    "date": date,
                    "doc_title": doc_title,
                    "page_url": page_url,
                    "pdf_url": pdf_url,
                    "pdf_filename": filename,
                }
            )

        except Exception as e:
            print(f"[ERROR] processing row: {e}")

    print(f"[DONE] scrape_cf_expanded executed in {timer() - t0:.2f} sec")
    return list_records, new_records


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 3. PDF DOWNLOAD PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════════════════


def pdf_downloader(cf_urls, raw_pdf_folder, metadata_folder, metadata_json):
    """
    Downloads PDFs from Consejo Fiscal URLs with incremental metadata saving.

    Implements robust download pipeline with:
        - Incremental scraping (skips already processed pages)
        - Incremental metadata saving (survives interruptions)
        - Primary + fallback download strategies (<embed>, data-pdf-src attributes)
        - Rate limiting (1-second delay between downloads)
        - Chronological sorting (oldest to newest)

    Args:
        cf_urls: list of str, URLs to scrape (e.g., informes, comunicados pages)
        raw_pdf_folder: str, folder to save downloaded PDFs
        metadata_folder: str, folder containing metadata JSON
        metadata_json: str, JSON filename without extension (e.g., "cf_metadata")

    Returns:
        DataFrame: Complete metadata including newly downloaded PDFs
    """
    t0 = timer()
    os.makedirs(raw_pdf_folder, exist_ok=True)
    os.makedirs(metadata_folder, exist_ok=True)

    metadata_path = os.path.join(metadata_folder, f"{metadata_json}.json")

    # Load existing metadata to enable incremental scraping
    if os.path.exists(metadata_path):
        old_df = pd.read_json(metadata_path, dtype=str)
        old_urls = set(old_df["pdf_url"].dropna())
        old_pages = set(old_df["page_url"].dropna())
    else:
        old_df = pd.DataFrame()
        old_urls = set()
        old_pages = set()

    all_new_records = []

    # Scrape all CF URLs incrementally
    for url in cf_urls:
        print(f"\n[SCRAPING] list page: {url}")
        list_records, new_page_records = scrape_cf(url, already_scraped_pages=old_pages)
        all_new_records.extend(new_page_records)

    # Early exit if no new pages found
    if not all_new_records:
        print("\n[INFO] No new pages: skipping download.")
        print(f"Metadata unchanged: {metadata_path}")
        return pd.read_json(metadata_path, dtype=str)

    # Filter for truly new PDFs not yet downloaded
    new_df = pd.DataFrame(all_new_records).dropna(subset=["pdf_url"])
    mask_new = ~new_df["pdf_url"].isin(old_urls)
    df_to_download = new_df[mask_new].copy()

    # Sort chronologically (oldest first)
    df_to_download["date"] = pd.to_datetime(df_to_download["date"], dayfirst=True)
    df_to_download = df_to_download.sort_values("date").reset_index(drop=True)

    print(f"\n[INFO] Found {len(df_to_download)} new PDFs to download")

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/pdf"}

    # Incremental download with metadata updates after each file
    temp_df = old_df.copy()

    for i, row in df_to_download.iterrows():
        pdf_url = row["pdf_url"]
        filename = row["pdf_filename"]
        page_url = row["page_url"]
        filepath = os.path.join(raw_pdf_folder, filename)

        print(f"\n[{i+1}/{len(df_to_download)}] {filename}")
        print(f"URL: {pdf_url}")

        success = False

        # Primary download attempt
        try:
            r = requests.get(pdf_url, headers=headers, timeout=20)
            r.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(r.content)
            print(f"[SAVED] {filename}")
            success = True

        except Exception as e:
            print(f"[WARN] Primary failed: {e}")

        # Extended fallback strategy
        if not success:
            try:
                print("🔁 Trying extended fallback…")
                detail = requests.get(page_url, timeout=15)
                dsoup = BeautifulSoup(detail.text, "html.parser")

                iframe_url = None

                # Fallback 1) <embed src="...pdf">
                embed = dsoup.find("embed", src=lambda x: x and ".pdf" in x.lower())
                if embed:
                    iframe_url = embed["src"]

                # Fallback 2) <div data-pdf-src="...pdf">
                if not iframe_url:
                    divpdf = dsoup.find("div", attrs={"data-pdf-src": True})
                    if divpdf and ".pdf" in divpdf["data-pdf-src"].lower():
                        iframe_url = divpdf["data-pdf-src"]

                # Normalize protocol-relative URLs
                if iframe_url and iframe_url.startswith("//"):
                    iframe_url = "https:" + iframe_url

                if iframe_url:
                    print(f"   ⇢ fallback PDF URL: {iframe_url}")

                    r2 = requests.get(iframe_url, headers=headers, timeout=20)
                    r2.raise_for_status()

                    # Verify content type is PDF
                    if "pdf" not in r2.headers.get("Content-Type", "").lower():
                        raise ValueError("Server returned HTML instead of PDF")

                    with open(filepath, "wb") as f:
                        f.write(r2.content)

                    print(f"[SAVED] via embed/data-pdf-src fallback: {filename}")
                    success = True
                else:
                    print("[ERROR] No embed/data-pdf-src found")

            except Exception as e2:
                print(f"[ERROR] Extended fallback failed: {e2}")

        # Incremental metadata save (survives interruptions)
        temp_df = pd.concat([temp_df, pd.DataFrame([row])], ignore_index=True)
        temp_df.to_json(
            metadata_path,
            orient="records",
            indent=2,
            force_ascii=False,
            date_format="iso",
        )

        # Rate limiting to avoid server throttling
        time.sleep(1)

    print("\n[SUMMARY]")
    print(f"Metadata saved incrementally: {metadata_path}")
    print(f"Done in {round(timer() - t0, 2)} sec")

    # Return complete metadata as DataFrame
    final_df = pd.read_json(metadata_path, dtype=str)
    return final_df


# --- Execute Download Pipeline ---

cf_urls = [
    "https://cf.gob.pe/p/informes/",
    "https://cf.gob.pe/p/comunicados/",
]

metadata_df = pdf_downloader(
    cf_urls=cf_urls,
    raw_pdf_folder=raw_data_subfolder,
    metadata_folder=metadata_folder,
    metadata_json="cf_metadata",
)


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 4. PDF CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════════════════

import fitz  # PyMuPDF
import shutil


# --- Cleanup: Remove Unwanted PDFs ---

# Annual reports contain statistical analysis, not fiscal tone communications
pdfs_to_remove = [
    "Informe-anual-2017_CF_vf.pdf",
    "Informe-anual-del-Consejo-Fiscal-2018-version-final1.pdf",
]


def remove_unwanted_pdfs(folder_path, filenames_to_remove):
    """
    Deletes specific unwanted PDF files from a given folder.

    Args:
        folder_path: str, directory containing the PDFs
        filenames_to_remove: list of str, filenames to delete

    Returns:
        None
    """
    t0 = timer()
    removed_count = 0

    print(f"🧹 Removing in: {folder_path}")
    for filename in filenames_to_remove:
        full_path = os.path.join(folder_path, filename)
        if os.path.exists(full_path):
            os.remove(full_path)
            print(f"[DELETED] {filename}")
            removed_count += 1
        else:
            print(f"[WARN] File not found: {filename}")

    t1 = timer()

    print("\n[SUMMARY]")
    print(f"Cleanup complete. Total files removed: {removed_count}")
    print(f"Time taken: {t1 - t0:.2f} seconds")


remove_unwanted_pdfs(raw_data_subfolder, pdfs_to_remove)


# --- Editable vs Scanned Detection ---


def is_editable_pdf(file_path, min_text_length=20):
    """
    Checks if a PDF contains extractable text (editable) vs scanned image.

    Args:
        file_path: str, path to PDF file
        min_text_length: int, minimum character count to consider as editable

    Returns:
        bool: True if PDF has extractable text, False if scanned/image-based
    """
    try:
        with fitz.open(file_path) as doc:
            total_text = "".join(page.get_text() for page in doc).strip()
            return len(total_text) >= min_text_length
    except Exception as e:
        print(f"[ERROR] reading {file_path}: {e}")
        return False


def classify_pdfs_by_type(classification_folder):
    """
    Classifies PDFs into 'editable' and 'scanned' subfolders based on text extractability.

    Moves all PDF files from the classification_folder into two subfolders:
        - editable/: PDFs with extractable text
        - scanned/: PDFs without extractable text (image-based)

    Args:
        classification_folder: str or list, directory(ies) containing PDFs to classify

    Returns:
        None
    """
    # Normalize to list for consistent processing
    if isinstance(classification_folder, str):
        classification_folder = [classification_folder]

    # Create classification subfolders
    output_dir_editable = os.path.join(classification_folder[0], "editable")
    output_dir_scanned = os.path.join(classification_folder[0], "scanned")
    os.makedirs(output_dir_editable, exist_ok=True)
    os.makedirs(output_dir_scanned, exist_ok=True)

    total_files = 0
    scanned_count = 0
    editable_count = 0

    t0 = timer()
    print("🔍 Starting PDF classification...")

    # Process all PDFs in provided folders
    for folder in classification_folder:
        for filename in os.listdir(folder):
            if filename.lower().endswith(".pdf"):
                total_files += 1
                pdf_path = os.path.join(folder, filename)

                # Classify and move to appropriate subfolder
                if is_editable_pdf(pdf_path):
                    shutil.move(pdf_path, os.path.join(output_dir_editable, filename))
                    editable_count += 1
                else:
                    shutil.move(pdf_path, os.path.join(output_dir_scanned, filename))
                    scanned_count += 1

    t1 = timer()

    # Print summary
    print("\n[SUMMARY]")
    print(f"Total PDFs processed: {total_files}")
    print(f"Editable PDFs: {editable_count}")
    print(f"Scanned PDFs: {scanned_count}")
    print(f"Saved editable PDFs in: '{output_dir_editable}'")
    print(f"Saved scanned PDFs in: '{output_dir_scanned}'")
    print(f"Time taken: {t1 - t0:.2f} seconds")


# --- Execute Classification ---

classification_folder = raw_data_subfolder
classify_pdfs_by_type(classification_folder)


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 5. METADATA ENRICHMENT
# ═══════════════════════════════════════════════════════════════════════════════════════════

import re


def metadata_enrichment(
    classification_folder, metadata_folder, metadata_json="cf_metadata"
):
    """
    Enriches metadata with extracted document information and PDF classification.

    Adds the following fields to the metadata:
        - pdf_type: "editable" or "scanned" based on folder location
        - doc_type: "Informe" or "Comunicado" extracted from doc_title
        - doc_number: Document number (leading zeros removed)
        - year: 4-digit year extracted from date
        - month: Month number (1-12) extracted from date

    Args:
        classification_folder: str, directory with 'editable' and 'scanned' subfolders
        metadata_folder: str, folder containing the metadata JSON file
        metadata_json: str, JSON filename without '.json' extension

    Returns:
        DataFrame: Enriched metadata with new columns
    """
    metadata_json_path = os.path.join(metadata_folder, f"{metadata_json}.json")

    # Load existing metadata
    metadata_df = pd.read_json(metadata_json_path)

    # Initialize new columns if they don't exist
    for col in ["pdf_type", "doc_type", "doc_number", "year", "month"]:
        if col not in metadata_df.columns:
            metadata_df[col] = ""

    # --- Extract Document Info from Title ---

    def extract_doc_info(row):
        """Extracts doc_type, doc_number, and year from doc_title and date."""
        doc_title = row["doc_title"]

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

    def extract_month(row):
        """Extracts month number from date field."""
        date_val = row["date"]
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

    editable_folder = os.path.join(classification_folder, "editable")
    scanned_folder = os.path.join(classification_folder, "scanned")

    # Verify folders exist
    if not os.path.isdir(editable_folder):
        print(f"[ERROR] 'editable' folder does not exist in '{classification_folder}'.")
    if not os.path.isdir(scanned_folder):
        print(f"[ERROR] 'scanned' folder does not exist in '{classification_folder}'.")

    # Map PDF filenames to their type
    for folder, file_type in [
        (editable_folder, "editable"),
        (scanned_folder, "scanned"),
    ]:
        if os.path.isdir(folder):
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

    # Check for missing columns
    missing_cols = [col for col in column_order if col not in metadata_df.columns]
    if missing_cols:
        print(f"[WARN] Missing columns {missing_cols}. They will not be reordered.")

    # Reorder
    metadata_df = metadata_df[column_order]

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


# --- Execute Metadata Enrichment ---

classification_folder = raw_data_subfolder
metadata_json = "cf_metadata"

updated_metadata_df = metadata_enrichment(
    classification_folder, metadata_folder, metadata_json
)


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 6. TEXT EXTRACTION FROM PDFS
# ═══════════════════════════════════════════════════════════════════════════════════════════
#%%
import os
import pdfplumber
import json
from time import time as timer

def extract_text_from_single_pdf(file_path, FONT_MIN=11.0, FONT_MAX=11.9, exclude_bold=True, vertical_threshold=10):
    """
    Extracts raw text from a single editable PDF for testing purposes, recognizing new paragraphs based on vertical spacing.
    
    Parameters:
    - file_path: str, path to the single PDF file to be processed
    - FONT_MIN: float, minimum font size to consider (default 11.0)
    - FONT_MAX: float, maximum font size to consider (default 11.9)
    - exclude_bold: bool, whether to exclude bold text (default True)
    - vertical_threshold: int, the minimum vertical space between lines to consider as a new paragraph (default 10)

    Prints the extracted text from the PDF for inspection and saves it to a JSON file in the same folder.
    """
    t0 = timer()

    print("🧠 Starting text extraction...\n")
    all_records = []

    try:
        print(f"📄 Processing: {file_path}")
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                # Extract words with their size, vertical position, and fontname
                words = page.extract_words(extra_attrs=["size", "top", "fontname"])

                # Filter out bold words if exclude_bold is True
                clean_words = [w for w in words if FONT_MIN <= w["size"] <= FONT_MAX and ("Bold" not in w["fontname"] if exclude_bold else True)]
                if not clean_words:
                    continue

                # Initialize variables for paragraph detection
                page_text = []
                paragraph_lines = []
                last_top = None  # Keeps track of the vertical position of the previous word

                # Process each word and check vertical spacing between lines
                for word in clean_words:
                    line_text = word["text"]
                    top = word["top"]  # Vertical position of the word

                    # Detect if we have a new paragraph based on vertical spacing
                    if last_top is not None and top - last_top > vertical_threshold:
                        # New paragraph detected based on large vertical space
                        if paragraph_lines:
                            page_text.append(" ".join(paragraph_lines))  # Add the previous paragraph
                        paragraph_lines = [line_text]  # Start a new paragraph
                    else:
                        paragraph_lines.append(line_text)  # Continue adding to the current paragraph
                    
                    last_top = top  # Update the last vertical position

                # Add the last paragraph if exists
                if paragraph_lines:
                    page_text.append(" ".join(paragraph_lines))

                # Combine all extracted text for this page into one string with '\n\n' separating paragraphs
                full_page_text = "\n\n".join(page_text)

                # 🚫 Stop extraction at "Anexo"
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
            return

        # Print extracted text for inspection
        for record in all_records:
            print(f"\n📄 Page {record['page']} of {record['filename']}:")
            print(record['text'])

        # Save extracted text to JSON file in the same path as the PDF
        json_filename = os.path.splitext(os.path.basename(file_path))[0] + ".json"
        json_file_path = os.path.join(os.path.dirname(file_path), json_filename)
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(all_records, f, ensure_ascii=False, indent=4)

        print(f"📂 Text saved to JSON file: {json_file_path}")

    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")

    t1 = timer()
    print(f"\n✅ Extraction complete. Total pages processed: {len(all_records)}")
    print(f"⏱️ Time taken: {t1 - t0:.2f} seconds")


def find_opinion_keyword_position(pdf, keywords, font_min, font_max):
    """
    Searches for 'Opinión del Consejo Fiscal' or 'Opinión del CF' keywords starting from page 2.

    The Fiscal Council's actual opinion often starts after introductory/legal content,
    marked by these specific headers. This function locates where the opinion begins.

    Args:
        pdf: pdfplumber PDF object
        keywords: list of regex patterns to search (e.g., [r"^Opinión del Consejo Fiscal", r"^Opinión del CF"])
        font_min: minimum font size for body text (11.0) - used as reference
        font_max: maximum font size for body text (11.9) - used as reference

    Returns:
        tuple: (start_page, start_top_position) where extraction should begin
               If keyword not found, returns (1, 0) to extract from beginning

    Note:
        - Keywords appear as section headers at 11.0-15.0pt (slightly larger than body text)
        - Range expanded to 15pt to capture PDFs with larger section headers
        - Must be LEFT-ALIGNED (x < 120pt) to avoid centered titles on cover/TOC pages
        - Supports both Arabic numerals (1, 2, 3...) and Roman numerals (I, II, III...)
    """
    print("   🔍 Searching for 'Opinión del' keyword starting from page 2...")
    print("      Requirements: LEFT-aligned (x < 120pt), font 11-15pt, from page 2+")

    # Search from page 2 onwards (skip page 1 which may have summaries)
    for page_num, page in enumerate(pdf.pages[1:], start=2):  # Start from page 2
        page_width = page.width

        # Extract words with relaxed filtering (need to see titles/headers)
        words = page.extract_words(extra_attrs=["size", "top", "fontname"])

        # Check if this PDF has font size metadata
        has_font_metadata = any("size" in w for w in words)

        if has_font_metadata:
            # Filter by broader font size range (keywords appear as section headers at 11-15pt)
            # Headers are typically slightly larger than body text (11-12pt)
            # Some PDFs use larger headers (13-15pt) - must capture these variants
            candidate_words = [
                w for w in words
                if "size" in w and 11.0 <= w["size"] <= 15.0  # Expanded range to capture larger section headers
            ]
        else:
            # Fallback: Some PDFs lack font metadata - use all words for keyword search
            # (Position filtering still applies: left-aligned check at x < 120pt)
            candidate_words = words
            if page_num == 2:  # Only print once
                print("      ⚠️  No font metadata detected. Using position-based filtering only.")

        if not candidate_words:
            continue

        # Reconstruct text line by line to check for keyword at line start
        # Group words by vertical position (same line)
        lines = {}
        for word in candidate_words:
            if "top" not in word:
                continue  # Skip words without position data
            top = round(word["top"], 1)  # Round to group words on same line
            if top not in lines:
                lines[top] = []
            lines[top].append(word)

        # Check each line for keyword at the beginning
        for top_pos in sorted(lines.keys()):
            line_words = sorted(lines[top_pos], key=lambda w: w.get("x0", 0))
            line_text = " ".join([w["text"] for w in line_words]).strip()

            # Get x position of first word to check alignment
            first_word_x = line_words[0].get("x0", 0)

            # CRITICAL: Check if text is LEFT-ALIGNED (not centered)
            # Left-aligned text starts at x=70-120pt (body text margin)
            # Centered text starts at x=150-300pt (middle of page)
            # For A4 (595pt width), center would be ~297pt
            # For US Letter (612pt width), center would be ~306pt
            is_left_aligned = first_word_x < 120  # Conservative threshold

            if not is_left_aligned:
                # Skip centered titles (likely cover page or TOC titles)
                continue

            # Check if any keyword pattern matches at line start
            # NOTE: Case-sensitive matching (must start with uppercase "Opinión")
            # This prevents false positives like "opinión del CF, esto revela..." in mid-sentence
            for keyword_pattern in keywords:
                if re.match(keyword_pattern, line_text):
                    # ADDITIONAL CHECK: Detect multi-line centered titles
                    # Long centered titles often span 2 lines:
                    #   Line 1: "Opinión del Consejo Fiscal sobre el Marco..." (X=91pt - appears left-aligned)
                    #   Line 2: "Multianual 2021-2024" (X > 120pt - centered continuation)
                    # True section headers are single-line or have ALL lines left-aligned

                    # Look for continuation line within next 30pt vertical distance
                    continuation_is_centered = False
                    # Check actual line positions (sorted keys) that come after current line
                    for potential_continuation_top in sorted(lines.keys()):
                        # Only check lines that are below current line (within 10-30pt vertical distance)
                        if potential_continuation_top > top_pos and potential_continuation_top <= top_pos + 30:
                            continuation_words = sorted(lines[potential_continuation_top], key=lambda w: w.get("x0", 0))
                            if continuation_words:
                                continuation_x = continuation_words[0].get("x0", 0)
                                # If continuation line is centered (X > 120pt), this is a multi-line title
                                if continuation_x >= 120:
                                    continuation_is_centered = True
                                    print(f"      ⚠️  Skipping page {page_num}: Multi-line centered title detected")
                                    print(f"         Line 1: '{line_text[:50]}...' at X={first_word_x:.1f}pt")
                                    print(f"         Line 2: X={continuation_x:.1f}pt (centered continuation)")
                                    break

                    if continuation_is_centered:
                        # Skip this match - it's a document title, not a section header
                        break

                    # Valid match - no centered continuation found
                    print(f"      ✓ Found keyword on page {page_num}: '{line_text[:70]}...'")
                    print(f"      ✓ Position: Y={top_pos:.1f}pt, X={first_word_x:.1f}pt (LEFT-aligned)")
                    print(f"      → Starting extraction from page {page_num}, position Y={top_pos}pt")
                    return (page_num, top_pos)

    # Keyword not found - extract from beginning
    print("      ℹ️ Keyword not found. Extracting from page 1.")
    return (1, 0)


def extract_text_from_single_pdf_v2(
    file_path,
    FONT_MIN=10.5,  # Lowered to capture ~11pt text (actual 10.98-11.02pt due to floating-point precision)
    FONT_MAX=11.9,  
    exclude_bold=False,
    vertical_threshold=15,
    first_page_header_cutoff=100,
    subsequent_header_cutoff=70,
    footer_cutoff_distance=85,
    last_page_footer_cutoff=120,
    left_margin=70,
    right_margin=70,
    exclude_specific_sizes=True,
    search_opinion_keyword=True
):
    """
    Enhanced text extraction from editable PDFs with position-based filtering and keyword detection.

    This version improves upon extract_text_from_single_pdf() by adding spatial filtering
    to exclude headers, footers, footnotes, and margin annotations based on their position
    on the page. Additionally, it can search for "Opinión del Consejo Fiscal" keywords to
    extract only the Fiscal Council's actual opinion, skipping preliminary content.

    Key Improvements over v1:
        ✓ Position-based header exclusion (first page vs subsequent pages)
        ✓ Position-based footer exclusion (page numbers, URLs, bottom footnotes)
        ✓ Last page stricter footer filtering (signatures, dates, captions)
        ✓ Horizontal margin filtering (excludes page numbers and margin notes)
        ✓ Explicit font size exclusions (8.4pt, 8.5pt, 9.5pt footnotes/captions)
        ✓ Keyword-based extraction start (finds "Opinión del CF" from page 2 onwards)
        ✓ Bold text inclusion by default (preserves inline emphasis for complete narrative)

    Parameters:
        file_path: str
            Path to the single editable PDF file to process

        FONT_MIN: float, default=11.0
            Minimum font size to consider for main body text

        FONT_MAX: float, default=11.9
            Maximum font size to consider for main body text

        exclude_bold: bool, default=False
            Whether to exclude bold text. False preserves inline emphasis (11.0pt bold)
            for complete narrative flow, important for fiscal tone analysis.

        vertical_threshold: int, default=15
            Minimum vertical space (pixels) between words to detect paragraph break

        first_page_header_cutoff: int, default=100
            Y-position cutoff for first page (excludes top 100pt for titles/headers)

        subsequent_header_cutoff: int, default=70
            Y-position cutoff for pages 2+ (excludes top 70pt)

        footer_cutoff_distance: int, default=120
            Distance from page bottom to exclude (removes footers, page numbers, URLs)

        last_page_footer_cutoff: int, default=400
            Distance from bottom for LAST PAGE ONLY (excludes signatures, dates, captions)
            More aggressive filtering to remove "Lima, DD de MONTH de YYYY", signatures,
            "Presidente Consejo Fiscal", graph/table captions, etc.

        left_margin: int, default=70
            Left margin cutoff in points (excludes page numbers in left margin)

        right_margin: int, default=70
            Right margin cutoff in points (excludes annotations in right margin)

        exclude_specific_sizes: bool, default=True
            If True, explicitly excludes common footnote/caption sizes:
            {9.5, 8.5, 8.4, 7.9, 7.0, 6.5, 6.0, 5.5}pt

        search_opinion_keyword: bool, default=True
            If True, searches for "Opinión del Consejo Fiscal" or "Opinión del CF" keywords
            starting from page 2. If found, extraction begins from that keyword onwards.
            If not found, extracts normally from page 1.
            Keywords must appear at the beginning of a line with font size 11.0-11.9pt.

    Returns:
        None (prints extracted text and saves to JSON file in same directory as PDF)

    Output Format:
        JSON file with structure: [
            {
                "filename": "document.pdf",
                "page": 1,
                "text": "paragraph1\\n\\nparagraph2\\n\\nparagraph3..."
            },
            ...
        ]

    Extraction Logic:
        1. For each page, extract all words with font attributes
        2. Filter by font size range (10.5-11.5pt)
        3. Exclude specific footnote sizes if enabled
        4. Apply position-based filters:
           - Header zone: Y > header_cutoff (150pt page 1, 100pt others)
           - Footer zone: Y < (page_height - 100pt)
           - Left margin: X > 70pt
           - Right margin: X < (page_width - 70pt)
        5. Detect paragraph breaks using vertical spacing
        6. Stop extraction at "Anexo" section
        7. Save to JSON with page-level granularity

    Example Usage:
        >>> # Basic usage (recommended defaults)
        >>> extract_text_from_single_pdf_v2('data/raw/editable/Informe-001-2025.pdf')

        >>> # Custom settings for stricter filtering
        >>> extract_text_from_single_pdf_v2(
        ...     'data/raw/editable/Comunicado-05-2025.pdf',
        ...     FONT_MIN=10.8,
        ...     FONT_MAX=11.2,
        ...     exclude_bold=True,
        ...     first_page_header_cutoff=180
        ... )

    Notes:
        - Tested on 65 editable PDFs from Consejo Fiscal (Informes, Comunicados, Pronunciamientos)
        - Position-based filtering reduces header/footer contamination by ~90%
        - Balanced defaults optimize for completeness while maintaining text purity
        - PDF analysis shows main body consistently at 11.0pt in Y-range 150-740pt
    """
    t0 = timer()

    print("🧠 Starting enhanced text extraction (v2)...\n")
    all_records = []

    # Define specific font sizes to exclude (footnotes, page numbers, superscripts)
    EXCLUDED_SIZES = {9.5, 8.5, 8.4, 7.9, 7.0, 6.5, 6.0, 5.5} if exclude_specific_sizes else set()

    try:
        print(f"📄 Processing: {file_path}")
        print(f"   Font range: {FONT_MIN}pt - {FONT_MAX}pt")
        print(f"   Exclude bold: {exclude_bold}")
        print(f"   Position filtering: ENABLED")
        print(f"   Header cutoff: {first_page_header_cutoff}pt (page 1), {subsequent_header_cutoff}pt (others)")
        print(f"   Footer cutoff: {footer_cutoff_distance}pt from bottom")
        print(f"   Last page footer: {last_page_footer_cutoff}pt from bottom (signatures/dates/captions)")
        print(f"   Margins: {left_margin}pt (left), {right_margin}pt (right)")
        if exclude_specific_sizes:
            print(f"   Excluded sizes: {sorted(EXCLUDED_SIZES)}")
        print()

        with pdfplumber.open(file_path) as pdf:
            total_pages = len(pdf.pages)

            # Step 1: Search for "Opinión del" keyword to find extraction start point
            start_page = 1
            start_top_position = 0

            if search_opinion_keyword:
                # Keyword patterns that match various formats:
                # - "Opinión del Consejo Fiscal..."
                # - "Opinión del CF..."
                # - "Opinión del CF sobre las proyecciones..." (with additional text)
                # - "4. Opinión del Consejo Fiscal..." (Arabic numerals)
                # - "II. Opinión del CF..." (Roman numerals)
                # - "   Opinión del CF..." (with leading spaces)
                #
                # Roman numerals: I, II, III, IV, V, VI, VII, VIII, IX, X, XI, XII, etc.
                # NOTE: The (?:...)? makes the entire number part OPTIONAL
                # NOTE: \b ensures word boundary (matches "CF" but not "CFO")
                keywords = [
                    r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del? Consejo Fiscal\b",  # Optional number + "Opinión de(l) Consejo Fiscal"
                    r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del? CF\b"                # Optional number + "Opinión de(l) CF"
                ]
                start_page, start_top_position = find_opinion_keyword_position(pdf, keywords, FONT_MIN, FONT_MAX)

                # DEBUG: Show what start_page was returned
                print(f"\n   🔍 DEBUG: Keyword search returned start_page={start_page}, start_top_position={start_top_position:.1f}pt")
                if start_page > 1:
                    print(f"   ✅ Will skip pages 1-{start_page-1}")
                else:
                    print(f"   ⚠️  Starting from page 1 (keyword not found or disabled)")

            print()

            # Step 2: Extract text from determined starting point
            keyword_found_on_current_page = False

            for page_num, page in enumerate(pdf.pages, start=1):
                # Skip pages before the keyword start page
                if page_num < start_page:
                    print(f"      [SKIPPED] Page {page_num} < start_page {start_page}")
                    continue

                page_height = page.height
                page_width = page.width

                # ⚠️ EARLY ANEXO DETECTION: Check raw page text BEFORE font filtering
                # Some PDFs have "ANEXO" in large fonts that get filtered out, but we still need to detect it
                # Use extract_text() which doesn't depend on font filtering
                raw_page_text = page.extract_text()
                if raw_page_text:
                    # Check if page starts with "ANEXO" (any case, with optional number/roman numeral)
                    # More robust pattern that handles: ANEXO, Anexo, ANEXOS, Anexos, ANEXO 1, ANEXO I, etc.
                    anexo_start_pattern = r"^\s*ANEXOS?(?:\s+(?:[IVXLCDM]+|\d+))?\s*:?"
                    if re.match(anexo_start_pattern, raw_page_text, re.IGNORECASE):
                        print(f"   Page {page_num}: Anexo section detected (page starts with 'ANEXO')")
                        print(f"      ⏹️  Stopping extraction. Skipping page {page_num} and all subsequent pages.")
                        break

                # Determine header cutoff based on page number
                header_cutoff = first_page_header_cutoff if page_num == 1 else subsequent_header_cutoff

                # Determine footer cutoff (stricter for last page)
                if page_num == total_pages:
                    footer_cutoff = page_height - last_page_footer_cutoff
                    print(f"   Page {page_num} (LAST): {page_width:.1f}x{page_height:.1f}pt (header>{header_cutoff}pt, footer<{footer_cutoff:.1f}pt - STRICT)")
                else:
                    footer_cutoff = page_height - footer_cutoff_distance
                    print(f"   Page {page_num}: {page_width:.1f}x{page_height:.1f}pt (header>{header_cutoff}pt, footer<{footer_cutoff:.1f}pt)")

                # Extract words with their attributes
                # NOTE: Do NOT request "x0" in extra_attrs as it causes character-level extraction in some PDFs
                words = page.extract_words(extra_attrs=["size", "top", "fontname"])

                # If this is the start page with keyword, adjust header cutoff to keyword position
                effective_header_cutoff = header_cutoff
                if page_num == start_page and start_top_position > 0:
                    # Start extraction from keyword position (slightly before to include the keyword itself)
                    effective_header_cutoff = max(start_top_position - 5, 0)
                    print(f"      → Keyword-adjusted header: {effective_header_cutoff:.1f}pt")

                # Apply comprehensive filtering
                # NOTE: x0 is available by default in word dict (left edge of word bounding box)
                clean_words = [
                    w for w in words
                    if (
                        # Font size in range
                        FONT_MIN <= w["size"] <= FONT_MAX

                        # Not in excluded sizes (footnotes, page numbers)
                        and (round(w["size"], 1) not in EXCLUDED_SIZES if exclude_specific_sizes else True)

                        # Bold exclusion (if enabled)
                        and ("Bold" not in w["fontname"] if exclude_bold else True)

                        # Vertical position filtering (headers and footers)
                        # Use effective_header_cutoff which may be adjusted for keyword position
                        and effective_header_cutoff < w["top"] < footer_cutoff

                        # Horizontal position filtering (margins)
                        # x0 is the left edge of the word's bounding box (available by default)
                        and left_margin < w.get("x0", 0) < (page_width - right_margin)
                    )
                ]

                if not clean_words:
                    print(f"      ⚠️ No words matched filters on page {page_num}")
                    continue

                print(f"      ✓ Filtered: {len(words)} words → {len(clean_words)} words")

                # Initialize paragraph detection
                page_text = []
                paragraph_lines = []
                last_top = None

                # Process each word and detect paragraph breaks
                for word in clean_words:
                    line_text = word["text"]
                    top = word["top"]

                    # Detect paragraph break based on vertical spacing
                    if last_top is not None and top - last_top > vertical_threshold:
                        # New paragraph detected
                        if paragraph_lines:
                            page_text.append(" ".join(paragraph_lines))
                        paragraph_lines = [line_text]
                    else:
                        paragraph_lines.append(line_text)

                    last_top = top

                # Add the last paragraph
                if paragraph_lines:
                    page_text.append(" ".join(paragraph_lines))

                # Combine paragraphs with double newlines
                full_page_text = "\n\n".join(page_text)

                # Stop extraction at "Anexo" section
                anexo_detected = False
                match = re.search(r"(?mi)^ *Anexos?\b[\s\w]*:?", full_page_text)
                if match:
                    full_page_text = full_page_text[:match.start()].strip()
                    print(f"      🛑 'Anexo' detected on page {page_num}. Truncating content.")
                    anexo_detected = True

                print(f"      ✓ Extracted {len(page_text)} paragraphs ({len(full_page_text)} chars)")

                # Add page record only if there's content
                if full_page_text:
                    all_records.append({
                        "filename": os.path.basename(file_path),
                        "page": page_num,
                        "text": full_page_text
                    })

                # Stop processing subsequent pages after Anexo
                if anexo_detected:
                    print(f"      ⏹️  Stopping extraction. Skipping all pages after {page_num}.")
                    break

        if not all_records:
            print("⚠️ No text extracted from the PDF.")
            return

        # Print extracted text for inspection
        print("\n" + "="*80)
        print("EXTRACTED TEXT PREVIEW")
        print("="*80)
        for record in all_records:
            print(f"\n📄 Page {record['page']} of {record['filename']}:")
            print("-" * 80)
            # Show first 500 chars of each page
            preview = record['text'][:500] + "..." if len(record['text']) > 500 else record['text']
            print(preview)

        # Save extracted text to JSON file
        json_filename = os.path.splitext(os.path.basename(file_path))[0] + "_v2.json"
        json_file_path = os.path.join(os.path.dirname(file_path), json_filename)
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(all_records, f, ensure_ascii=False, indent=4)

        print(f"\n📂 Text saved to JSON file: {json_file_path}")

    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        import traceback
        traceback.print_exc()

    t1 = timer()
    print(f"\n✅ Extraction complete. Total pages processed: {len(all_records)}")
    print(f"⏱️ Time taken: {t1 - t0:.2f} seconds")


def extract_text_from_editable_pdfs(
    editable_folder="data/raw/editable",
    output_folder="data/raw",
    output_filename="editable_pdfs_extracted_text.json",
    FONT_MIN=10.5,
    FONT_MAX=11.9,
    exclude_bold=False,
    vertical_threshold=15,
    first_page_header_cutoff=100,
    subsequent_header_cutoff=70,
    footer_cutoff_distance=85,
    last_page_footer_cutoff=120,
    left_margin=70,
    right_margin=70,
    exclude_specific_sizes=True,
    search_opinion_keyword=True
):
    """
    Extract text from ALL editable PDFs in a folder and save to a single consolidated JSON file.

    This function loops through all PDF files in the editable folder, applies the same
    extraction logic as extract_text_from_single_pdf_v2(), and saves all results to a
    single JSON file with structure:
    [
        {"pdf_filename": "doc1.pdf", "page": 1, "text": "..."},
        {"pdf_filename": "doc1.pdf", "page": 2, "text": "..."},
        {"pdf_filename": "doc2.pdf", "page": 1, "text": "..."},
        ...
    ]

    Parameters:
        editable_folder: str, default="data/raw/editable"
            Path to folder containing editable PDF files

        output_folder: str, default="data/raw"
            Path to folder where consolidated JSON will be saved

        output_filename: str, default="editable_pdfs_extracted_text.json"
            Name of the output JSON file

        All other parameters: Same as extract_text_from_single_pdf_v2()
            See extract_text_from_single_pdf_v2() documentation for details

    Returns:
        None (saves consolidated JSON file to disk)

    Output File Structure:
        data/raw/editable_pdfs_extracted_text.json with format:
        [
            {
                "pdf_filename": "documento1.pdf",
                "page": 1,
                "text": "paragraph1\\n\\nparagraph2..."
            },
            ...
        ]
    """
    t0 = timer()

    # Get all PDF files from editable folder
    pdf_files = glob.glob(os.path.join(editable_folder, "*.pdf"))

    if not pdf_files:
        print(f"⚠️ No PDF files found in {editable_folder}")
        return

    print("="*80)
    print(f"BATCH TEXT EXTRACTION FROM EDITABLE PDFs")
    print("="*80)
    print(f"Source folder: {editable_folder}")
    print(f"Output file: {os.path.join(output_folder, output_filename)}")
    print(f"Found {len(pdf_files)} PDF files")
    print("="*80)
    print()

    # Excluded font sizes (footnotes, captions, page numbers)
    EXCLUDED_SIZES = [5.5, 6.0, 6.5, 7.0, 7.9, 8.4, 8.5, 9.5]

    # Aggregate all records from all PDFs
    all_records = []
    processed_count = 0
    failed_count = 0

    for pdf_path in pdf_files:
        pdf_filename = os.path.basename(pdf_path)
        print(f"\n{'─'*80}")
        print(f"[{processed_count + 1}/{len(pdf_files)}] Processing: {pdf_filename}")
        print('─'*80)

        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)

                # Keyword search (if enabled)
                start_page = 1
                start_top_position = 0

                if search_opinion_keyword:
                    print(f"   🔍 Searching for 'Opinión del' keyword...")
                    keywords = [
                        r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del? Consejo Fiscal\b",
                        r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del? CF\b"
                    ]
                    start_page, start_top_position = find_opinion_keyword_position(pdf, keywords, FONT_MIN, FONT_MAX)

                    if start_page > 1:
                        print(f"      ✅ Starting from page {start_page} (skipping pages 1-{start_page-1})")
                    else:
                        print(f"      ℹ️ No keyword found. Extracting from page 1.")

                # Extract text from each page
                page_records = []

                for page_num, page in enumerate(pdf.pages, start=1):
                    # Skip pages before start_page
                    if page_num < start_page:
                        continue

                    page_width = float(page.width)
                    page_height = float(page.height)

                    # ⚠️ EARLY ANEXO DETECTION: Check raw page text BEFORE font filtering
                    raw_page_text = page.extract_text()
                    if raw_page_text:
                        # Check if page starts with "ANEXO" (any case, with optional number/roman numeral)
                        anexo_start_pattern = r"^\s*ANEXOS?(?:\s+(?:[IVXLCDM]+|\d+))?\s*:?"
                        if re.match(anexo_start_pattern, raw_page_text, re.IGNORECASE):
                            # Stop processing this PDF - Anexo section reached
                            break

                    # Determine header cutoff
                    header_cutoff = first_page_header_cutoff if page_num == 1 else subsequent_header_cutoff

                    # Determine footer cutoff
                    if page_num == total_pages:
                        footer_cutoff = page_height - last_page_footer_cutoff
                    else:
                        footer_cutoff = page_height - footer_cutoff_distance

                    # Extract words
                    words = page.extract_words(extra_attrs=["size", "top", "fontname"])

                    # Adjust header cutoff if this is the keyword start page
                    effective_header_cutoff = header_cutoff
                    if page_num == start_page and start_top_position > 0:
                        effective_header_cutoff = max(start_top_position - 5, 0)

                    # Apply filters
                    clean_words = [
                        w for w in words
                        if (
                            FONT_MIN <= w["size"] <= FONT_MAX
                            and (round(w["size"], 1) not in EXCLUDED_SIZES if exclude_specific_sizes else True)
                            and ("Bold" not in w["fontname"] if exclude_bold else True)
                            and effective_header_cutoff < w["top"] < footer_cutoff
                            and left_margin < w.get("x0", 0) < (page_width - right_margin)
                        )
                    ]

                    if not clean_words:
                        continue

                    # Build paragraphs
                    page_text = []
                    paragraph_lines = []
                    last_top = None

                    for word in clean_words:
                        line_text = word["text"]
                        top = word["top"]

                        if last_top is not None and abs(top - last_top) > vertical_threshold:
                            # New paragraph detected
                            if paragraph_lines:
                                page_text.append(" ".join(paragraph_lines))
                                paragraph_lines = []

                        paragraph_lines.append(line_text)
                        last_top = top

                    # Add final paragraph
                    if paragraph_lines:
                        page_text.append(" ".join(paragraph_lines))

                    # Join paragraphs
                    full_page_text = "\n\n".join(page_text)

                    # Stop at "Anexo" section
                    anexo_detected = False
                    match = re.search(r"(?mi)^ *Anexos?\b[\s\w]*:?", full_page_text)
                    if match:
                        full_page_text = full_page_text[:match.start()].strip()
                        anexo_detected = True

                    if full_page_text:
                        page_records.append({
                            "pdf_filename": pdf_filename,
                            "page": page_num,
                            "text": full_page_text
                        })

                    # Stop processing subsequent pages after Anexo
                    if anexo_detected:
                        break

                if page_records:
                    all_records.extend(page_records)
                    total_chars = sum(len(r['text']) for r in page_records)
                    print(f"   ✅ Extracted {len(page_records)} pages ({total_chars} chars)")
                    processed_count += 1
                else:
                    print(f"   ⚠️ No text extracted")
                    failed_count += 1

        except Exception as e:
            print(f"   ❌ Error: {e}")
            failed_count += 1

    # Save consolidated JSON
    if not all_records:
        print("\n⚠️ No records extracted from any PDF")
        return

    output_path = os.path.join(output_folder, output_filename)
    os.makedirs(output_folder, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=4)

    t1 = timer()

    print("\n" + "="*80)
    print("BATCH EXTRACTION COMPLETE")
    print("="*80)
    print(f"✅ Processed: {processed_count}/{len(pdf_files)} PDFs")
    print(f"❌ Failed: {failed_count}/{len(pdf_files)} PDFs")
    print(f"📄 Total pages extracted: {len(all_records)}")
    print(f"📊 Total characters: {sum(len(r['text']) for r in all_records):,}")
    print(f"📂 Output file: {output_path}")
    print(f"⏱️ Time taken: {t1 - t0:.2f} seconds")


def extract_text_from_editable_pdfs_incremental(
    editable_folder="data/raw/editable",
    output_folder="data/raw",
    output_filename="editable_pdfs_extracted_text.json",
    FONT_MIN=10.5,
    FONT_MAX=11.9,
    exclude_bold=False,
    vertical_threshold=15,
    first_page_header_cutoff=100,
    subsequent_header_cutoff=70,
    footer_cutoff_distance=85,
    last_page_footer_cutoff=120,
    left_margin=70,
    right_margin=70,
    exclude_specific_sizes=True,
    search_opinion_keyword=True,
    force_reextract=False
):
    """
    INCREMENTAL extraction: Only processes PDFs that are NOT already in the output JSON file.

    This function checks the existing JSON file to identify which PDFs have already been
    extracted, then only processes NEW PDFs that aren't in the JSON. This allows efficient
    incremental updates without re-processing the entire corpus.

    Key Benefits:
        - ⚡ Faster: Skips already-processed PDFs
        - 💾 Efficient: Only extracts new additions to editable folder
        - 🔄 Incremental: Supports continuous pipeline updates
        - 🛡️ Safe: Preserves existing extractions

    Parameters:
        editable_folder: str, default="data/raw/editable"
            Path to folder containing editable PDF files

        output_folder: str, default="data/raw"
            Path to folder where consolidated JSON will be saved

        output_filename: str, default="editable_pdfs_extracted_text.json"
            Name of the output JSON file

        force_reextract: bool, default=False
            If True, re-extract ALL PDFs regardless of JSON status.
            Useful for updating extractions after code changes.

        All other parameters: Same as extract_text_from_editable_pdfs()

    Returns:
        None (updates/creates consolidated JSON file)

    Workflow:
        1. Read existing JSON file (if exists)
        2. Identify already-extracted PDF filenames
        3. Find new PDFs in editable folder (not in JSON)
        4. Extract only new PDFs
        5. Append to existing records
        6. Save updated JSON

    Example Usage:
        >>> # First run: extracts all PDFs
        >>> extract_text_from_editable_pdfs_incremental()

        >>> # Add new PDFs to data/raw/editable/

        >>> # Second run: extracts ONLY new PDFs
        >>> extract_text_from_editable_pdfs_incremental()

        >>> # Force re-extract everything (e.g., after code updates)
        >>> extract_text_from_editable_pdfs_incremental(force_reextract=True)
    """
    t0 = timer()

    # Get all PDF files from editable folder
    pdf_files = glob.glob(os.path.join(editable_folder, "*.pdf"))

    if not pdf_files:
        print(f"⚠️ No PDF files found in {editable_folder}")
        return

    print("="*80)
    print(f"INCREMENTAL TEXT EXTRACTION FROM EDITABLE PDFs")
    print("="*80)
    print(f"Source folder: {editable_folder}")
    print(f"Output file: {os.path.join(output_folder, output_filename)}")
    print(f"Total PDFs in folder: {len(pdf_files)}")
    print("="*80)
    print()

    # Load existing JSON to identify already-extracted PDFs
    output_path = os.path.join(output_folder, output_filename)
    existing_records = []
    already_extracted_pdfs = set()

    if os.path.exists(output_path) and not force_reextract:
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                existing_records = json.load(f)

            # Get unique PDF filenames from existing records
            already_extracted_pdfs = set(r['pdf_filename'] for r in existing_records)

            print(f"📂 Found existing JSON with {len(existing_records)} records")
            print(f"📊 Already extracted: {len(already_extracted_pdfs)} PDFs")
            print()
        except Exception as e:
            print(f"⚠️ Error reading existing JSON: {e}")
            print("   Starting fresh extraction...")
            existing_records = []
            already_extracted_pdfs = set()
    elif force_reextract:
        print(f"🔄 Force re-extraction enabled - will process ALL PDFs")
        print()
    else:
        print(f"📝 No existing JSON found - will extract all PDFs")
        print()

    # Identify NEW PDFs that need extraction
    pdf_basenames = {os.path.basename(p): p for p in pdf_files}
    new_pdfs = [
        pdf_basenames[basename]
        for basename in pdf_basenames
        if basename not in already_extracted_pdfs
    ]

    if not new_pdfs:
        print("✅ All PDFs already extracted. Nothing to do!")
        print(f"   Existing: {len(already_extracted_pdfs)} PDFs")
        return

    print(f"🆕 New PDFs to extract: {len(new_pdfs)}")
    for pdf_path in new_pdfs:
        print(f"   • {os.path.basename(pdf_path)}")
    print()

    # Excluded font sizes
    EXCLUDED_SIZES = [5.5, 6.0, 6.5, 7.0, 7.9, 8.4, 8.5, 9.5]

    # Extract only NEW PDFs
    new_records = []
    processed_count = 0
    failed_count = 0

    for pdf_path in new_pdfs:
        pdf_filename = os.path.basename(pdf_path)
        print(f"\n{'─'*80}")
        print(f"[{processed_count + 1}/{len(new_pdfs)}] Processing: {pdf_filename}")
        print('─'*80)

        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)

                # Keyword search (if enabled)
                start_page = 1
                start_top_position = 0

                if search_opinion_keyword:
                    print(f"   🔍 Searching for 'Opinión del' keyword...")
                    keywords = [
                        r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del? Consejo Fiscal\b",
                        r"^\s*(?:(?:\d+|[IVX]+)\.?\s*)?Opinión del? CF\b"
                    ]
                    start_page, start_top_position = find_opinion_keyword_position(pdf, keywords, FONT_MIN, FONT_MAX)

                    if start_page > 1:
                        print(f"      ✅ Starting from page {start_page} (skipping pages 1-{start_page-1})")
                    else:
                        print(f"      ℹ️ No keyword found. Extracting from page 1.")

                # Extract text from each page
                page_records = []

                for page_num, page in enumerate(pdf.pages, start=1):
                    if page_num < start_page:
                        continue

                    page_width = float(page.width)
                    page_height = float(page.height)

                    # Early Anexo detection
                    raw_page_text = page.extract_text()
                    if raw_page_text:
                        anexo_start_pattern = r"^\s*ANEXOS?(?:\s+(?:[IVXLCDM]+|\d+))?\s*:?"
                        if re.match(anexo_start_pattern, raw_page_text, re.IGNORECASE):
                            break

                    # Determine cutoffs
                    header_cutoff = first_page_header_cutoff if page_num == 1 else subsequent_header_cutoff
                    if page_num == total_pages:
                        footer_cutoff = page_height - last_page_footer_cutoff
                    else:
                        footer_cutoff = page_height - footer_cutoff_distance

                    # Extract words
                    words = page.extract_words(extra_attrs=["size", "top", "fontname"])

                    # Adjust header cutoff if keyword start page
                    effective_header_cutoff = header_cutoff
                    if page_num == start_page and start_top_position > 0:
                        effective_header_cutoff = max(start_top_position - 5, 0)

                    # Apply filters
                    clean_words = [
                        w for w in words
                        if (
                            FONT_MIN <= w["size"] <= FONT_MAX
                            and (round(w["size"], 1) not in EXCLUDED_SIZES if exclude_specific_sizes else True)
                            and ("Bold" not in w["fontname"] if exclude_bold else True)
                            and effective_header_cutoff < w["top"] < footer_cutoff
                            and left_margin < w.get("x0", 0) < (page_width - right_margin)
                        )
                    ]

                    if not clean_words:
                        continue

                    # Build paragraphs
                    page_text = []
                    paragraph_lines = []
                    last_top = None

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

                    # Join paragraphs
                    full_page_text = "\n\n".join(page_text)

                    # Check for Anexo in filtered text (secondary check)
                    anexo_detected = False
                    match = re.search(r"(?mi)^ *Anexos?\b[\s\w]*:?", full_page_text)
                    if match:
                        full_page_text = full_page_text[:match.start()].strip()
                        anexo_detected = True

                    if full_page_text:
                        page_records.append({
                            "pdf_filename": pdf_filename,
                            "page": page_num,
                            "text": full_page_text
                        })

                    if anexo_detected:
                        break

                if page_records:
                    new_records.extend(page_records)
                    total_chars = sum(len(r['text']) for r in page_records)
                    print(f"   ✅ Extracted {len(page_records)} pages ({total_chars} chars)")
                    processed_count += 1
                else:
                    print(f"   ⚠️ No text extracted")
                    failed_count += 1

        except Exception as e:
            print(f"   ❌ Error: {e}")
            failed_count += 1

    # Combine existing + new records
    all_records = existing_records + new_records

    if not all_records:
        print("\n⚠️ No records to save")
        return

    # Save updated JSON
    os.makedirs(output_folder, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_records, f, ensure_ascii=False, indent=4)

    t1 = timer()

    print("\n" + "="*80)
    print("INCREMENTAL EXTRACTION COMPLETE")
    print("="*80)
    print(f"🆕 New PDFs processed: {processed_count}/{len(new_pdfs)}")
    print(f"❌ Failed: {failed_count}/{len(new_pdfs)}")
    print(f"📄 New pages extracted: {len(new_records)}")
    print(f"📊 New characters: {sum(len(r['text']) for r in new_records):,}")
    print(f"📈 Total records in JSON: {len(all_records)} (was {len(existing_records)})")
    print(f"📂 Output file: {output_path}")
    print(f"⏱️ Time taken: {t1 - t0:.2f} seconds")


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 7. TEXT EXTRACTION FROM SCANNED PDFS (OCR)
# ═══════════════════════════════════════════════════════════════════════════════════════════




# ═══════════════════════════════════════════════════════════════════════════════════════════
# 8. TEXT CLEANING PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════════════════

def clean_editable_extracted_text(text: str, aggressive: bool = False) -> dict:
    """
    Execute an 8-step ordered text cleaning pipeline on extracted PDF text.

    This function removes noise patterns like signatures, dates, section headers,
    graph/table titles, and rare symbols. The order of steps is critical to prevent
    pattern interference.

    Args:
        text: Raw extracted text from PDF
        aggressive: If True, includes Step 9 (enumeration removal) - NOT RECOMMENDED

    Returns:
        Dictionary with:
            - 'cleaned_text': Cleaned text ready for paragraph segmentation
            - 'original_length': Original character count
            - 'cleaned_length': Cleaned character count
            - 'reduction_pct': Percentage reduction in characters
            - 'steps_applied': List of step names applied

    Steps:
        1. Remove dotted signature lines
        2. Remove ALL Lima date patterns (improved)
        3. Remove standalone uppercase lines
        4. Remove standalone section headers
        5. Remove graph/table titles
        6. Remove chart sub-labels
        7. Replace rare symbols
        8. Normalize whitespace
        9. Remove enumeration (optional, aggressive mode only)
        10. Remove false paragraph breaks (NEW)

    Example:
        >>> result = clean_editable_extracted_text(raw_text)
        >>> print(result['cleaned_text'])
        >>> print(f"Reduced by {result['reduction_pct']:.1f}%")
    """
    if not text or not text.strip():
        return {
            'cleaned_text': text,
            'original_length': len(text) if text else 0,
            'cleaned_length': len(text) if text else 0,
            'reduction_pct': 0.0,
            'steps_applied': []
        }

    original_length = len(text)
    steps_applied = []

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

    # Step 10: Remove false paragraph breaks (NEW - added for final polish)
    text = _remove_false_paragraph_breaks(text)
    steps_applied.append("Remove false paragraph breaks")

    cleaned_length = len(text)
    reduction_pct = ((original_length - cleaned_length) / original_length * 100) if original_length > 0 else 0.0

    return {
        'cleaned_text': text,
        'original_length': original_length,
        'cleaned_length': cleaned_length,
        'reduction_pct': reduction_pct,
        'steps_applied': steps_applied
    }


# ────────────────────────────────────────────────────────────────────────────
# Helper Functions for Each Cleaning Step
# ────────────────────────────────────────────────────────────────────────────

def _remove_dotted_signatures(text: str) -> str:
    """
    STEP 1: Remove lines with 5+ consecutive dots followed by uppercase names.

    Example: "\\n\\n………………………………………………………….. WALDO EPIFANIO MENDOZA BELLIDO"
    """
    pattern = r'\n*[\.…]{5,}[\s\n]*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]+)(?=\n|$)'
    return re.sub(pattern, '', text)


def _remove_date_signature_blocks(text: str) -> str:
    """
    STEP 2: Remove ALL Lima date patterns (improved version).

    Removes ANY occurrence of "Lima, DD de mes de YYYY" pattern, regardless of what follows.
    This includes standalone dates and dates followed by signatures.

    Examples:
        - "\\n\\nLima, 23 de mayo de 2022\\n\\n"
        - "\\n\\nLima, 15 de agosto de 2019\\n\\nWALDO MENDOZA BELLIDO"
        - "\\n\\nLima, 02 de marzo de 2023."
    """
    # Pattern: Lima, DD de mes de YYYY followed by optional period and/or newlines
    # Captures the entire date block including trailing whitespace
    pattern = r'\n*Lima,?\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\.?[\s\n]*'
    text = re.sub(pattern, '\n\n', text)

    # Also remove any uppercase names/organizations that may follow (legacy pattern)
    pattern_legacy = r'\n\n([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{10,})\n\n'
    text = re.sub(pattern_legacy, '\n\n', text)

    return text


def _remove_uppercase_lines(text: str) -> str:
    """
    STEP 3: Remove lines with 3+ consecutive uppercase words.

    Examples:
        - "\\n\\nCONSEJO FISCAL DEL PERÚ\\n\\n"
        - "\\n\\nWALDO EPIFANIO MENDOZA BELLIDO\\n\\n"

    Excludes:
        - Acronyms in parentheses: (PBI), (MEF)
    """
    pattern = r'\n\n([A-ZÁÉÍÓÚÑ]+(?:\s+[A-ZÁÉÍÓÚÑ]+){2,})\n\n'
    return re.sub(pattern, '\n\n', text)


def _remove_section_headers(text: str) -> str:
    """
    STEP 4: Remove section headers, titles, and chart/table labels.

    IMPROVED: Now detects both regular headers AND numbered/lettered labels
    using two helper functions:
    - _is_section_header() for text headers (< 150 chars, < 15 words, no ending period)
    - _is_chart_or_table_label() for numbered patterns (1:, I., A), etc.)

    Examples removed:
        - "Opinión del CF sobre las proyecciones contempladas en el IAPM"
        - "1: Leyes con impacto fiscal adverso"
        - "I. Opinión del CF sobre el cumplimiento de la regla macrofiscal"
        - "Análisis de riesgos fiscales"
        - "Conclusiones"
    """
    paragraphs = text.split('\n\n')
    cleaned_paragraphs = []

    for para in paragraphs:
        para_stripped = para.strip()

        # Skip if it's a section header OR chart/table label
        if _is_section_header(para_stripped) or _is_chart_or_table_label(para_stripped):
            continue  # Skip this paragraph
        else:
            cleaned_paragraphs.append(para)

    return '\n\n'.join(cleaned_paragraphs)


def _is_section_header(line: str) -> bool:
    """
    Determine if a line is a section header (should be removed).

    IMPROVED: Increased thresholds to catch longer headers like
    "Opinión del CF sobre las proyecciones contempladas en el IAPM"

    Conditions:
        - Length < 150 characters (was 50)
        - Word count < 20 words (was 8, then 15)
        - Starts with uppercase letter or number
        - Does NOT end with period, exclamation mark, or question mark
        - Is NOT a date

    Examples:
        - "Opinión del CF sobre las proyecciones..." → True (header)
        - "El CF considera que esta norma..." → False (sentence ending with period)
    """
    if not line:
        return False

    words = line.split()

    return (
        len(line) > 0 and
        len(line) < 150 and  # CHANGED: was 50
        len(words) > 0 and len(words) < 20 and  # CHANGED: was 8, then 15, now 20
        line[0].isupper() and
        not line[-1] in '.!?' and  # CHANGED: removed colon/semicolon, they can appear in headers
        not re.match(r'Lima,?\s+\d{1,2}\s+de', line)
    )


def _is_chart_or_table_label(line: str) -> bool:
    """
    Detect chart/table labels with numbered/lettered patterns.

    NEW FUNCTION: Detects patterns like "1: Title", "I. Section", "A) Item"
    that are commonly used as chart labels or table headers.

    Patterns detected:
        - "1: Leyes con impacto fiscal adverso" (number + colon)
        - "I. Opinión del CF sobre..." (Roman numeral + period)
        - "A) Leyes con impacto" (letter + parenthesis)
        - "Gráfico 1:", "Tabla N° 2:" (explicit chart/table references)

    Examples:
        >>> _is_chart_or_table_label("1: Leyes con impacto fiscal adverso")
        True
        >>> _is_chart_or_table_label("I. Opinión del CF sobre el proyecto")
        True
        >>> _is_chart_or_table_label("El CF considera que...")
        False
    """
    if not line or not line.strip():
        return False

    line = line.strip()

    # Pattern 1: Gráfico/Tabla/Cuadro/Figura + number
    if re.match(r'^(Gráfico|Tabla|Cuadro|Figura|Gráf|Tab)\s+N?°?\s*\d+', line, re.IGNORECASE):
        return True

    # Pattern 2: Number + colon (e.g., "1: Title", "2: Subtitle")
    if re.match(r'^\d+\s*:\s*.+', line):
        return True

    # Pattern 3: Roman numeral + period or colon (e.g., "I. Title", "II: Subtitle")
    if re.match(r'^[IVXLCDM]+\s*[.:]', line):
        return True

    # Pattern 4: Letter + parenthesis (e.g., "A) Item", "B) Item")
    if re.match(r'^[A-Z]\s*\)\s*.+', line):
        return True

    # Pattern 5: Letter + period at start of short text (e.g., "A. Item")
    if re.match(r'^[A-Z]\s*\.\s*.+', line) and len(line) < 100:
        return True

    return False


def _remove_graph_table_titles(text: str) -> str:
    """
    STEP 5: Remove lines starting with "Gráfico", "Tabla", "Cuadro", "Figura" + number.

    Examples:
        - "Gráfico 1: Leyes con impacto fiscal adverso"
        - "Tabla N° 1: escenarios de crecimiento 2020-2021"
    """
    pattern = r'\n*(Gráfico|Tabla|Cuadro|Figura)\s+N?°?\s*\d+[^\n]*\n*'
    return re.sub(pattern, '\n', text, flags=re.IGNORECASE)


def _remove_chart_labels(text: str) -> str:
    """
    STEP 6: Remove chart panel labels like (A), (B), A), B).

    Examples:
        - "(A) Crecimiento del PBI 2020-2021 (B) PBI trimestral"
        - "A) Leyes con impacto fiscal negativo B) Leyes con impacto"

    IMPORTANT: Must NOT match acronyms like (SPP), (CF), (MEF) - only standalone A), B), (A), (B)
    """
    # Pattern 1: Multiple labels with parentheses on same line
    # Must start at beginning or after whitespace, not inside another parenthesis
    # Example: "\n(A) text (B) text\n"
    text = re.sub(r'\n+\([A-Z]\)\s[^\n]+\([A-Z]\)\s[^\n]*\n+', '\n', text)

    # Pattern 2: Multiple labels without parentheses on same line
    # Must be after newline or start, with space after the letter
    # Example: "\nA) text B) text\n"
    # Use word boundary to avoid matching inside acronyms like (AFP)
    text = re.sub(r'\n+[A-Z]\)\s[^\n]+[A-Z]\)\s[^\n]*\n+', '\n', text)

    # Pattern 3: Single chart label at start of very short line
    # Only if it starts a new line (not mid-text)
    text = re.sub(r'\n+\([A-Z]\)\s[^\n]{1,50}\n+', '\n', text)

    return text


def _replace_rare_symbols(text: str) -> str:
    """
    STEP 7: Replace rare symbols with spaces or normalized equivalents.

    Symbols:
        - Bullet points: •, ➢, ►, ■, ▪
        - Special characters: Ø
        - Horizontal ellipsis: … (replace with ...)
    """
    replacements = {
        '•': ' ',
        '➢': ' ',
        '►': ' ',
        '■': ' ',
        '▪': ' ',
        '□': ' ',
        '◼': ' ',
        '○': ' ',
        '●': ' ',
        '▫': ' ',
        'Ø': ' ',
        '…': '...',
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def _normalize_whitespace(text: str) -> str:
    """
    STEP 8: Normalize whitespace artifacts from previous cleaning steps.

    Actions:
        1. Remove spaces before punctuation marks (. , ; : ! ?)
        2. Replace multiple spaces with single space
        3. Replace 3+ consecutive newlines with 2 newlines
        4. Strip leading/trailing whitespace
    """
    # Remove spaces before punctuation marks
    # Example: "permanentes . Contrario" -> "permanentes. Contrario"
    text = re.sub(r'\s+([.,;:!?])', r'\1', text)

    # Replace multiple spaces with single space
    text = re.sub(r' {2,}', ' ', text)

    # Replace 3+ consecutive newlines with double newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def _remove_enumeration(text: str) -> str:
    """
    STEP 9: Remove standalone enumeration patterns (OPTIONAL - NOT RECOMMENDED).

    ⚠️ WARNING: This removes legitimate list items. Only use in aggressive mode.

    Pattern: Standalone enumeration at line start
    Example: "\\n\\na) \\n\\n" or "\\n\\n1) \\n\\n"
    """
    pattern = r'\n\n([a-z]|[ivxIVX]+|\d+)\)\s*\n\n'
    return re.sub(pattern, '\n\n', text)


def _remove_false_paragraph_breaks(text: str) -> str:
    """
    STEP 10: Remove false paragraph breaks before lowercase letters.

    A paragraph NEVER starts with a lowercase letter in proper Spanish text.
    This removes OCR/extraction artifacts where mid-sentence line breaks were
    incorrectly interpreted as paragraph breaks.

    Examples:
        - "con\\n\\nla reciente propuesta" -> "con la reciente propuesta"
        - "asociado\\n\\na las APP" -> "asociado a las APP"

    Also removes \\n\\n before:
        - Years: "fiscal\\n\\n2020" -> "fiscal 2020"
        - Common connectors: "con\\n\\nde" -> "con de"
    """
    # Remove ALL \n\n before lowercase letters
    # This is the main rule - paragraphs NEVER start with lowercase
    text = re.sub(r'\n\n([a-záéíóúñü])', r' \1', text)

    # Remove \n\n before years
    text = re.sub(r'\n\n([12]\d{3})', r' \1', text)

    # Remove \n\n before common connectors (extra safety)
    connectors = r'(?:de|del|la|el|los|las|un|una|en|con|por|para|que|se|y|o|su|sus|sobre|al|ha|han|lo|le)'
    text = re.sub(r'\n\n(' + connectors + r'\s)', r' \1', text)

    return text


def clean_editable_extracted_text_batch(
    input_json_path: str,
    output_json_path: str,
    aggressive: bool = False,
    verbose: bool = True
):
    """
    Apply text cleaning pipeline to all records in a JSON file.

    This function processes a JSON file containing extracted PDF text (with fields
    'pdf_filename', 'page', 'text') and creates a new JSON file with cleaned text.

    Args:
        input_json_path: Path to input JSON file (e.g., 'data/raw/editable_pdfs_extracted_text.json')
        output_json_path: Path to output JSON file (e.g., 'data/raw/editable_pdfs_clean_editable_extracted_text.json')
        aggressive: If True, includes enumeration removal (not recommended)
        verbose: If True, prints detailed statistics

    Output JSON structure:
        Each record contains:
            - pdf_filename: Original PDF filename
            - page: Page number
            - text: Cleaned text
            - original_length: Original character count
            - cleaned_length: Cleaned character count
            - reduction_pct: Percentage reduction

    Example:
        >>> clean_editable_extracted_text_batch(
        ...     input_json_path='data/raw/editable_pdfs_extracted_text.json',
        ...     output_json_path='data/raw/editable_pdfs_clean_editable_extracted_text.json'
        ... )
    """
    import time
    from collections import defaultdict

    t0 = time.time()

    print("=" * 80)
    print("TEXT CLEANING PIPELINE - BATCH PROCESSING")
    print("=" * 80)
    print(f"Input file: {input_json_path}")
    print(f"Output file: {output_json_path}")
    print(f"Aggressive mode: {aggressive}")
    print()

    # Load input JSON
    print(f"📂 Loading input file...")
    with open(input_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"✓ Loaded {len(data)} records")
    print()

    # Statistics tracking
    step_stats = defaultdict(lambda: {'records_affected': 0, 'chars_removed': 0})

    # Process each record
    print("🧹 Cleaning text records...")
    cleaned_data = []

    for i, record in enumerate(data, 1):
        if verbose and i % 50 == 0:
            print(f"  Processing record {i}/{len(data)}...")

        # Clean the text
        original_text = record['text']
        result = clean_editable_extracted_text(original_text, aggressive=aggressive)

        # Track statistics per step
        if result['reduction_pct'] > 0:
            # At least one step affected this record
            for step_num, step_name in enumerate(result['steps_applied'], 1):
                step_stats[step_num]['records_affected'] += 1

        # Create cleaned record
        cleaned_record = {
            'pdf_filename': record['pdf_filename'],
            'page': record['page'],
            'text': result['cleaned_text'],
            'original_length': result['original_length'],
            'cleaned_length': result['cleaned_length'],
            'reduction_pct': result['reduction_pct']
        }

        cleaned_data.append(cleaned_record)

    print(f"✓ Completed processing {len(data)} records")
    print()

    # Calculate overall statistics
    total_original_chars = sum(r['original_length'] for r in cleaned_data)
    total_cleaned_chars = sum(r['cleaned_length'] for r in cleaned_data)
    overall_reduction = ((total_original_chars - total_cleaned_chars) / total_original_chars * 100) if total_original_chars > 0 else 0

    # Print statistics
    if verbose:
        print("=" * 80)
        print("CLEANING STATISTICS")
        print("=" * 80)
        print(f"Total records processed: {len(data)}")
        print(f"Total original characters: {total_original_chars:,}")
        print(f"Total cleaned characters: {total_cleaned_chars:,}")
        print(f"Characters removed: {total_original_chars - total_cleaned_chars:,}")
        print(f"Overall reduction: {overall_reduction:.2f}%")
        print()

        # Average reduction per record
        avg_reduction = sum(r['reduction_pct'] for r in cleaned_data) / len(cleaned_data) if cleaned_data else 0
        print(f"Average reduction per record: {avg_reduction:.2f}%")

        # Records with significant cleaning (>5% reduction)
        significant_cleaning = [r for r in cleaned_data if r['reduction_pct'] > 5]
        print(f"Records with >5% reduction: {len(significant_cleaning)}/{len(cleaned_data)} ({len(significant_cleaning)/len(cleaned_data)*100:.1f}%)")
        print()

    # Save output JSON
    print(f"💾 Saving cleaned data to: {output_json_path}")
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)

    t1 = time.time()

    print(f"✓ Successfully saved {len(cleaned_data)} cleaned records")
    print(f"⏱️  Time taken: {t1 - t0:.2f} seconds")
    print()
    print("=" * 80)


def clean_editable_extracted_text_batch_incremental(
    input_json_path: str,
    output_json_path: str,
    aggressive: bool = False,
    verbose: bool = True,
    force_reclean: bool = False
):
    """
    INCREMENTAL text cleaning: Only processes records that are NOT already in the output JSON file.

    This function compares PDF filenames between input and output JSON files. Only NEW records
    (filenames in input but not in output) are cleaned and appended to the existing cleaned data.

    Key Benefits:
        - ⚡ Faster: Skips already-cleaned records
        - 💾 Efficient: Only cleans newly added PDFs
        - 🔄 Incremental: Supports continuous pipeline updates
        - 🛡️ Safe: Preserves existing cleaned data

    Args:
        input_json_path: Path to input JSON file (e.g., 'data/raw/editable_pdfs_extracted_text.json')
        output_json_path: Path to output JSON file (e.g., 'data/raw/editable_pdfs_clean_editable_extracted_text.json')
        aggressive: If True, includes enumeration removal (not recommended)
        verbose: If True, prints detailed statistics
        force_reclean: If True, re-process ALL records (ignores existing output)

    Workflow:
        1. Load existing cleaned JSON (if exists)
        2. Identify already-cleaned PDF filenames
        3. Filter input for NEW records only
        4. Clean only NEW records
        5. Append new cleaned records to existing records
        6. Save updated JSON

    Example:
        >>> # First run: cleans all records
        >>> clean_editable_extracted_text_batch_incremental(
        ...     input_json_path='data/raw/editable_pdfs_extracted_text.json',
        ...     output_json_path='data/raw/editable_pdfs_clean_editable_extracted_text.json'
        ... )
        # Output: Cleaned 336 records

        >>> # Second run: skips all (nothing new)
        >>> clean_editable_extracted_text_batch_incremental(
        ...     input_json_path='data/raw/editable_pdfs_extracted_text.json',
        ...     output_json_path='data/raw/editable_pdfs_clean_editable_extracted_text.json'
        ... )
        # Output: All records already cleaned. Nothing to do!

        >>> # After adding 5 new PDFs and extracting them:
        >>> clean_editable_extracted_text_batch_incremental(
        ...     input_json_path='data/raw/editable_pdfs_extracted_text.json',
        ...     output_json_path='data/raw/editable_pdfs_clean_editable_extracted_text.json'
        ... )
        # Output: Cleaned 5 new records (336 existing + 5 new = 341 total)
    """
    import time
    import os
    from collections import defaultdict

    t0 = time.time()

    print("=" * 80)
    print("INCREMENTAL TEXT CLEANING PIPELINE")
    print("=" * 80)
    print(f"Input file: {input_json_path}")
    print(f"Output file: {output_json_path}")
    print(f"Aggressive mode: {aggressive}")
    print(f"Force re-clean: {force_reclean}")
    print()

    # Load input JSON
    print(f"📂 Loading input file...")
    with open(input_json_path, 'r', encoding='utf-8') as f:
        input_data = json.load(f)

    print(f"✓ Loaded {len(input_data)} records from input")
    print()

    # Load existing cleaned JSON (if exists and not forcing re-clean)
    existing_records = []
    already_cleaned_filenames = set()

    if os.path.exists(output_json_path) and not force_reclean:
        print(f"📂 Found existing cleaned data, loading...")
        with open(output_json_path, 'r', encoding='utf-8') as f:
            existing_records = json.load(f)

        # Extract set of already-cleaned PDF filenames
        already_cleaned_filenames = set(r['pdf_filename'] for r in existing_records)

        print(f"✓ Loaded {len(existing_records)} existing cleaned records")
        print(f"📊 Already cleaned PDFs: {len(already_cleaned_filenames)} unique filenames")
        print()
    else:
        if force_reclean:
            print("⚠️  Force re-clean mode: Will process all records")
        else:
            print("📝 No existing cleaned data found - will clean all records")
        print()

    # Identify NEW records (not already cleaned)
    new_records = [
        r for r in input_data
        if r['pdf_filename'] not in already_cleaned_filenames
    ]

    # Check if there's anything to clean
    if not new_records:
        print("=" * 80)
        print("✅ All records already cleaned. Nothing to do!")
        print(f"   Existing: {len(existing_records)} records")
        print("=" * 80)
        return

    print(f"🆕 New records to clean: {len(new_records)}")
    print(f"   (Skipping {len(input_data) - len(new_records)} already-cleaned records)")
    print()

    # Show sample of new PDFs
    if verbose and new_records:
        new_pdfs = sorted(set(r['pdf_filename'] for r in new_records))
        print(f"   New PDF filenames ({len(new_pdfs)}):")
        for pdf in new_pdfs[:5]:
            print(f"   • {pdf}")
        if len(new_pdfs) > 5:
            print(f"   ... and {len(new_pdfs) - 5} more")
        print()

    # Clean NEW records only
    print("🧹 Cleaning NEW text records...")
    print()

    cleaned_new_records = []

    for i, record in enumerate(new_records, 1):
        if verbose and i % 50 == 0:
            print(f"  Processing record {i}/{len(new_records)}...")

        # Clean the text
        original_text = record['text']
        result = clean_editable_extracted_text(original_text, aggressive=aggressive)

        # Create cleaned record
        cleaned_record = {
            'pdf_filename': record['pdf_filename'],
            'page': record['page'],
            'text': result['cleaned_text'],
            'original_length': result['original_length'],
            'cleaned_length': result['cleaned_length'],
            'reduction_pct': result['reduction_pct']
        }

        cleaned_new_records.append(cleaned_record)

    print(f"✓ Completed cleaning {len(new_records)} new records")
    print()

    # Combine existing + new cleaned records
    all_cleaned_records = existing_records + cleaned_new_records

    # Calculate statistics for NEW records
    total_original_chars = sum(r['original_length'] for r in cleaned_new_records)
    total_cleaned_chars = sum(r['cleaned_length'] for r in cleaned_new_records)
    overall_reduction = ((total_original_chars - total_cleaned_chars) / total_original_chars * 100) if total_original_chars > 0 else 0

    # Print statistics
    if verbose:
        print("=" * 80)
        print("CLEANING STATISTICS (NEW RECORDS ONLY)")
        print("=" * 80)
        print(f"New records cleaned: {len(cleaned_new_records)}")
        print(f"Total original characters: {total_original_chars:,}")
        print(f"Total cleaned characters: {total_cleaned_chars:,}")
        print(f"Characters removed: {total_original_chars - total_cleaned_chars:,}")
        print(f"Overall reduction: {overall_reduction:.2f}%")
        print()

        # Average reduction per record
        avg_reduction = sum(r['reduction_pct'] for r in cleaned_new_records) / len(cleaned_new_records) if cleaned_new_records else 0
        print(f"Average reduction per record: {avg_reduction:.2f}%")

        # Records with significant cleaning (>5% reduction)
        significant_cleaning = [r for r in cleaned_new_records if r['reduction_pct'] > 5]
        print(f"Records with >5% reduction: {len(significant_cleaning)}/{len(cleaned_new_records)} ({len(significant_cleaning)/len(cleaned_new_records)*100:.1f}%)")
        print()

        print("=" * 80)
        print("OVERALL STATISTICS (EXISTING + NEW)")
        print("=" * 80)
        print(f"Total records in output: {len(all_cleaned_records)}")
        print(f"  - Existing (preserved): {len(existing_records)}")
        print(f"  - New (just cleaned): {len(cleaned_new_records)}")
        print()

    # Save updated JSON
    print(f"💾 Saving updated cleaned data to: {output_json_path}")
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(all_cleaned_records, f, ensure_ascii=False, indent=2)

    t1 = time.time()

    print(f"✓ Successfully saved {len(all_cleaned_records)} cleaned records")
    print(f"📊 Updated output file:")
    print(f"   - Before: {len(existing_records)} records")
    print(f"   - After: {len(all_cleaned_records)} records (+{len(cleaned_new_records)} new)")
    print(f"⏱️  Time taken: {t1 - t0:.2f} seconds")
    print()
    print("=" * 80)


# ═══════════════════════════════════════════════════════════════════════════════════════════
# END OF PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════════════════
