# *********************************************************************************************
#  Title:
# *********************************************************************************************
#
#   Program       : data_curation.py
#   Project       : Fiscal Tone
#   Author        : Jason Cruz
#   Last updated  : 11/22/2025
#   Python        : 3.12
#
#   Overview: [Text]
#
#   Sections:
#       1. Data Collection ...................................................................
#       2. 
# 
#   Notes:
#       "[Text]"
#
# *********************************************************************************************

# Libraries

import os
from pathlib import Path  # Importing Path module from pathlib to handle file and directory paths in a cross-platform way.

# Set-up
#-------------------------------------------------------------------------------------------------

# Get current working directory
PROJECT_ROOT = Path.cwd()  # Get the current working directory where the notebook is being executed.

# User input for folder location
user_input = input("Enter relative path (default='.'): ").strip() or "."  # Prompt user to input the folder path or use the default value "."
target_path = (PROJECT_ROOT / user_input).resolve()  # Combine the project root directory with user input to get the full target path.

# Create the necessary directories if they don't already exist
target_path.mkdir(parents=True, exist_ok=True)  # Creates the target folder and any necessary parent directories.
print(f"Using path: {target_path}")  # Print out the path being used for confirmation.

# Define paths for saving data and PDFs
data_folder = 'data'  # This folder will store the new Weekly Reports (post-2013), which are in PDF format.
raw_data_subfolder = os.path.join(data_folder, 'raw')  # Subfolder for saving the raw PDFs exactly as downloaded from the BCRP website.
input_data_subfolder = os.path.join(data_folder, 'input')  # Subfolder for saving reduced PDFs that contain only the selected pages with GDP growth tables.
output_data_subfolder = os.path.join(data_folder, 'output')

# Additional folders for metadata, records, and alert tracking
metadata_folder = 'metadata'  # Folder for storing metadata files like cf_metadata.json.

# Create additional required folders
for folder in [data_folder, raw_data_subfolder, input_data_subfolder, output_data_subfolder, metadata_folder]:
    os.makedirs(folder, exist_ok=True)  # Create the additional folders if they don't exist.
    print(f"📂 {folder} created")  # Print confirmation for each of these additional folders.


# 1. Data Collection
#-------------------------------------------------------------------------------------------------

import os
import time
from timeit import default_timer as timer
import requests
import pandas as pd
from urllib.parse import urlparse, parse_qs, unquote
from bs4 import BeautifulSoup

# ======================================================
# Utility: classify PPT / presentation documents
# ======================================================

def is_presentation_pdf(url_or_text):
    if not url_or_text:
        return False
    s = url_or_text.lower()
    ppt_keywords = [
        "ppt", "presentacion", "presentación", "diapositiva",
        "slides", "conferencia", "powerpoint"
    ]
    return any(kw in s for kw in ppt_keywords)


# ======================================================
# Utility: extract all PDF links
# ======================================================

def extract_pdf_links(dsoup):
    pdf_links = []
    for a in dsoup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" in href.lower():
            txt = a.text.strip() if a.text else ""
            pdf_links.append((href, txt))
    return pdf_links


# ======================================================
# Utility: select the best PDF from multiple candidates
# ======================================================

def select_appropriate_pdf(pdf_links):
    if not pdf_links:
        return None

    filtered = [
        (href, txt) for href, txt in pdf_links
        if not is_presentation_pdf(href) and not is_presentation_pdf(txt)
    ]

    candidates = filtered if filtered else pdf_links

    priority_keywords = [
        "comunicado", "informe", "nota", "reporte",
        "documento", "pronunciamiento"
    ]

    def score(x):
        href, _ = x
        h = href.lower()
        return sum(kw in h for kw in priority_keywords)

    return max(candidates, key=score)[0]


# ======================================================
# SCRAPER – Incremental: only visits detail pages not seen before
# ======================================================

