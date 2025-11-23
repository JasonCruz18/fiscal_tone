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

import os
from pathlib import Path


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

# Example usage: specify the PDF file path
file_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Comunicado-Congreso-vf.pdf"
extract_text_from_single_pdf(file_path, FONT_MIN=11.0, FONT_MAX=11.9, exclude_bold=False, vertical_threshold=15)


# ═══════════════════════════════════════════════════════════════════════════════════════════
# 7. TEXT EXTRACTION FROM SCANNED PDFS (OCR)
# ═══════════════════════════════════════════════════════════════════════════════════════════

try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image, ImageEnhance, ImageFilter
except ImportError:
    print("[WARN] OCR dependencies not installed. Run: pip install pytesseract pdf2image Pillow")
    print("[WARN] Also install Tesseract OCR system binary: https://github.com/UB-Mannheim/tesseract/wiki")


# --- Region of Interest (ROI) Definitions ---

# Coordinate zones for cropping (in pixels at 300 DPI)
ROI_PAGE_1 = {
    'top': 250,      # Skip logo, document ID, title
    'bottom': -100,  # Skip footer (from page bottom)
    'left': 70,      # Standard left margin
    'right': -70     # Standard right margin (from page right)
}

ROI_BODY = {
    'top': 100,      # Skip logo header
    'bottom': -100,  # Skip footer
    'left': 70,
    'right': -70
}

ROI_FINAL = {
    'top': 100,      # Skip logo header
    'bottom': -300,  # Larger exclusion for signature block
    'left': 70,
    'right': -70
}


# --- Image Preprocessing Functions ---

def preprocess_page_image(image, page_num, total_pages):
    """
    Crops and enhances page image for optimal OCR quality.

    Applies region-based cropping to exclude headers, footers, and margins,
    then enhances contrast and applies denoising for better text recognition.

    Args:
        image: PIL Image object of the PDF page
        page_num: int, current page number (1-indexed)
        total_pages: int, total number of pages in document

    Returns:
        PIL Image: Cropped and enhanced image ready for OCR
    """
    width, height = image.size

    # Select appropriate ROI based on page type
    if page_num == 1:
        roi = ROI_PAGE_1
    elif page_num == total_pages:
        roi = ROI_FINAL
    else:
        roi = ROI_BODY

    # Crop to exclude headers/footers/margins
    cropped = image.crop((
        roi['left'],
        roi['top'],
        width + roi['right'],   # right is negative offset
        height + roi['bottom']  # bottom is negative offset
    ))

    # Enhance contrast for better OCR accuracy
    enhancer = ImageEnhance.Contrast(cropped)
    enhanced = enhancer.enhance(1.5)

    # Apply slight denoising
    denoised = enhanced.filter(ImageFilter.MedianFilter(size=3))

    return denoised


def enhance_image_quality(image):
    """
    Additional image enhancement for low-quality scans.

    Args:
        image: PIL Image object

    Returns:
        PIL Image: Enhanced image with improved sharpness and brightness
    """
    # Increase sharpness
    sharpener = ImageEnhance.Sharpness(image)
    sharp = sharpener.enhance(1.5)

    # Adjust brightness if needed
    brightness_enhancer = ImageEnhance.Brightness(sharp)
    bright = brightness_enhancer.enhance(1.1)

    return bright


# --- Text Cleaning Functions ---

