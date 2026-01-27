"""
Debug script to see exactly what stage6 is removing
"""
import json
import re
from pathlib import Path

# Load data after stage5 (before stage6)
# We'll simulate stage6 to see what it removes

def load_and_process():
    """Load scanned PDFs and process through stage 0-5, then show stage6 removals"""

    # For simplicity, let's just load the current cleaned file and check what WOULD be removed
    # by the current stage6 logic

    input_file = Path('data/raw/scanned_pdfs_extracted_text.json')

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("\n" + "="*80)
    print("ANALYZING STAGE6 REMOVALS")
    print("="*80)

    total_removed = 0
    removals_by_reason = {
        'too_short': [],
        'pattern_match': [],
        'all_caps': []
    }

    for entry in data:
        text = entry['text']
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        for para in paragraphs:
            should_remove = False
            reason = None

            # Check patterns (only on SHORT paragraphs < 100 chars)
            if len(para) < 100:
                removal_patterns_short = [
                    r'^Informe\s+N[*°º]?\s*\d',
                    r'^CF[-\s]*\d',
                    r'^Lima,\s+\d+\s+de\s+\w+\s+de\s+\d{4}',
                    r'^\d+\s*/\s*\d+$',
                    r'^Presidente.*Consejo Fiscal$',
                    r'^Conclusiones?\s*:?$',
                    r'^Esquema\s+[Ff]iscal$',
                    r'^Consejo\s+Fiscal\s*:?$',
                ]

                for pattern in removal_patterns_short:
                    if re.search(pattern, para, re.IGNORECASE):
                        should_remove = True
                        reason = f'pattern_match: {pattern}'
                        removals_by_reason['pattern_match'].append({
                            'pdf': entry['pdf_filename'],
                            'page': entry['page'],
                            'text': para,
                            'pattern': pattern,
                            'length': len(para)
                        })
                        break

            # Too short
            if len(para) < 50:
                should_remove = True
                reason = 'too_short'
                removals_by_reason['too_short'].append({
                    'pdf': entry['pdf_filename'],
                    'page': entry['page'],
                    'text': para,
                    'length': len(para)
                })

            # All-caps names (only in SHORT paragraphs)
            if len(para) < 100 and not should_remove:
                alpha = [c for c in para if c.isalpha()]
                if alpha:
                    if sum(1 for c in alpha if c.isupper()) / len(alpha) > 0.5:
                        should_remove = True
                        reason = 'all_caps'
                        removals_by_reason['all_caps'].append({
                            'pdf': entry['pdf_filename'],
                            'page': entry['page'],
                            'text': para,
                            'length': len(para),
                            'caps_ratio': sum(1 for c in alpha if c.isupper()) / len(alpha)
                        })

            if should_remove:
                total_removed += 1

    # Print results
    print(f"\nTotal paragraphs to be removed: {total_removed}")
    print("\n" + "-"*80)
    print("BREAKDOWN BY REASON:")
    print("-"*80)

    print(f"\n1. TOO SHORT (< 50 chars): {len(removals_by_reason['too_short'])} paragraphs")
    if removals_by_reason['too_short']:
        print("\nExamples:")
        for i, item in enumerate(removals_by_reason['too_short'][:10], 1):
            print(f"\n  [{i}] {item['pdf']}, page {item['page']} ({item['length']} chars)")
            print(f"      Text: '{item['text']}'")

    print(f"\n2. PATTERN MATCH: {len(removals_by_reason['pattern_match'])} paragraphs")
    if removals_by_reason['pattern_match']:
        print("\nExamples:")
        for i, item in enumerate(removals_by_reason['pattern_match'][:10], 1):
            print(f"\n  [{i}] {item['pdf']}, page {item['page']} ({item['length']} chars)")
            print(f"      Pattern: {item['pattern']}")
            print(f"      Text: '{item['text']}'")

    print(f"\n3. ALL CAPS: {len(removals_by_reason['all_caps'])} paragraphs")
    if removals_by_reason['all_caps']:
        print("\nExamples:")
        for i, item in enumerate(removals_by_reason['all_caps'][:10], 1):
            print(f"\n  [{i}] {item['pdf']}, page {item['page']} ({item['length']} chars)")
            print(f"      Caps ratio: {item['caps_ratio']:.2%}")
            print(f"      Text: '{item['text']}'")

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)

    # Check if any long paragraphs are being removed (would be a problem)
    long_removed = [item for reason_list in removals_by_reason.values()
                    for item in reason_list if item.get('length', 0) > 100]

    if long_removed:
        print(f"\n⚠️  WARNING: {len(long_removed)} paragraphs > 100 chars are being removed!")
        print("These might be valid content:")
        for i, item in enumerate(long_removed[:5], 1):
            print(f"\n  [{i}] {item['pdf']}, page {item['page']} ({item.get('length')} chars)")
            print(f"      Text: '{item.get('text', '')[:200]}...'")
    else:
        print("\n✅ All removed paragraphs are < 100 chars (likely noise)")

    print()

if __name__ == "__main__":
    load_and_process()