def scrape_cf(url, already_scraped_pages):
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

            list_records.append({
                "date": date,
                "doc_title": doc_title,
                "page_url": page_url
            })

            if page_url in already_scraped_pages:
                continue

            detail = requests.get(page_url, timeout=15)
            dsoup = BeautifulSoup(detail.text, "html.parser")

            pdf_url = None

            # A) <a> PDF
            pdf_links = extract_pdf_links(dsoup)
            if pdf_links:
                pdf_url = select_appropriate_pdf(pdf_links)

            # B) iframe
            if not pdf_url:
                iframe = dsoup.find("iframe", src=lambda x: x and ".pdf" in x.lower())
                if iframe:
                    src = iframe["src"]
                    if src.startswith("//"):
                        src = "https:" + src
                    pdf_url = src

            # C) Google Docs viewer
            if not pdf_url:
                iframe = dsoup.find("iframe", src=lambda x: x and "docs.google.com" in x.lower())
                if iframe:
                    parsed = urlparse(iframe["src"])
                    q = parse_qs(parsed.query)
                    if "url" in q:
                        pdf_url = unquote(q["url"][0])

            # D) PDF viewer "Guardar"
            if not pdf_url:
                button = dsoup.find("button", id="downloadButton") or dsoup.find("span", string="Guardar")
                if button:
                    parent = button.find_parent("a")
                    if parent and parent.has_attr("href"):
                        pdf_url = parent["href"]

            filename = pdf_url.split("/")[-1] if pdf_url else None

            new_records.append({
                "date": date,
                "doc_title": doc_title,
                "page_url": page_url,
                "pdf_url": pdf_url,
                "pdf_filename": filename
            })

        except Exception as e:
            print(f"❌ Error processing row: {e}")

    print(f"⌛ scrape_cf_expanded executed in {timer() - t0:.2f} sec")
    return list_records, new_records



# ======================================================
# DOWNLOADER — with incremental JSON-safe saving (even if interrupted)
# ======================================================

def pdf_downloader(cf_urls, raw_pdf_folder, metadata_folder, metadata_json):

    t0 = timer()
    os.makedirs(raw_pdf_folder, exist_ok=True)
    os.makedirs(metadata_folder, exist_ok=True)

    metadata_path = os.path.join(metadata_folder, f"{metadata_json}.json")

    # Load previous metadata safely
    if os.path.exists(metadata_path):
        old_df = pd.read_json(metadata_path, dtype=str)
        old_urls = set(old_df["pdf_url"].dropna())
        old_pages = set(old_df["page_url"].dropna())
    else:
        old_df = pd.DataFrame()
        old_urls = set()
        old_pages = set()

    all_new_records = []

    # SCRAPE incremental
    for url in cf_urls:
        print(f"\n🌐 Scraping list page: {url}")
        list_records, new_page_records = scrape_cf(
            url, already_scraped_pages=old_pages
        )
        all_new_records.extend(new_page_records)

    if not all_new_records:
        print("\n🔎 No new pages: skipping download.")
        print(f"📝 Metadata unchanged: {metadata_path}")
        # → return existing JSON as DataFrame
        return pd.read_json(metadata_path, dtype=str)

    new_df = pd.DataFrame(all_new_records).dropna(subset=["pdf_url"])
    mask_new = ~new_df["pdf_url"].isin(old_urls)
    df_to_download = new_df[mask_new].copy()

    # Sort oldest → newest
    df_to_download["date"] = pd.to_datetime(df_to_download["date"], dayfirst=True)
    df_to_download = df_to_download.sort_values("date").reset_index(drop=True)

    print(f"\n🔎 Found {len(df_to_download)} new PDFs to download")

    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/pdf"}

    # ---- Incremental download + incremental JSON writing ----
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
        
        # Fallback attempt
        if not success:
            try:
                print("🔁 Trying extended fallback…")
                detail = requests.get(page_url, timeout=15)
                dsoup = BeautifulSoup(detail.text, "html.parser")
        
                iframe_url = None
        
                # 1) <embed src="...pdf">
                embed = dsoup.find("embed", src=lambda x: x and ".pdf" in x.lower())
                if embed:
                    iframe_url = embed["src"]
        
                # 2) <div data-pdf-src="...pdf">
                if not iframe_url:
                    divpdf = dsoup.find("div", attrs={"data-pdf-src": True})
                    if divpdf and ".pdf" in divpdf["data-pdf-src"].lower():
                        iframe_url = divpdf["data-pdf-src"]
        
                # Normalize URL
                if iframe_url and iframe_url.startswith("//"):
                    iframe_url = "https:" + iframe_url
        
                if iframe_url:
                    print(f"   ⇢ fallback PDF URL: {iframe_url}")
        
                    r2 = requests.get(iframe_url, headers=headers, timeout=20)
                    r2.raise_for_status()
        
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

        # === Incremental update to metadata (even if interrupted later) ===
        temp_df = pd.concat([temp_df, pd.DataFrame([row])], ignore_index=True)
        temp_df.to_json(metadata_path, orient='records', indent=2, force_ascii=False, date_format='iso')

        # avoid rate limit
        time.sleep(1)

    print("\n📊 Summary:")
    print(f"📝 Metadata saved incrementally: {metadata_path}")
    print(f"⏱️ Done in {round(timer() - t0, 2)} sec")

    # === RETURN THE JSON AS DATAFRAME ===
    final_df = pd.read_json(metadata_path, dtype=str)
    return final_df