def remove_footer_patterns(text):
    """
    Removes footer text patterns that leak through ROI cropping.

    Filters out:
        - Address lines ("Av. República de Panamá...")
        - Page numbers (e.g., "1/4", "5/7")
        - Website URLs and phone numbers

    Args:
        text: str, raw OCR text

    Returns:
        str: Text with footer patterns removed
    """
    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        # Skip address lines
        if re.search(r'Av\.\s*República\s+de\s+Panamá', line, re.IGNORECASE):
            continue

        # Skip page numbers (format: X/Y)
        if re.search(r'^\s*\d+\s*/\s*\d+\s*$', line):
            continue

        # Skip short lines with page numbers
        if re.search(r'\d+/\d+', line) and len(line) < 20:
            continue

        # Skip website/contact info
        if re.search(r'www\.cf\.gob\.pe|Teléfono', line, re.IGNORECASE):
            continue

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def remove_header_patterns(text):
    """
    Removes header text patterns that leak through ROI cropping.

    Filters out:
        - Document IDs ("Informe N° XXX-2016-CF")
        - Institution names ("CONSEJO FISCAL")
        - Watermark text ("PRESIDENTE")

    Args:
        text: str, raw OCR text

    Returns:
        str: Text with header patterns removed
    """
    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        # Skip document ID patterns
        if re.search(r'Informe\s+N[°ºo]\s*\d+-\d{4}-CF', line, re.IGNORECASE):
            continue

        # Skip institution name (when it appears alone)
        if re.search(r'^\s*CONSEJO\s+FISCAL\s*$', line, re.IGNORECASE):
            continue

        # Skip watermark text
        if 'PRESIDENTE' in line and len(line) < 20:
            continue

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def remove_section_headers(text):
    """
    Removes section headers like 'Antecedentes', 'Conclusiones', 'Riesgos'.

    Based on user preference to extract only paragraph text without structural markers.

    Args:
        text: str, raw OCR text

    Returns:
        str: Text with section headers removed
    """
    # Common section headers in Consejo Fiscal documents
    section_headers = [
        r'^\s*Antecedentes\s*$',
        r'^\s*Escenario\s+internacional\s+(y\s+)?local\s*$',
        r'^\s*Proyecciones\s+fiscales\s*$',
        r'^\s*Riesgos\s*$',
        r'^\s*Conclusiones\s*$',
        r'^\s*Recomendaciones\s*$',
        r'^\s*Introducción\s*$',
        r'^\s*Análisis\s*$',
    ]

    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        # Check if line matches any section header pattern
        is_header = any(re.match(pattern, line, re.IGNORECASE) for pattern in section_headers)

        if not is_header:
            cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def remove_footnotes(text):
    """
    Removes footnote markers and footnote content from text.

    Footnotes appear as:
        1. Superscript numbers in main text (removed via OCR artifact cleaning)
        2. Numbered footnote content at page bottom (detected and truncated)

    Args:
        text: str, raw OCR text

    Returns:
        str: Text with footnotes removed
    """
    # Remove common OCR artifacts for superscript numbers
    text = re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]+', '', text)

    # Detect footnote start pattern (line begins with digit + space + capital letter)
    # This indicates transition from main text to footnotes
    lines = text.split('\n')
    main_content = []

    for i, line in enumerate(lines):
        # Detect footnote start: "1 Some footnote text..."
        if re.match(r'^\s*\d+\s+[A-ZÁÉÍÓÚÑ]', line):
            # Verify it's actually a footnote (short line or followed by more numbered lines)
            if len(line) > 50:  # Likely still main text
                main_content.append(line)
            else:
                # This and all following lines are footnotes, stop here
                break
        else:
            main_content.append(line)

    return '\n'.join(main_content)


def stop_at_signature_or_anexo(text):
    """
    Truncates text at signature block or anexo section.

    Stops extraction when encountering:
        - Date line: "Lima, DD de MONTH de YYYY"
        - Anexo headers: "ANEXO 1:", "Anexo:"

    Args:
        text: str, raw OCR text

    Returns:
        str: Text truncated before signature/anexo
    """
    # Pattern 1: Signature date line
    signature_match = re.search(r'Lima,\s*\d+\s+de\s+\w+\s+de\s+\d{4}', text, re.IGNORECASE)
    if signature_match:
        text = text[:signature_match.start()].strip()

    # Pattern 2: Anexo section
    anexo_match = re.search(r'ANEXO\s*\d*\s*:', text, re.IGNORECASE)
    if anexo_match:
        text = text[:anexo_match.start()].strip()

    return text


def clean_ocr_text(text, page_num, total_pages):
    """
    Applies all cleaning filters to raw OCR text.

    Multi-stage cleaning pipeline:
        1. Remove footer patterns
        2. Remove header patterns
        3. Remove section headers
        4. Remove footnotes
        5. Stop at signature/anexo (final page only)

    Args:
        text: str, raw OCR text from page
        page_num: int, current page number
        total_pages: int, total pages in document

    Returns:
        str: Clean text ready for paragraph extraction
    """
    text = remove_footer_patterns(text)
    text = remove_header_patterns(text)
    text = remove_section_headers(text)
    text = remove_footnotes(text)

    # Only check for signature/anexo on final page
    if page_num == total_pages:
        text = stop_at_signature_or_anexo(text)

    return text


