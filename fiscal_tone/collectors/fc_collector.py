"""
Fiscal Council Document Collector.

This module handles web scraping and downloading of PDF documents from
Peru's Fiscal Council (Consejo Fiscal) website at cf.gob.pe.

Main Functions:
    scrape_cf: Scrape document metadata from CF list pages
    pdf_downloader: Download PDFs with incremental saving and fallback strategies
    remove_unwanted_pdfs: Remove specific PDFs (e.g., annual reports)

Example:
    >>> from fiscal_tone.collectors.fc_collector import pdf_downloader
    >>> df = pdf_downloader(
    ...     cf_urls=["https://cf.gob.pe/p/informes/"],
    ...     raw_pdf_folder="data/raw",
    ...     metadata_folder="metadata",
    ...     metadata_json="cf_metadata"
    ... )
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from timeit import default_timer as timer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Default configuration (can be overridden by config file)
DEFAULT_REQUEST_DELAY = 1.0  # seconds between downloads
DEFAULT_REQUEST_TIMEOUT = 20  # seconds
DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# URLs to scrape by default
DEFAULT_CF_URLS = [
    "https://cf.gob.pe/p/informes/",
    "https://cf.gob.pe/p/comunicados/",
]

# Annual reports to exclude (contain statistical analysis, not fiscal tone communications)
DEFAULT_PDFS_TO_REMOVE = [
    "Informe-anual-2017_CF_vf.pdf",
    "Informe-anual-del-Consejo-Fiscal-2018-version-final1.pdf",
]


def is_presentation_pdf(url_or_text: str | None) -> bool:
    """
    Detect if a URL or text indicates a PowerPoint presentation file.

    Args:
        url_or_text: URL or link text to check for presentation keywords.

    Returns:
        True if presentation-related keywords found, False otherwise.

    Example:
        >>> is_presentation_pdf("informe_presentacion.pdf")
        True
        >>> is_presentation_pdf("comunicado_001.pdf")
        False
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


def extract_pdf_links(dsoup: BeautifulSoup) -> list[tuple[str, str]]:
    """
    Extract all PDF links from a BeautifulSoup parsed HTML page.

    Args:
        dsoup: BeautifulSoup object of the detail page.

    Returns:
        List of tuples [(href, link_text), ...] for all PDF links found.

    Example:
        >>> soup = BeautifulSoup('<a href="doc.pdf">Document</a>', 'html.parser')
        >>> extract_pdf_links(soup)
        [('doc.pdf', 'Document')]
    """
    pdf_links = []
    for a in dsoup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" in href.lower():
            txt = a.text.strip() if a.text else ""
            pdf_links.append((href, txt))
    return pdf_links


def select_appropriate_pdf(pdf_links: list[tuple[str, str]]) -> str | None:
    """
    Select the most appropriate PDF from multiple candidates using keyword scoring.

    Filters out presentations first, then scores remaining PDFs by priority keywords
    (comunicado, informe, nota, reporte, documento, pronunciamiento).

    Args:
        pdf_links: List of tuples [(href, link_text), ...].

    Returns:
        URL of the selected PDF, or None if no candidates.

    Example:
        >>> links = [("presentacion.pdf", "PPT"), ("comunicado_001.pdf", "Doc")]
        >>> select_appropriate_pdf(links)
        'comunicado_001.pdf'
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

    def score(x: tuple[str, str]) -> int:
        href, _ = x
        h = href.lower()
        return sum(kw in h for kw in priority_keywords)

    return max(candidates, key=score)[0]


def scrape_cf(
    url: str,
    already_scraped_pages: set[str],
    timeout: int = 15,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Scrape a Consejo Fiscal list page and extract PDF metadata.

    Implements incremental scraping by skipping detail pages already processed.
    Uses multiple fallback strategies to find PDF URLs:
        A) Direct <a> tag PDF links
        B) iframe src attributes
        C) Google Docs viewer URL extraction
        D) Download button with "Guardar" text

    Args:
        url: URL of the list page to scrape (e.g., cf.gob.pe/p/informes/).
        already_scraped_pages: URLs of detail pages already processed.
        timeout: Request timeout in seconds.

    Returns:
        Tuple of (list_records, new_records):
            - list_records: All entries from the list page (date, title, page_url)
            - new_records: Only new entries with PDF metadata extracted

    Example:
        >>> records, new = scrape_cf("https://cf.gob.pe/p/informes/", set())
        >>> len(new) > 0  # Should find some documents
        True
    """
    t0 = timer()

    response = requests.get(url, timeout=timeout)
    soup = BeautifulSoup(response.text, "html.parser")

    rows = soup.select("table.table tbody tr")
    new_records: list[dict[str, Any]] = []
    list_records: list[dict[str, Any]] = []

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
            detail = requests.get(page_url, timeout=timeout)
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

    print(f"[DONE] scrape_cf executed in {timer() - t0:.2f} sec")
    return list_records, new_records


