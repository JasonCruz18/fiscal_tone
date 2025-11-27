"""
Test final_robust_detector on all 13 PDFs and generate summary report
"""

from final_robust_detector import visualize_detection
from pdf2image import convert_from_path
from pathlib import Path
import json

def test_all_pdfs():
    """Test detector on all 13 scanned PDFs"""

    pdf_dir = Path("data/raw/scanned")
    output_dir = Path("final_robust_test_all")
    output_dir.mkdir(parents=True, exist_ok=True)

    # List all scanned PDFs
    pdf_files = sorted(pdf_dir.glob("*.pdf"))

    print(f"Found {len(pdf_files)} PDF files")
    print("="*80)

    all_results = []

    for pdf_path in pdf_files:
        print(f"\n{'='*80}")
        print(f"Testing: {pdf_path.name}")
        print('='*80)

        # Get page count
        images = convert_from_path(pdf_path, dpi=72)
        num_pages = len(images)

        pdf_results = {
            'filename': pdf_path.name,
            'total_pages': num_pages,
            'pages': []
        }

        # Process each page
        for page_num in range(1, num_pages + 1):
            try:
                info = visualize_detection(pdf_path, page_num, output_dir)

                page_result = {
                    'page': page_num,
                    'method': info['method'],
                    'confidence': info['confidence'],
                    'footer_y': info['footer_y'],
                    'footer_y_pct': info['footer_y'] / info['details'].get('cyan_zone_end', 1) if info['details'].get('cyan_zone_end') else 0,
                    'has_footnote': info['details'].get('has_footnote', False),
                    'cyan_zone_start_pct': info['details']['cyan_zone_start'] / 3508 * 100,  # Approximate
                    'cyan_zone_end_pct': info['details']['cyan_zone_end'] / 3508 * 100
                }

                pdf_results['pages'].append(page_result)

                print(f"  Page {page_num}: {info['method']}, Cyan: {page_result['cyan_zone_start_pct']:.1f}%-{page_result['cyan_zone_end_pct']:.1f}%, Footnote: {page_result['has_footnote']}")

            except Exception as e:
                print(f"  [ERROR] Page {page_num}: {str(e)}")
                pdf_results['pages'].append({
                    'page': page_num,
                    'error': str(e)
                })

        # Summary for this PDF
        footnote_count = sum(1 for p in pdf_results['pages'] if p.get('has_footnote', False))
        separator_count = sum(1 for p in pdf_results['pages'] if p.get('method') == 'separator_segment')

        print(f"\n  Summary: {num_pages} pages, {footnote_count} with footnotes, {separator_count} separators found")

        all_results.append(pdf_results)

    # Save full results to JSON
    results_file = output_dir / "test_results.json"
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*80}")
    print("OVERALL SUMMARY")
    print('='*80)

    total_pages = sum(r['total_pages'] for r in all_results)
    total_footnotes = sum(sum(1 for p in r['pages'] if p.get('has_footnote', False)) for r in all_results)
    total_separators = sum(sum(1 for p in r['pages'] if p.get('method') == 'separator_segment') for r in all_results)

    print(f"Total PDFs: {len(all_results)}")
    print(f"Total pages: {total_pages}")
    print(f"Pages with footnotes: {total_footnotes}")
    print(f"Pages with separator found: {total_separators}")
    print(f"Pages using cyan base: {total_pages - total_separators}")
    print(f"\nResults saved to: {results_file}")
    print(f"Visualizations saved to: {output_dir}/")


if __name__ == "__main__":
    test_all_pdfs()