# --- Paragraph Extraction Functions ---

def extract_main_paragraphs(text):
    """
    Extracts substantive paragraphs from cleaned OCR text.

    Filters out:
        - Short fragments (<50 characters)
        - Table-like content (high digit ratio)
        - Overly fragmented text (too many line breaks)

    Args:
        text: str, cleaned OCR text

    Returns:
        list of str: Substantive paragraphs only
    """
    # Split by double newlines or multiple blank lines
    potential_paragraphs = re.split(r'\n\s*\n', text)

    paragraphs = []

    for para in potential_paragraphs:
        para = para.strip()

        # Filter 1: Skip if too short (likely not a real paragraph)
        if len(para) < 50:
            continue

        # Filter 2: Skip if looks like a table (lots of numbers)
        digit_count = sum(c.isdigit() for c in para)
        if digit_count / len(para) > 0.3:
            continue

        # Filter 3: Skip if too many line breaks (fragmented OCR text)
        line_break_count = para.count('\n')
        if line_break_count / len(para) > 0.05:
            continue

        # Filter 4: Skip if too many short words (likely OCR artifacts)
        words = para.split()
        if words:
            short_word_ratio = sum(1 for w in words if len(w) <= 2) / len(words)
            if short_word_ratio > 0.4:
                continue

        # Clean up internal whitespace
        para = re.sub(r'\s+', ' ', para)

        paragraphs.append(para)

    return paragraphs


# --- Main Extraction Function ---

