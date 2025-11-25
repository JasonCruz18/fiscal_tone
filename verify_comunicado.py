"""
Verify Comunicado042024-VF JSON file contents
"""
import json
import os

json_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Comunicado042024-VF_v2.json"

if os.path.exists(json_path):
    # Get file info
    import time
    mod_time = os.path.getmtime(json_path)
    mod_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mod_time))
    size = os.path.getsize(json_path)

    print("="*80)
    print("COMUNICADO042024-VF JSON FILE VERIFICATION")
    print("="*80)
    print(f"File: {os.path.basename(json_path)}")
    print(f"Modified: {mod_time_str}")
    print(f"Size: {size:,} bytes")
    print()

    # Read JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Analyze pages
    pages = [r['page'] for r in data]
    print(f"Total records: {len(data)}")
    print(f"Pages extracted: {pages}")
    print(f"First page: {pages[0]}")
    print(f"Last page: {pages[-1]}")
    print()

    # Show first few lines of each page
    for i, record in enumerate(data):
        page = record['page']
        text = record['text']
        lines = text.split('\n')
        first_line = lines[0][:100] if lines else ""
        print(f"Page {page}: {first_line}...")
        if i >= 2:  # Show first 3 pages
            print(f"   ... (and {len(data) - 3} more pages)")
            break

    print()
    if pages == [1, 2, 3, 4, 5]:
        print("✓ CORRECT: Extracted pages 1-5 (keyword not found, started from beginning)")
    elif pages == [4, 5]:
        print("✗ INCORRECT: Only extracted pages 4-5 (false positive keyword match)")
        print("   This means the case-sensitive fix is NOT applied!")
    else:
        print(f"? UNEXPECTED: Got pages {pages}")
else:
    print(f"JSON file not found: {json_path}")
    print("\nPlease run: python debug_comunicado_detailed.py")
