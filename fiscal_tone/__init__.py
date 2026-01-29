"""
FiscalTone - Fiscal Policy Sentiment Analysis Pipeline.

A research pipeline for analyzing fiscal policy communications from
Peru's Fiscal Council (Consejo Fiscal) using LLM-based textual analysis.

The pipeline consists of the following stages:
    1. Collection: Web scraping and PDF download from cf.gob.pe
    2. Classification: Editable vs scanned PDF detection
    3. Extraction: Text extraction (font-based and OCR)
    4. Cleaning: Multi-stage text normalization
    5. Segmentation: Paragraph-level segmentation
    6. Analysis: LLM-based fiscal tone classification
    7. Visualization: Time-series analysis and reporting

Example:
    >>> from fiscal_tone.collectors import run_collection_stage
    >>> df = run_collection_stage(raw_pdf_folder="data/raw")

For CLI usage:
    $ python -m fiscal_tone.collectors.fc_collector --help
    $ python scripts/run_pipeline.py --all
"""

__version__ = "0.1.0"
__author__ = "Jason Cruz"
__email__ = ""

# Subpackage imports (lazy loading pattern)
from fiscal_tone import collectors

__all__ = [
    "__version__",
    "__author__",
    "collectors",
]
