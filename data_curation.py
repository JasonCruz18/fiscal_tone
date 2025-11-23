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
    print(f"📂 {folder} created")


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
            print(f"❌ Error processing row: {e}")

    print(f"⌛ scrape_cf_expanded executed in {timer() - t0:.2f} sec")
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
        print(f"\n🌐 Scraping list page: {url}")
        list_records, new_page_records = scrape_cf(url, already_scraped_pages=old_pages)
        all_new_records.extend(new_page_records)

    # Early exit if no new pages found
    if not all_new_records:
        print("\n🔎 No new pages: skipping download.")
        print(f"📝 Metadata unchanged: {metadata_path}")
        return pd.read_json(metadata_path, dtype=str)

    # Filter for truly new PDFs not yet downloaded
    new_df = pd.DataFrame(all_new_records).dropna(subset=["pdf_url"])
    mask_new = ~new_df["pdf_url"].isin(old_urls)
    df_to_download = new_df[mask_new].copy()

    # Sort chronologically (oldest first)
    df_to_download["date"] = pd.to_datetime(df_to_download["date"], dayfirst=True)
    df_to_download = df_to_download.sort_values("date").reset_index(drop=True)

    print(f"\n🔎 Found {len(df_to_download)} new PDFs to download")

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/pdf"}

    # Incremental download with metadata updates after each file
    temp_df = old_df.copy()

    for i, row in df_to_download.iterrows():
        pdf_url = row["pdf_url"]
        filename = row["pdf_filename"]
        page_url = row["page_url"]
        filepath = os.path.join(raw_pdf_folder, filename)

        print(f"\n[{i+1}/{len(df_to_download)}] 📄 {filename}")
        print(f"🔗 {pdf_url}")

        success = False

        # Primary download attempt
        try:
            r = requests.get(pdf_url, headers=headers, timeout=20)
            r.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(r.content)
            print(f"✅ Saved {filename}")
            success = True

        except Exception as e:
            print(f"⚠️ Primary failed: {e}")

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

                    print(f"✅ Saved via embed/data-pdf-src fallback: {filename}")
                    success = True
                else:
                    print("❌ No embed/data-pdf-src found")

            except Exception as e2:
                print(f"❌ Extended fallback failed: {e2}")

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

    print("\n📊 Summary:")
    print(f"📝 Metadata saved incrementally: {metadata_path}")
    print(f"⏱️ Done in {round(timer() - t0, 2)} sec")

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
            print(f"🗑️ Deleted: {filename}")
            removed_count += 1
        else:
            print(f"⚠️ File not found: {filename}")

    t1 = timer()

    print("\n📊 Summary:")
    print(f"🧹 Cleanup complete. Total files removed: {removed_count}")
    print(f"⏱️ Time taken: {t1 - t0:.2f} seconds")


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
        print(f"❌ Error reading {file_path}: {e}")
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
    print("\n📊 Summary:")
    print(f"📄 Total PDFs processed: {total_files}")
    print(f"💻 Editable PDFs: {editable_count}")
    print(f"🖨️ Scanned PDFs: {scanned_count}")
    print(f"📁 Saved editable PDFs in: '{output_dir_editable}'")
    print(f"📁 Saved scanned PDFs in: '{output_dir_scanned}'")
    print(f"⏱️ Time taken: {t1 - t0:.2f} seconds")


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
        print(f"❌ 'editable' folder does not exist in '{classification_folder}'.")
    if not os.path.isdir(scanned_folder):
        print(f"❌ 'scanned' folder does not exist in '{classification_folder}'.")

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
        print(f"⚠️ Warning: Missing columns {missing_cols}. They will not be reordered.")

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

    print(f"📑 Metadata enriched and saved to: '{metadata_json_path}'")

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

import pdfplumber
import json
from time import time as timer


# --- Helper: Header/Footer Detection ---


def is_header_footer(word, page_height, page_width):
    """
    Detects if a word belongs to header or footer based on position and content patterns.

    Uses both position-based detection (top/bottom margins) and content-based patterns
    (URLs, addresses, page numbers, institutional text).

    Args:
        word: dict with 'text', 'top', 'x0' keys from pdfplumber
        page_height: float, height of the page in points
        page_width: float, width of the page in points

    Returns:
        bool: True if word is part of header/footer, False otherwise
    """
    HEADER_MARGIN = 70  # Top margin (points)
    FOOTER_MARGIN = 70  # Bottom margin (points)

    # Position-based detection
    if word["top"] < HEADER_MARGIN:  # Header region
        return True
    if word["top"] > page_height - FOOTER_MARGIN:  # Footer region
        return True

    # Content-based patterns specific to Consejo Fiscal documents
    text = word["text"].strip()
    footer_patterns = [
        r"www\.cf\.gob\.pe",  # Website URL
        r"Av\.\s*Contralmirante\s*Montero",  # Office address
        r"^\d+/\d+$",  # Page numbers (e.g., "1/6")
        r"^CONSEJO\s+FISCAL",  # Institution name
        r"^Consejo\s+Fiscal\s+del\s+Perú",
        r"Magdalena\s+del\s+Mar",  # District name
    ]

    for pattern in footer_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False