def extract_text_from_scanned_pdf(file_path, dpi=300):
    """
    Extracts fiscal opinion paragraphs from scanned PDFs using OCR.

    This function implements a comprehensive extraction pipeline specifically designed
    for Peru's Consejo Fiscal scanned PDF documents:
        1. Converts PDF pages to images at specified DPI
        2. Crops images to exclude headers, footers, and margins
        3. Enhances image quality for optimal OCR
        4. Performs Tesseract OCR with Spanish language model
        5. Cleans text to remove non-paragraph content
        6. Extracts only substantive paragraphs with metadata

    Args:
        file_path: str, path to scanned PDF file
        dpi: int, resolution for PDF to image conversion (default 300)

    Returns:
        list of dict: [{'text': paragraph, 'page': page_num, 'pdf_filename': filename}, ...]
        Returns empty list if extraction fails or no paragraphs found

    Example:
        >>> results = extract_text_from_scanned_pdf('data/raw/scanned/Informe_001-2016.pdf')
        >>> print(f"Extracted {len(results)} paragraphs")
        >>> print(results[0]['text'][:100])
    """
    t0 = timer()

    print(f"[OCR] Starting extraction from: {os.path.basename(file_path)}")
    print(f"      DPI: {dpi}")

    try:
        # Step 1: Convert PDF to images
        print("[OCR] Converting PDF pages to images...")
        images = convert_from_path(file_path, dpi=dpi)
        total_pages = len(images)
        print(f"      Converted {total_pages} pages")

        all_paragraphs = []

        # Step 2: Process each page
        for page_num, image in enumerate(images, start=1):
            print(f"\n[OCR] Processing page {page_num}/{total_pages}...")

            # Step 2a: Preprocess image (crop and enhance)
            cropped = preprocess_page_image(image, page_num, total_pages)

            # Step 2b: Perform OCR with Spanish language model
            custom_config = r'--oem 3 --psm 6 -l spa'  # LSTM OCR, uniform text block, Spanish
            page_text = pytesseract.image_to_string(cropped, config=custom_config)

            # Step 2c: Clean OCR text
            clean_text = clean_ocr_text(page_text, page_num, total_pages)

            # Step 2d: Extract paragraphs from cleaned text
            page_paragraphs = extract_main_paragraphs(clean_text)

            print(f"      Extracted {len(page_paragraphs)} paragraphs")

            # Step 2e: Add metadata to each paragraph
            for para in page_paragraphs:
                all_paragraphs.append({
                    'text': para,
                    'page': page_num,
                    'pdf_filename': os.path.basename(file_path)
                })

        t1 = timer()

        print(f"\n[DONE] Extraction complete!")
        print(f"       Total paragraphs: {len(all_paragraphs)}")
        print(f"       Time taken: {t1 - t0:.2f} seconds")

        return all_paragraphs

    except Exception as e:
        print(f"[ERROR] OCR extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return []


# --- Quality Validation Function ---

def validate_extraction(paragraphs):
    """
    Validates extraction quality and identifies potential issues.

    Checks for common extraction problems:
        - Footer leakage
        - Header leakage
        - Page numbers in text
        - Missing expected content
        - Signature block leakage
        - Anexo content leakage

    Args:
        paragraphs: list of dict, output from extract_text_from_scanned_pdf()

    Returns:
        dict: {'passed': bool, 'issues': list of str, 'warnings': list of str}
    """
    issues = []
    warnings = []

    if not paragraphs:
        issues.append("No paragraphs extracted")
        return {'passed': False, 'issues': issues, 'warnings': warnings}

    # Combine all text for pattern checking
    all_text = ' '.join([p['text'] for p in paragraphs])

    # Check 1: No footer leakage
    if re.search(r'Av\.\s*República\s+de\s+Panamá', all_text, re.IGNORECASE):
        issues.append("Footer text detected (address)")

    # Check 2: No page numbers
    page_num_matches = re.findall(r'\d+/\d+', all_text)
    if page_num_matches:
        warnings.append(f"Page numbers detected: {page_num_matches[:3]}")

    # Check 3: No signature block
    if re.search(r'PRESIDENTE\s+DEL\s+CONSEJO\s+FISCAL', all_text, re.IGNORECASE):
        issues.append("Signature block detected")

    # Check 4: No anexo content
    if re.search(r'Anexo\s+\d+:', all_text, re.IGNORECASE):
        issues.append("Anexo section detected")

    # Check 5: Expected content patterns
    if 'informe' not in all_text.lower() and 'presente' not in all_text.lower():
        warnings.append("Missing expected opening phrases")

    # Check 6: Reasonable paragraph count
    if len(paragraphs) < 3:
        warnings.append(f"Low paragraph count: {len(paragraphs)}")

    # Check 7: Reasonable text length
    avg_length = sum(len(p['text']) for p in paragraphs) / len(paragraphs)
    if avg_length < 100:
        warnings.append(f"Suspiciously short paragraphs (avg: {avg_length:.0f} chars)")

    passed = len(issues) == 0

    return {
        'passed': passed,
        'issues': issues,
        'warnings': warnings
    }


# --- Batch Processing Function ---

def batch_extract_scanned_pdfs(scanned_folder, output_json_path, dpi=300):
    """
    Processes all scanned PDFs in a folder and saves results to JSON.

    Args:
        scanned_folder: str, path to folder containing scanned PDFs
        output_json_path: str, path to save output JSON file
        dpi: int, resolution for OCR (default 300)

    Returns:
        list of dict: All extracted paragraphs from all PDFs
    """
    t0 = timer()

    all_results = []
    pdf_files = [f for f in os.listdir(scanned_folder) if f.lower().endswith('.pdf')]

    print(f"📚 Found {len(pdf_files)} scanned PDFs to process\n")

    for i, filename in enumerate(pdf_files, start=1):
        print(f"\n{'='*80}")
        print(f"[{i}/{len(pdf_files)}] {filename}")
        print('='*80)

        file_path = os.path.join(scanned_folder, filename)
        paragraphs = extract_text_from_scanned_pdf(file_path, dpi=dpi)

        # Validate extraction
        validation = validate_extraction(paragraphs)
        if not validation['passed']:
            print(f"⚠️  VALIDATION FAILED:")
            for issue in validation['issues']:
                print(f"   ❌ {issue}")
        if validation['warnings']:
            print(f"⚠️  Warnings:")
            for warning in validation['warnings']:
                print(f"   ⚡ {warning}")

        all_results.extend(paragraphs)

    # Save to JSON
    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    t1 = timer()

    print(f"\n\n{'='*80}")
    print("📊 BATCH PROCESSING SUMMARY")
    print('='*80)
    print(f"Total PDFs processed: {len(pdf_files)}")
    print(f"Total paragraphs extracted: {len(all_results)}")
    print(f"Output saved to: {output_json_path}")
    print(f"Total time: {t1 - t0:.2f} seconds")

    return all_results


# ═══════════════════════════════════════════════════════════════════════════════════════════
# END OF PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════════════════
