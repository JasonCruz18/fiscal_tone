"""
Restore all PDFs from cf_metadata.json using their stored URLs.

Reads metadata/cf_metadata.json, downloads every PDF whose file is missing,
and places it directly into data/raw/editable/ or data/raw/scanned/ based on
the pdf_type field already recorded in metadata.

Usage:
    python scripts/restore_pdfs.py
    python scripts/restore_pdfs.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

# Windows console UTF-8 fix
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
METADATA_PATH = ROOT / "metadata" / "cf_metadata.json"
RAW_DIR = ROOT / "data" / "raw"
EDITABLE_DIR = RAW_DIR / "editable"
SCANNED_DIR = RAW_DIR / "scanned"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 30
DELAY = 1.2  # seconds between downloads


def dest_folder(pdf_type: str) -> Path:
    if pdf_type == "scanned":
        return SCANNED_DIR
    return EDITABLE_DIR  # editable, empty, or None all go here


def download_pdf(url: str, dest: Path, dry_run: bool = False) -> bool:
    if dest.exists():
        print(f"  [SKIP] already exists: {dest.name}")
        return True
    if dry_run:
        print(f"  [DRY]  would download -> {dest}")
        return True
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        if r.status_code != 200:
            print(f"  [ERR]  HTTP {r.status_code} for {url}")
            return False
        content_type = r.headers.get("Content-Type", "")
        if "pdf" not in content_type.lower() and "octet" not in content_type.lower():
            print(f"  [WARN] unexpected Content-Type '{content_type}' for {dest.name}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        size_kb = dest.stat().st_size // 1024
        print(f"  [OK]   {dest.name}  ({size_kb} KB)")
        return True
    except Exception as exc:
        print(f"  [ERR]  {exc} for {url}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore missing PDFs from cf_metadata.json")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be downloaded without downloading")
    args = parser.parse_args()

    if not METADATA_PATH.exists():
        print(f"[ERROR] metadata not found: {METADATA_PATH}")
        sys.exit(1)

    with open(METADATA_PATH, encoding="utf-8") as f:
        metadata = json.load(f)

    EDITABLE_DIR.mkdir(parents=True, exist_ok=True)
    SCANNED_DIR.mkdir(parents=True, exist_ok=True)

    total = len(metadata)
    skipped = downloaded = failed = 0

    print(f"\nRestoring {total} PDFs from metadata...\n")

    for i, record in enumerate(metadata, 1):
        filename = record.get("pdf_filename", "")
        url = record.get("pdf_url", "")
        pdf_type = record.get("pdf_type", "editable")

        if not filename or not url:
            print(f"  [{i}/{total}] [SKIP] missing filename or url in record")
            skipped += 1
            continue

        folder = dest_folder(pdf_type)
        dest = folder / filename

        print(f"[{i:02d}/{total}] {filename}  ({pdf_type})")
        ok = download_pdf(url, dest, dry_run=args.dry_run)

        if ok:
            if dest.exists() or args.dry_run:
                downloaded += 1
            else:
                skipped += 1
        else:
            failed += 1

        if not args.dry_run and not dest.exists():
            pass
        elif ok and not args.dry_run:
            time.sleep(DELAY)

    print()
    print("=" * 50)
    print(f"Done. Downloaded/present: {downloaded}  |  Failed: {failed}  |  Skipped: {skipped}")
    editable_count = len(list(EDITABLE_DIR.glob("*.pdf")))
    scanned_count = len(list(SCANNED_DIR.glob("*.pdf")))
    print(f"  data/raw/editable/  -> {editable_count} PDFs")
    print(f"  data/raw/scanned/   -> {scanned_count} PDFs")


if __name__ == "__main__":
    main()
