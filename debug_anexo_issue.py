import json

# Load data
with open('data/raw/scanned_pdfs_extracted_text.json', 'r', encoding='utf-8') as f:
    raw = json.load(f)

with open('data/raw/scanned_pdfs_clean_extracted_text.json', 'r', encoding='utf-8') as f:
    clean = json.load(f)

# Check 001-2018 PDF
print("="*80)
print("INFORME-N°-001-2018-CF.pdf - ANEXO ISSUE")
print("="*80)

# Find the PDF (try different encodings)
raw_pages = [p for p in raw if '001-2018' in p['pdf_filename']]
clean_pages = [p for p in clean if '001-2018' in p['pdf_filename']]

if raw_pages:
    pdf_name = raw_pages[0]['pdf_filename']
    print(f"PDF found: {pdf_name}")
    print(f"RAW pages: {len(raw_pages)}")
    print(f"CLEAN pages: {len(clean_pages)}")
    print(f"Clean page numbers: {sorted([p['page'] for p in clean_pages])}")

    # Check page 11
    p11_raw = [p for p in raw_pages if p['page'] == 11]
    if p11_raw:
        text = p11_raw[0]['text']
        idx = text.find('ANEXO')
        print(f"\nPage 11 (RAW):")
        print(f"  ANEXO position: {idx}")
        if idx >= 0:
            print(f"  Context: ...{text[max(0,idx-50):idx+150]}...")

    # Check if page 11 exists in clean
    p11_clean = [p for p in clean_pages if p['page'] == 11]
    if p11_clean:
        print(f"\nPage 11 (CLEAN): EXISTS - THIS IS THE PROBLEM!")
        print(f"  Text preview: {p11_clean[0]['text'][:200]}...")
    else:
        print(f"\nPage 11 (CLEAN): Correctly removed")
else:
    print("PDF not found!")

# Check PDFs without keywords
print("\n" + "="*80)
print("PDFs WITHOUT KEYWORDS")
print("="*80)

test_pdfs = ['001-2016', '002-2016']
for pdf_pattern in test_pdfs:
    raw_pages = [p for p in raw if pdf_pattern in p['pdf_filename']]
    clean_pages = [p for p in clean if pdf_pattern in p['pdf_filename']]

    if raw_pages:
        pdf_name = raw_pages[0]['pdf_filename']
        print(f"\n{pdf_name}:")
        print(f"  RAW: {len(raw_pages)} pages")
        print(f"  CLEAN: {len(clean_pages)} pages")
        if clean_pages:
            first_page = min([p['page'] for p in clean_pages])
            print(f"  First page in CLEAN: {first_page}")
            if first_page > 1:
                print(f"    -> PROBLEM: Should start from page 1!")
            else:
                print(f"    -> OK: Starts from page 1")
