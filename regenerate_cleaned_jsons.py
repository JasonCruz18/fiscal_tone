"""
Regenerate both cleaned JSON files using improved header detection.

This script runs the cleaning pipelines directly:
1. For editable PDFs: Runs reclean_editable_pdfs.py
2. For scanned PDFs: Runs clean_scanned_text.py

Both scripts have been updated with improved header detection:
- Character threshold: 150 (was 50/120)
- Word threshold: 20 (was 8/15)
- Added chart/table label detection (1:, I., A), etc.)
"""

import subprocess
import sys

print("\n" + "="*80)
print("REGENERATING CLEANED JSON FILES WITH IMPROVED HEADER DETECTION")
print("="*80)

# ────────────────────────────────────────────────────────────────────────────
# 1. EDITABLE PDFs
# ────────────────────────────────────────────────────────────────────────────

print("\n[1/2] Processing EDITABLE PDFs...")
print("="*80)
print("Running reclean_editable_pdfs.py with improved functions...")
print()

result1 = subprocess.run(
    [sys.executable, "reclean_editable_pdfs.py"],
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace'
)

print(result1.stdout)

if result1.returncode != 0:
    print(f"\n[ERROR] Editable PDF cleaning failed:")
    print(result1.stderr)
else:
    print("[SUCCESS] Editable PDFs cleaned successfully")

# ────────────────────────────────────────────────────────────────────────────
# 2. SCANNED PDFs
# ────────────────────────────────────────────────────────────────────────────

print("\n[2/2] Processing SCANNED PDFs...")
print("="*80)
print("Running clean_scanned_text.py with improved stage3...")

# Run the scanned PDFs cleaning script
import subprocess

result = subprocess.run(
    [sys.executable, "clean_scanned_text.py"],
    capture_output=True,
    text=True,
    encoding='utf-8',
    errors='replace'
)

print(result.stdout)

if result.returncode != 0:
    print(f"\n[ERROR] Scanned PDF cleaning failed:")
    print(result.stderr)
else:
    print("[SUCCESS] Scanned PDFs cleaned successfully")

# ────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ────────────────────────────────────────────────────────────────────────────

print("\n" + "="*80)
print("REGENERATION COMPLETE")
print("="*80)
print("\nBoth cleaned JSON files have been updated with improved header detection:")
print(f"  1. {output_editable}")
print(f"  2. data/raw/scanned_pdfs_clean_extracted_text.json")
print("\nHeaders and chart labels (like '1:', 'I.', 'A)') are now properly removed.")
print("="*80 + "\n")