#%%
cf_urls = [
    "https://cf.gob.pe/p/informes/",
    "https://cf.gob.pe/p/comunicados/"
]

metadata_df = pdf_downloader(
    cf_urls=cf_urls,
    raw_pdf_folder=raw_data_subfolder,
    metadata_folder=metadata_folder,
    metadata_json="cf_metadata"
)

# Delete selected PDFs

# Lista de archivos a eliminar
pdfs_to_remove = [
    "Informe-anual-2017_CF_vf.pdf", # This is a way too long document containing statistical analaysis. We're focus only on text as comunicados from CF.
    "Informe-anual-del-Consejo-Fiscal-2018-version-final1.pdf"
]

def remove_unwanted_pdfs(folder_path, filenames_to_remove):
    """
    Deletes specific unwanted PDF files from a given folder.

    Parameters:
    - folder_path: str, the directory containing the PDFs
    - filenames_to_remove: list of str, filenames to delete
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

    print(f"\n🧹 Cleanup complete. Total files removed: {removed_count}")
    print(f"⏱️ Time taken: {t1 - t0:.2f} seconds")
    
remove_unwanted_pdfs(raw_data_subfolder, pdfs_to_remove)

# Classifying into editable and scanned pdfs

import fitz  # PyMuPDF, used to extract text from PDFs

def is_editable_pdf(file_path, min_text_length=20):
    """Check if a PDF contains extractable text (editable)."""
    try:
        with fitz.open(file_path) as doc:
            return len("".join(page.get_text() for page in doc).strip()) >= min_text_length
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}")
        return False

import os
import shutil
from timeit import default_timer as timer

def classify_pdfs_by_type(classification_folder):
    """
    Classifies PDF files into 'editable' and 'scanned' subfolders.
    This function now only focuses on classifying the type of raw data (editable or scanned) and moving files.
    
    Parameters:
    - classification_folder: str, the directory where 'editable' and 'scanned' subfolders will be created.
    
    Returns:
    - None
    """
    # Ensure classification_folder is a list, even if a single folder is passed
    if isinstance(classification_folder, str):
        classification_folder = [classification_folder]

    # Create the 'editable' and 'scanned' subfolders within the classification_folder
    output_dir_editable = os.path.join(classification_folder[0], "editable")
    output_dir_scanned = os.path.join(classification_folder[0], "scanned")
    os.makedirs(output_dir_editable, exist_ok=True)
    os.makedirs(output_dir_scanned, exist_ok=True)

    total_files = 0
    scanned_count = 0
    editable_count = 0

    t0 = timer()
    print("🔍 Starting PDF classification...")

    # Iterate through the provided folders
    for folder in classification_folder:
        for filename in os.listdir(folder):
            if filename.lower().endswith(".pdf"):
                total_files += 1
                pdf_path = os.path.join(folder, filename)

                # Classify and move the PDF to the appropriate folder
                if is_editable_pdf(pdf_path):
                    shutil.move(pdf_path, os.path.join(output_dir_editable, filename))
                    editable_count += 1
                else:
                    shutil.move(pdf_path, os.path.join(output_dir_scanned, filename))
                    scanned_count += 1

    t1 = timer()

    # Print a summary
    print("\n📊 Summary:")
    print(f"📄 Total PDFs processed: {total_files}")
    print(f"💻 Editable PDFs: {editable_count}")
    print(f"🖨️ Scanned PDFs: {scanned_count}")
    print(f"📁 Saved editable PDFs in: '{output_dir_editable}'")
    print(f"📁 Saved scanned PDFs in: '{output_dir_scanned}'")
    print(f"⏱️ Time taken: {t1 - t0:.2f} seconds")

# Define the folder paths
classification_folder = raw_data_subfolder

# Call the function to classify PDFs
classify_pdfs_by_type(classification_folder)


# Enrich metadata 

import os
import pandas as pd
import re

def metadata_enrichment(classification_folder, metadata_folder, metadata_json="cf_metadata"):
    """
    Enriches metadata with information such as 'pdf_type', 'doc_type', 'doc_number', 'year', and 'month'.

    Parameters:
    - classification_folder: str, the directory where 'editable' and 'scanned' subfolders exist.
    - metadata_folder: str, the folder where the metadata JSON file is located.
    - metadata_json: str, the name of the JSON file containing metadata (without the '.json' extension).

    Returns:
    - metadata_df: DataFrame with the enriched metadata.
    """
    # Add .json extension to metadata_json if not provided
    metadata_json_path = os.path.join(metadata_folder, f"{metadata_json}.json")

    # Load the metadata JSON file
    metadata_df = pd.read_json(metadata_json_path)

    # Ensure 'pdf_type', 'doc_type', 'doc_number', 'year' and 'month' columns exist
    if 'pdf_type' not in metadata_df.columns:
        metadata_df['pdf_type'] = ''
    if 'doc_type' not in metadata_df.columns:
        metadata_df['doc_type'] = ''
    if 'doc_number' not in metadata_df.columns:
        metadata_df['doc_number'] = ''
    if 'year' not in metadata_df.columns:
        metadata_df['year'] = ''
    if 'month' not in metadata_df.columns:
        metadata_df['month'] = ''

    # Function to extract 'doc_type', 'doc_number', 'year' from 'doc_title' column
    def extract_doc_info(row):
        doc_title = row["doc_title"]
        # Extract document type (Informe, Comunicado), document number, and year
        match = re.search(r"\b(Informe|Comunicado)\b(?:\s+CF)?(?:\s+(?:N[°ºo]|No))?\s*(\d{2,4})", doc_title, re.IGNORECASE)
        doc_type = match.group(1).capitalize() if match else None
        doc_number = match.group(2) if match and match.lastindex >= 2 else None
        year_match = re.search(r"\b(\d{4})\b", str(row.get("date", "")))
        year = year_match.group(1) if year_match else None

        # Convert doc_number to integer (this removes leading zeros)
        if doc_number:
            doc_number = int(doc_number)

        return pd.Series({"doc_type": doc_type, "doc_number": doc_number, "year": year})

    # Enrich metadata by applying doc_type, doc_number, and year extraction
    metadata_df[["doc_type", "doc_number", "year"]] = metadata_df.apply(extract_doc_info, axis=1)

    # Function to extract 'month' from 'date' column (assuming 'date' is in "YYYY-MM-DD" format)
    def extract_month(row):
        date_val = row["date"]
        if pd.notna(date_val):  # Check if the date is not NaN
            # Check if it's already a Timestamp object (pandas auto-converts dates)
            if isinstance(date_val, pd.Timestamp):
                return date_val.month
            # If it's a string, extract month from the date string
            try:
                month = int(str(date_val).split('-')[1])  # Extract the month (second part of the date)
                return month
            except (IndexError, ValueError):
                return None
        return None

    # Add 'month' column by applying the extract_month function
    metadata_df['month'] = metadata_df.apply(extract_month, axis=1)

    # Ensure 'editable' and 'scanned' subfolders exist in the provided classification_folder
    editable_folder = os.path.join(classification_folder, "editable")
    scanned_folder = os.path.join(classification_folder, "scanned")

    # Check if the 'editable' and 'scanned' folders exist
    if not os.path.isdir(editable_folder):
        print(f"❌ 'editable' folder does not exist in '{classification_folder}'.")
    if not os.path.isdir(scanned_folder):
        print(f"❌ 'scanned' folder does not exist in '{classification_folder}'.")

    # Update 'pdf_type' based on folder classification
    for folder, file_type in [(editable_folder, "editable"), (scanned_folder, "scanned")]:
        if os.path.isdir(folder):
            for filename in os.listdir(folder):
                if filename.lower().endswith(".pdf"):
                    metadata_df.loc[metadata_df['pdf_filename'] == filename, 'pdf_type'] = file_type

    # Reorder columns as requested: 'date', 'year', 'month', 'page_url', 'pdf_url', 'pdf_filename', 'pdf_type', 'doc_title', 'doc_type', 'doc_number'
    column_order = ['date', 'year', 'month', 'page_url', 'pdf_url', 'pdf_filename', 'pdf_type', 'doc_title', 'doc_type', 'doc_number']
    
    # Check if all columns exist before reordering
    missing_cols = [col for col in column_order if col not in metadata_df.columns]
    if missing_cols:
        print(f"⚠️ Warning: Missing columns {missing_cols}. They will not be reordered.")

    # Reorder columns if they exist
    metadata_df = metadata_df[column_order]

    # Save the enriched metadata back to the original JSON file (replacing it)
    metadata_df.to_json(metadata_json_path, orient='records', indent=2, force_ascii=False, date_format='iso')

    print(f"📑 Metadata enriched and saved to: '{metadata_json_path}'")
    
    return metadata_df

# Define the folder paths
classification_folder = raw_data_subfolder
metadata_folder = metadata_folder
metadata_json = "cf_metadata"  # Note: without the ".json" extension

updated_metadata_df = metadata_enrichment(classification_folder, metadata_folder, metadata_json)


# 2. Data extraction
#-------------------------------------------------------------------------------------------------

import os
import pdfplumber
import json
from time import time as timer

# ======================================================
# Helper functions for improved text extraction
# ======================================================

def is_header_footer(word, page_height, page_width):
    """
    Detect if a word is part of header or footer based on position and content patterns.

    Parameters:
    - word: dict with 'text', 'top', 'x0' keys from pdfplumber
    - page_height: height of the page
    - page_width: width of the page

    Returns:
    - bool: True if word is header/footer, False otherwise
    """
    # Position-based detection
    HEADER_MARGIN = 70  # Top 70 points of page
    FOOTER_MARGIN = 70  # Bottom 70 points of page

    # Check if in header region (top of page)
    if word["top"] < HEADER_MARGIN:
        return True

    # Check if in footer region (bottom of page)
    if word["top"] > page_height - FOOTER_MARGIN:
        return True

    # Content-based patterns for headers/footers
    text = word["text"].strip()
    footer_patterns = [
        r"www\.cf\.gob\.pe",
        r"Av\.\s*Contralmirante\s*Montero",
        r"^\d+/\d+$",  # Page numbers like "1/6", "2/15"
        r"^CONSEJO\s+FISCAL",
        r"^Consejo\s+Fiscal\s+del\s+Perú",
        r"Magdalena\s+del\s+Mar"
    ]

    for pattern in footer_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False


def has_tables_or_graphics(page):
    """
    Detect if a page contains tables or graphics that might interfere with text extraction.

    Parameters:
    - page: pdfplumber page object

    Returns:
    - bool: True if page has tables/graphics, False otherwise
    """
    # Check for embedded images (actual graphics/charts)
    # Allow single image (typically the logo), but skip if multiple images
    if len(page.images) > 1:
        return True

    # Check for table structures using pdfplumber's table detection
    tables = page.find_tables()
    if tables:
        # Only skip if table is substantial (has actual data)
        for table in tables:
            if table.bbox:  # Has bounding box
                # Calculate table size
                width = table.bbox[2] - table.bbox[0]
                height = table.bbox[3] - table.bbox[1]
                # Skip if table takes up significant space
                if width > 200 and height > 100:
                    return True

    # Check for horizontal/vertical lines (common in tables)
    # Increased threshold - fiscal council docs have some decorative lines/borders
    lines = page.lines
    if len(lines) > 15:  # More than 15 lines suggests complex table structure
        return True

    return False


def is_section_header(word, last_word, is_bold, vertical_gap_threshold=20):
    """
    Detect if a bold word is a section header vs inline emphasis.

    Parameters:
    - word: current word dict
    - last_word: previous word dict (or None)
    - is_bold: whether current word is bold
    - vertical_gap_threshold: minimum gap to consider as new section

    Returns:
    - bool: True if this is likely a section header, False if inline emphasis
    """
    if not is_bold:
        return False

    # If there's a large vertical gap before this word, likely a header
    if last_word is not None:
        vertical_gap = word["top"] - last_word["top"]
        if vertical_gap > vertical_gap_threshold:
            return True

    # Common section header patterns
    text = word["text"].strip()
    header_keywords = [
        "Principales mensajes",
        "Opinión del Consejo Fiscal",
        "Opinión de CF",
        "Conclusión",
        "Recomendación",
        "Introducción",
        "Antecedentes"
    ]

    for keyword in header_keywords:
        if keyword.lower() in text.lower():
            return True

    return False


def is_first_page_title(word, page_num, page_height):
    """
    Detect if a word is part of the main document title on the first page.

    Parameters:
    - word: word dict
    - page_num: current page number (1-indexed)
    - page_height: page height

    Returns:
    - bool: True if this is part of the title, False otherwise
    """
    if page_num != 1:
        return False

    # Title is typically in the top portion of first page (but below header margin)
    TITLE_REGION_TOP = 70  # Below header
    TITLE_REGION_BOTTOM = 200  # Within top third of page

    if TITLE_REGION_TOP < word["top"] < TITLE_REGION_BOTTOM:
        # Check for title patterns
        text = word["text"].strip()
        title_patterns = [
            r"^Informe\s+(?:CF\s+)?N[°º]",
            r"^Comunicado\s+(?:CF\s+)?N[°º]",
            r"^Pronunciamiento"
        ]

        for pattern in title_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True

    return False


def extract_text_from_single_pdf(file_path, FONT_MIN=11.0, FONT_MAX=11.9, exclude_bold=False, vertical_threshold=10):
    """
    Extracts raw text from a single editable PDF, extracting only main body paragraphs.

    This function uses multiple filtering strategies to exclude headers, footers, titles,
    section headers, and tables/graphics, while preserving emphasized terms in paragraphs.

    Parameters:
    - file_path: str, path to the single PDF file to be processed
    - FONT_MIN: float, minimum font size to consider (default 11.0)
    - FONT_MAX: float, maximum font size to consider (default 11.9)
    - exclude_bold: bool, whether to exclude ALL bold text (default False)
                    When False, uses smart filtering to keep emphasized words but exclude headers
    - vertical_threshold: int, the minimum vertical space between lines to consider as a new paragraph (default 10)

    Filtering applied:
    - Font size range (FONT_MIN to FONT_MAX)
    - Headers/footers by position (top/bottom 70pt margins)
    - Headers/footers by content pattern (URLs, page numbers, institutional text)
    - First-page document title
    - Section headers (bold text with large vertical gaps)
    - Tables and graphics (entire pages skipped)
    - Anexo sections (stops extraction)

    Prints the extracted text for inspection and saves it to a JSON file in the same folder.
    """
    t0 = timer()

    print("🧠 Starting text extraction...\n")
    all_records = []
    pages_skipped = 0

    try:
        print(f"📄 Processing: {file_path}")
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                # Get page dimensions
                page_height = page.height
                page_width = page.width

                # Skip pages with tables or graphics
                if has_tables_or_graphics(page):
                    print(f"⏭️  Skipping page {page_num}: contains tables or graphics")
                    pages_skipped += 1
                    continue

                # Extract words with their size, vertical position, and fontname
                words = page.extract_words(extra_attrs=["size", "top", "fontname", "x0"])

                # Enhanced filtering with multiple criteria
                clean_words = []
                last_word = None

                for word in words:
                    # Font size filter
                    if not (FONT_MIN <= word["size"] <= FONT_MAX):
                        continue

                    # Header/footer filter
                    if is_header_footer(word, page_height, page_width):
                        continue

                    # First-page title filter
                    if is_first_page_title(word, page_num, page_height):
                        continue

                    # Bold text handling
                    is_bold = "Bold" in word.get("fontname", "")

                    if exclude_bold and is_bold:
                        # Old behavior: exclude all bold
                        continue
                    elif is_bold:
                        # Smart filtering: exclude section headers but keep emphasis
                        if is_section_header(word, last_word, is_bold, vertical_gap_threshold=20):
                            continue

                    # Word passed all filters
                    clean_words.append(word)
                    last_word = word

                if not clean_words:
                    continue

                # Initialize variables for paragraph detection
                page_text = []
                paragraph_lines = []
                last_top = None
                last_word_text = ""

                # Process each word and check vertical spacing between lines
                for word in clean_words:
                    line_text = word["text"]
                    top = word["top"]

                    # Enhanced paragraph break detection
                    new_paragraph = False

                    if last_top is not None:
                        vertical_gap = top - last_top

                        # Large gap = definite break
                        if vertical_gap > vertical_threshold:
                            new_paragraph = True
                        # Sentence ending + moderate gap
                        elif vertical_gap > vertical_threshold * 0.7 and last_word_text.endswith(('.', '!', '?')):
                            new_paragraph = True
                        # List item detection
                        elif line_text.strip().startswith(('•', '-', '1.', '2.', '3.', 'i)', 'ii)', 'iii)', 'a)', 'b)')):
                            new_paragraph = True

                    if new_paragraph:
                        # Add the previous paragraph
                        if paragraph_lines:
                            page_text.append(" ".join(paragraph_lines))
                        paragraph_lines = [line_text]
                    else:
                        paragraph_lines.append(line_text)

                    last_top = top
                    last_word_text = line_text

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
                    # Stop processing further pages after anexo
                    all_records.append({
                        "filename": os.path.basename(file_path),
                        "page": page_num,
                        "text": full_page_text
                    })
                    break

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
    print(f"\n✅ Extraction complete.")
    print(f"📊 Pages with text extracted: {len(all_records)}")
    print(f"⏭️  Pages skipped (tables/graphics): {pages_skipped}")
    print(f"⏱️ Time taken: {t1 - t0:.2f} seconds")

# Example usage: specify the PDF file path
file_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Comunicado-Congreso-vf.pdf"
extract_text_from_single_pdf(file_path, FONT_MIN=11.0, FONT_MAX=11.9, exclude_bold=False, vertical_threshold=15)



# 3.  
#-------------------------------------------------------------------------------------------------