# --- Helper: Table/Graphics Detection ---


def has_tables_or_graphics(page):
    """
    Detects if a page contains substantial tables or graphics that interfere with extraction.

    Uses multiple heuristics:
        - Image count (allows single logo, flags multiple charts)
        - Table detection with size threshold (>200x100 points)
        - Line count (>15 lines suggests complex table structure)

    Args:
        page: pdfplumber page object

    Returns:
        bool: True if page should be skipped due to tables/graphics, False otherwise
    """
    # Check for multiple embedded images (allow one logo)
    if len(page.images) > 1:
        return True

    # Check for substantial tables
    tables = page.find_tables()
    if tables:
        for table in tables:
            if table.bbox:
                width = table.bbox[2] - table.bbox[0]
                height = table.bbox[3] - table.bbox[1]
                # Skip if table is substantial
                if width > 200 and height > 100:
                    return True

    # Check for complex line structures (tables have many lines)
    lines = page.lines
    if len(lines) > 15:  # Threshold for decorative vs structural lines
        return True

    return False


# --- Helper: Section Header Detection ---


def is_section_header(word, last_word, is_bold, vertical_gap_threshold=20):
    """
    Distinguishes section headers from inline bold emphasis.

    Args:
        word: dict, current word with 'text', 'top' keys
        last_word: dict or None, previous word
        is_bold: bool, whether current word is bold
        vertical_gap_threshold: int, minimum vertical gap (points) for headers

    Returns:
        bool: True if likely a section header, False if inline emphasis
    """
    if not is_bold:
        return False

    # Large vertical gap indicates new section
    if last_word is not None:
        vertical_gap = word["top"] - last_word["top"]
        if vertical_gap > vertical_gap_threshold:
            return True

    # Common section header keywords in Fiscal Council documents
    text = word["text"].strip()
    header_keywords = [
        "Principales mensajes",
        "Opinión del Consejo Fiscal",
        "Opinión de CF",
        "Conclusión",
        "Recomendación",
        "Introducción",
        "Antecedentes",
    ]

    for keyword in header_keywords:
        if keyword.lower() in text.lower():
            return True

    return False


# --- Helper: First Page Title Detection ---


def is_first_page_title(word, page_num, page_height):
    """
    Detects if a word is part of the main document title on page 1.

    Args:
        word: dict with 'text', 'top' keys
        page_num: int, current page number (1-indexed)
        page_height: float, page height in points

    Returns:
        bool: True if part of document title, False otherwise
    """
    if page_num != 1:
        return False

    # Title region on first page (below header, top third of page)
    TITLE_REGION_TOP = 70
    TITLE_REGION_BOTTOM = 200

    if TITLE_REGION_TOP < word["top"] < TITLE_REGION_BOTTOM:
        text = word["text"].strip()
        title_patterns = [
            r"^Informe\s+(?:CF\s+)?N[°º]",
            r"^Comunicado\s+(?:CF\s+)?N[°º]",
            r"^Pronunciamiento",
        ]

        for pattern in title_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

    return False


# --- Main Text Extraction Function ---


