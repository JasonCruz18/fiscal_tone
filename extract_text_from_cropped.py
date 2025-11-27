"""
Extract Text from Cropped Pages using Tesseract OCR

Processes all 93 cropped pages and extracts text for analysis
"""

import pytesseract
from PIL import Image
from pathlib import Path
import json
from tqdm import tqdm
import re


# Configure Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def extract_text_from_image(image_path, lang='spa'):
    """
    Extract text from image using Tesseract OCR

    Args:
        image_path: Path to cropped image
        lang: Language code (spa=Spanish, eng=English)

    Returns:
        Extracted text string
    """
    try:
        # Open image
        img = Image.open(image_path)

        # Extract text with Spanish language model
        # --psm 6: Assume uniform block of text
        # --oem 3: Use LSTM neural net mode
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(img, lang=lang, config=custom_config)

        return text.strip()

    except Exception as e:
        return f"[ERROR] {str(e)}"


def process_all_cropped_pages(cropped_dir="cropped_output/cropped_pages",
                               output_dir="extracted_text"):
    """
    Process all 93 cropped pages and extract text

    Saves:
    - Individual text files per page
    - Consolidated JSON with all extractions
    - Analysis report
    """
    cropped_dir = Path(cropped_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get all cropped images
    image_files = sorted(cropped_dir.glob("*_cropped.png"))

    print(f"\n{'='*80}")
    print(f"EXTRACTING TEXT FROM {len(image_files)} CROPPED PAGES")
    print('='*80)

    results = {}

    for img_path in tqdm(image_files, desc="Extracting", ncols=80):
        # Extract text
        text = extract_text_from_image(img_path, lang='spa')

        # Parse filename: "Informe-N°-001-2018-CF_page01_cropped.png"
        stem = img_path.stem.replace('_cropped', '')
        pdf_name = '_'.join(stem.split('_')[:-1])  # Remove page number
        page_num = stem.split('_')[-1].replace('page', '')

        # Save individual text file
        text_filename = f"{stem}.txt"
        text_path = output_dir / text_filename
        with open(text_path, 'w', encoding='utf-8') as f:
            f.write(text)

        # Store in results
        if pdf_name not in results:
            results[pdf_name] = {}

        results[pdf_name][int(page_num)] = {
            'image_file': img_path.name,
            'text_file': text_filename,
            'text': text,
            'char_count': len(text),
            'line_count': len(text.split('\n'))
        }

    # Save consolidated JSON
    json_path = output_dir / "all_extracted_text.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Generate analysis report
    print(f"\n{'='*80}")
    print("EXTRACTION SUMMARY")
    print('='*80)

    total_pages = sum(len(pages) for pages in results.values())
    total_chars = sum(
        page_data['char_count']
        for pdf_pages in results.values()
        for page_data in pdf_pages.values()
    )

    print(f"Total PDFs: {len(results)}")
    print(f"Total pages: {total_pages}")
    print(f"Total characters extracted: {total_chars:,}")
    print(f"Average chars per page: {total_chars // total_pages:,}")

    print(f"\nOutputs:")
    print(f"  Text files: {output_dir}/ ({total_pages} files)")
    print(f"  JSON: {json_path}")

    print('='*80)

    return results


def analyze_footnote_patterns(results):
    """
    Analyze extracted text to identify footnote patterns

    This will help us design the most robust cleaning strategy
    """
    print(f"\n{'='*80}")
    print("ANALYZING FOOTNOTE PATTERNS")
    print('='*80)

    # Patterns to look for
    superscript_pattern = r'[¹²³⁴⁵⁶⁷⁸⁹⁰]+'
    law_pattern = r'Ley N[°º]\s*\d+'
    decree_pattern = r'Decreto [Ll]egislativo N[°º]\s*\d+'
    article_pattern = r'Art[ií]culo \d+'
    address_pattern = r'Av\.\s*Contralmirante\s*Montero'

    findings = {
        'superscripts': [],
        'laws': [],
        'decrees': [],
        'articles': [],
        'addresses': [],
        'common_phrases': {}
    }

    for pdf_name, pages in results.items():
        for page_num, page_data in pages.items():
            text = page_data['text']
            lines = text.split('\n')

            # Check for superscripts
            for i, line in enumerate(lines):
                if re.search(superscript_pattern, line):
                    findings['superscripts'].append({
                        'pdf': pdf_name,
                        'page': page_num,
                        'line_num': i,
                        'line': line[:100]  # First 100 chars
                    })

            # Check for laws
            if re.search(law_pattern, text):
                findings['laws'].append({
                    'pdf': pdf_name,
                    'page': page_num,
                    'count': len(re.findall(law_pattern, text))
                })

            # Check for decrees
            if re.search(decree_pattern, text):
                findings['decrees'].append({
                    'pdf': pdf_name,
                    'page': page_num,
                    'count': len(re.findall(decree_pattern, text))
                })

            # Check for articles
            if re.search(article_pattern, text):
                findings['articles'].append({
                    'pdf': pdf_name,
                    'page': page_num,
                    'count': len(re.findall(article_pattern, text))
                })

            # Check for address
            if re.search(address_pattern, text, re.IGNORECASE):
                findings['addresses'].append({
                    'pdf': pdf_name,
                    'page': page_num
                })

    # Print findings
    print(f"\nSuperscripts found: {len(findings['superscripts'])} occurrences")
    if findings['superscripts'][:3]:
        print("  Sample lines:")
        for item in findings['superscripts'][:3]:
            print(f"    [{item['pdf']}_p{item['page']}] {item['line']}")

    print(f"\nLaw references: {len(findings['laws'])} pages")
    print(f"Decree references: {len(findings['decrees'])} pages")
    print(f"Article references: {len(findings['articles'])} pages")
    print(f"Address found: {len(findings['addresses'])} pages")

    # Save analysis
    analysis_path = Path("extracted_text/footnote_analysis.json")
    with open(analysis_path, 'w', encoding='utf-8') as f:
        json.dump(findings, f, indent=2, ensure_ascii=False)

    print(f"\nAnalysis saved to: {analysis_path}")
    print('='*80)

    return findings


if __name__ == "__main__":
    # Extract text from all pages
    results = process_all_cropped_pages()

    # Analyze patterns
    patterns = analyze_footnote_patterns(results)

    print("\n[DONE] Text extraction and analysis complete!")
    print("Next step: Review patterns and design cleaning strategy")