def pdf_downloader(
    cf_urls: list[str] | None = None,
    raw_pdf_folder: str = "data/raw",
    metadata_folder: str = "metadata",
    metadata_json: str = "cf_metadata",
    request_delay: float = DEFAULT_REQUEST_DELAY,
    request_timeout: int = DEFAULT_REQUEST_TIMEOUT,
    user_agent: str = DEFAULT_USER_AGENT,
) -> pd.DataFrame:
    """
    Download PDFs from Consejo Fiscal URLs with incremental metadata saving.

    Implements robust download pipeline with:
        - Incremental scraping (skips already processed pages)
        - Incremental metadata saving (survives interruptions)
        - Primary + fallback download strategies (<embed>, data-pdf-src)
        - Rate limiting (configurable delay between downloads)
        - Chronological sorting (oldest to newest)

    Args:
        cf_urls: URLs to scrape (defaults to informes + comunicados pages).
        raw_pdf_folder: Folder to save downloaded PDFs.
        metadata_folder: Folder containing metadata JSON.
        metadata_json: JSON filename without extension.
        request_delay: Seconds to wait between downloads (rate limiting).
        request_timeout: Request timeout in seconds.
        user_agent: User-Agent header for HTTP requests.

    Returns:
        DataFrame with complete metadata including newly downloaded PDFs.

    Example:
        >>> df = pdf_downloader(
        ...     cf_urls=["https://cf.gob.pe/p/informes/"],
        ...     raw_pdf_folder="data/raw"
        ... )
        >>> "pdf_filename" in df.columns
        True
    """
    if cf_urls is None:
        cf_urls = DEFAULT_CF_URLS

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
        old_urls: set[str] = set()
        old_pages: set[str] = set()

    all_new_records: list[dict[str, Any]] = []

    # Scrape all CF URLs incrementally
    for url in cf_urls:
        print(f"\n[SCRAPING] list page: {url}")
        list_records, new_page_records = scrape_cf(url, already_scraped_pages=old_pages)
        all_new_records.extend(new_page_records)

    # Early exit if no new pages found
    if not all_new_records:
        print("\n[INFO] No new pages: skipping download.")
        print(f"Metadata unchanged: {metadata_path}")
        if os.path.exists(metadata_path):
            return pd.read_json(metadata_path, dtype=str)
        return pd.DataFrame()

    # Filter for truly new PDFs not yet downloaded
    new_df = pd.DataFrame(all_new_records).dropna(subset=["pdf_url"])
    mask_new = ~new_df["pdf_url"].isin(old_urls)
    df_to_download = new_df[mask_new].copy()

    # Sort chronologically (oldest first)
    df_to_download["date"] = pd.to_datetime(df_to_download["date"], dayfirst=True)
    df_to_download = df_to_download.sort_values("date").reset_index(drop=True)

    print(f"\n[INFO] Found {len(df_to_download)} new PDFs to download")

    headers = {"User-Agent": user_agent, "Accept": "application/pdf"}

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
            r = requests.get(pdf_url, headers=headers, timeout=request_timeout)
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
                print("[RETRY] Trying extended fallback...")
                detail = requests.get(page_url, timeout=request_timeout)
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
                    print(f"   -> fallback PDF URL: {iframe_url}")

                    r2 = requests.get(iframe_url, headers=headers, timeout=request_timeout)
                    r2.raise_for_status()

                    # Verify content type is PDF
                    if "pdf" not in r2.headers.get("Content-Type", "").lower():
                        raise ValueError("Server returned HTML instead of PDF")

                    with open(filepath, "wb") as f:
                        f.write(r2.content)

                    print(f"[SAVED] via fallback: {filename}")
                    success = True
                else:
                    print("[ERROR] No fallback URL found")

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
        time.sleep(request_delay)

    print("\n[SUMMARY]")
    print(f"Metadata saved incrementally: {metadata_path}")
    print(f"Done in {round(timer() - t0, 2)} sec")

    # Return complete metadata as DataFrame
    final_df = pd.read_json(metadata_path, dtype=str)
    return final_df