def extract_text_from_single_pdf(
    file_path,
    FONT_MIN=11.0,
    FONT_MAX=11.9,
    exclude_bold=False,
    vertical_threshold=10,
):
    """
    Extracts main body text from an editable PDF using advanced filtering strategies.

    This function implements a sophisticated text extraction pipeline that:
        1. Filters by font size range (default 11.0-11.9)
        2. Excludes headers/footers by position and content patterns
        3. Skips first-page document titles
        4. Distinguishes section headers from inline bold emphasis
        5. Skips entire pages with substantial tables/graphics
        6. Detects paragraph breaks using vertical spacing and sentence endings
        7. Stops extraction at "Anexo" sections
        8. Saves extracted text to JSON file

    Args:
        file_path: str, path to the PDF file
        FONT_MIN: float, minimum font size to extract (default 11.0)
        FONT_MAX: float, maximum font size to extract (default 11.9)
        exclude_bold: bool, if True excludes all bold text; if False uses smart
                      filtering to keep inline emphasis but exclude headers
        vertical_threshold: int, minimum vertical spacing (points) for paragraph breaks

    Filtering Strategies:
        - Font size: FONT_MIN to FONT_MAX
        - Position: Top/bottom 70pt margins excluded
        - Content: URLs, page numbers, addresses, institution names
        - Document structure: Titles, section headers, appendices
        - Visual elements: Pages with tables/graphics skipped

    Output:
        - Prints extracted text to console for inspection
        - Saves JSON file with structure: [{"filename": str, "page": int, "text": str}, ...]
        - JSON saved in same directory as PDF with matching basename

    Returns:
        None
    """
    t0 = timer()

    print("🧠 Starting text extraction...\n")
    all_records = []
    pages_skipped = 0

    try:
        print(f"📄 Processing: {file_path}")
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_height = page.height
                page_width = page.width

                # Skip pages with substantial tables or graphics
                if has_tables_or_graphics(page):
                    print(f"⏭️  Skipping page {page_num}: contains tables or graphics")
                    pages_skipped += 1
                    continue

                # Extract words with metadata (size, position, font)
                words = page.extract_words(
                    extra_attrs=["size", "top", "fontname", "x0"]
                )

                # Apply multi-stage filtering
                clean_words = []
                last_word = None

                for word in words:
                    # Filter 1: Font size range
                    if not (FONT_MIN <= word["size"] <= FONT_MAX):
                        continue

                    # Filter 2: Headers/footers by position and content
                    if is_header_footer(word, page_height, page_width):
                        continue

                    # Filter 3: First-page document title
                    if is_first_page_title(word, page_num, page_height):
                        continue

                    # Filter 4: Bold text handling
                    is_bold = "Bold" in word.get("fontname", "")

                    if exclude_bold and is_bold:
                        continue  # Exclude all bold
                    elif is_bold:
                        # Smart filtering: exclude headers, keep inline emphasis
                        if is_section_header(
                            word, last_word, is_bold, vertical_gap_threshold=20
                        ):
                            continue

                    # Word passed all filters
                    clean_words.append(word)
                    last_word = word

                if not clean_words:
                    continue

                # Reconstruct paragraphs using vertical spacing analysis
                page_text = []
                paragraph_lines = []
                last_top = None
                last_word_text = ""

                for word in clean_words:
                    line_text = word["text"]
                    top = word["top"]

                    new_paragraph = False

                    if last_top is not None:
                        vertical_gap = top - last_top

                        # Paragraph break heuristics
                        if vertical_gap > vertical_threshold:
                            new_paragraph = True  # Large gap
                        elif (
                            vertical_gap > vertical_threshold * 0.7
                            and last_word_text.endswith((".", "!", "?"))
                        ):
                            new_paragraph = True  # Sentence end + moderate gap
                        elif line_text.strip().startswith(
                            (
                                "•",
                                "-",
                                "1.",
                                "2.",
                                "3.",
                                "i)",
                                "ii)",
                                "iii)",
                                "a)",
                                "b)",
                            )
                        ):
                            new_paragraph = True  # List item

                    if new_paragraph:
                        if paragraph_lines:
                            page_text.append(" ".join(paragraph_lines))
                        paragraph_lines = [line_text]
                    else:
                        paragraph_lines.append(line_text)

                    last_top = top
                    last_word_text = line_text

                # Add final paragraph
                if paragraph_lines:
                    page_text.append(" ".join(paragraph_lines))

                # Join paragraphs with double newline
                full_page_text = "\n\n".join(page_text)

                # Stop extraction at "Anexo" section
                match = re.search(r"(?mi)^ *Anexos?\b[\s\w]*:?", full_page_text)
                if match:
                    full_page_text = full_page_text[: match.start()].strip()
                    print(
                        f"🛑 'Anexo' detected on page {page_num}. Truncating content."
                    )
                    all_records.append(
                        {
                            "filename": os.path.basename(file_path),
                            "page": page_num,
                            "text": full_page_text,
                        }
                    )
                    break  # Stop processing further pages

                all_records.append(
                    {
                        "filename": os.path.basename(file_path),
                        "page": page_num,
                        "text": full_page_text,
                    }
                )

        if not all_records:
            print("⚠️ No text extracted from the PDF.")
            return

        # Print extracted text for inspection
        for record in all_records:
            print(f"\n📄 Page {record['page']} of {record['filename']}:")
            print(record["text"])

        # Save to JSON file in same directory as PDF
        json_filename = os.path.splitext(os.path.basename(file_path))[0] + ".json"
        json_file_path = os.path.join(os.path.dirname(file_path), json_filename)
        with open(json_file_path, "w", encoding="utf-8") as f:
            json.dump(all_records, f, ensure_ascii=False, indent=4)

        print(f"📂 Text saved to JSON file: {json_file_path}")

    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")

    t1 = timer()
    print(f"\n✅ Extraction complete.")
    print(f"📊 Pages with text extracted: {len(all_records)}")
    print(f"⏭️  Pages skipped (tables/graphics): {pages_skipped}")
    print(f"⏱️ Time taken: {t1 - t0:.2f} seconds")


# --- Example Usage (Testing) ---
# WARNING: Hardcoded path for testing purposes only

file_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Comunicado-Congreso-vf.pdf"
extract_text_from_single_pdf(
    file_path,
    FONT_MIN=11.0,
    FONT_MAX=11.9,
    exclude_bold=False,
    vertical_threshold=15,
)


# ═══════════════════════════════════════════════════════════════════════════════════════════
# END OF PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════════════════
