"""
Document collectors for FiscalTone.

This module provides web scraping and document download functionality
for collecting fiscal policy documents from government sources.

Modules:
    fc_collector: Peru's Fiscal Council (Consejo Fiscal) document collector
"""

from fiscal_tone.collectors.fc_collector import (
    extract_pdf_links,
    is_presentation_pdf,
    pdf_downloader,
    remove_unwanted_pdfs,
    run_collection_stage,
    scrape_cf,
    select_appropriate_pdf,
)

__all__ = [
    "is_presentation_pdf",
    "extract_pdf_links",
    "select_appropriate_pdf",
    "scrape_cf",
    "pdf_downloader",
    "remove_unwanted_pdfs",
    "run_collection_stage",
]
