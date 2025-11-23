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
#       6. TEXT EXTRACTION FROM PDFS .................................................... Line 588
#
#   Workflow:
#       1. Scrape PDF links from cf.gob.pe (informes & comunicados)
#       2. Download PDFs incrementally with multiple fallback strategies
#       3. Classify PDFs as editable vs scanned
#       4. Enrich metadata with document type, number, year, month
#       5. Extract text from editable PDFs using font-based filtering
#
#   Key Features:
#       - Incremental scraping (skips already processed pages)
#       - Rate limiting (1-second delay between downloads)
#       - Multi-fallback PDF URL detection (iframes, embeds, Google Docs viewer)
#       - Font-based text extraction with header/footer filtering
#       - Stops extraction at "Anexo" sections
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
# END OF PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════════════════
