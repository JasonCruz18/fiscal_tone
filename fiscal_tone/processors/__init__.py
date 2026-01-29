"""
Document processors for FiscalTone.

This module provides PDF processing functionality including:
- PDF classification (editable vs scanned)
- Metadata enrichment
- Text extraction (font-based and OCR)
- Text cleaning and normalization
- Paragraph segmentation

Modules:
    pdf_classifier: PDF classification and metadata enrichment
    text_extractor: Text extraction from PDFs
    text_cleaner: Text cleaning pipeline
    paragraph_extractor: Paragraph segmentation (to be implemented)

Note:
    Imports are lazy to avoid requiring all dependencies at once.
    Import specific modules as needed:

    >>> from fiscal_tone.processors.text_cleaner import clean_text
"""

# Lazy imports to avoid dependency issues
# Users should import directly from submodules:
#   from fiscal_tone.processors.text_cleaner import clean_text
#   from fiscal_tone.processors.pdf_classifier import is_editable_pdf

__all__ = [
    # PDF Classification (requires PyMuPDF)
    "pdf_classifier",
    # Text Extraction (requires pdfplumber)
    "text_extractor",
    # Text Cleaning (no special dependencies)
    "text_cleaner",
]


def __getattr__(name: str):
    """Lazy import of submodules."""
    if name == "pdf_classifier":
        from fiscal_tone.processors import pdf_classifier
        return pdf_classifier
    elif name == "text_extractor":
        from fiscal_tone.processors import text_extractor
        return text_extractor
    elif name == "text_cleaner":
        from fiscal_tone.processors import text_cleaner
        return text_cleaner
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