def remove_unwanted_pdfs(
    folder_path: str | Path,
    filenames_to_remove: list[str] | None = None,
) -> int:
    """
    Delete specific unwanted PDF files from a given folder.

    Args:
        folder_path: Directory containing the PDFs.
        filenames_to_remove: Filenames to delete (defaults to annual reports).

    Returns:
        Number of files successfully removed.

    Example:
        >>> removed = remove_unwanted_pdfs("data/raw", ["unwanted.pdf"])
        >>> isinstance(removed, int)
        True
    """
    if filenames_to_remove is None:
        filenames_to_remove = DEFAULT_PDFS_TO_REMOVE

    t0 = timer()
    removed_count = 0

    print(f"[CLEANUP] Removing files in: {folder_path}")
    for filename in filenames_to_remove:
        full_path = os.path.join(folder_path, filename)
        if os.path.exists(full_path):
            os.remove(full_path)
            print(f"[DELETED] {filename}")
            removed_count += 1
        else:
            print(f"[SKIP] Not found: {filename}")

    print(f"\n[SUMMARY] Removed {removed_count} files in {timer() - t0:.2f} sec")
    return removed_count


def run_collection_stage(
    cf_urls: list[str] | None = None,
    raw_pdf_folder: str = "data/raw",
    metadata_folder: str = "metadata",
    metadata_json: str = "cf_metadata",
    cleanup: bool = True,
) -> pd.DataFrame:
    """
    Execute the complete document collection stage.

    This is a high-level function that runs the full collection pipeline:
    1. Scrape document metadata from CF website
    2. Download new PDFs incrementally
    3. Optionally remove unwanted PDFs (annual reports)

    Args:
        cf_urls: URLs to scrape (defaults to informes + comunicados).
        raw_pdf_folder: Folder to save downloaded PDFs.
        metadata_folder: Folder for metadata JSON.
        metadata_json: JSON filename without extension.
        cleanup: Whether to remove annual reports after download.

    Returns:
        DataFrame with metadata of all collected documents.

    Example:
        >>> df = run_collection_stage(raw_pdf_folder="data/raw")
        >>> "pdf_filename" in df.columns
        True
    """
    print("=" * 70)
    print("STAGE 1-2: DOCUMENT COLLECTION")
    print("=" * 70)

    # Step 1: Download PDFs
    metadata_df = pdf_downloader(
        cf_urls=cf_urls,
        raw_pdf_folder=raw_pdf_folder,
        metadata_folder=metadata_folder,
        metadata_json=metadata_json,
    )

    # Step 2: Remove unwanted PDFs (annual reports)
    if cleanup:
        remove_unwanted_pdfs(raw_pdf_folder)

    print("\n[DONE] Collection stage complete")
    print(f"Total documents in metadata: {len(metadata_df)}")

    return metadata_df


# =============================================================================
# CLI Entry Point (for standalone execution)
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Collect PDF documents from Peru's Fiscal Council website"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="data/raw",
        help="Output folder for downloaded PDFs (default: data/raw)",
    )
    parser.add_argument(
        "--metadata",
        "-m",
        default="metadata",
        help="Metadata folder (default: metadata)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip removal of annual reports",
    )

    args = parser.parse_args()

    # Run collection
    df = run_collection_stage(
        raw_pdf_folder=args.output,
        metadata_folder=args.metadata,
        cleanup=not args.no_cleanup,
    )

    print(f"\nCollection complete. {len(df)} documents in metadata.")
