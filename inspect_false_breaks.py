import json
import re

# Load cleaned data
with open('data/raw/scanned_pdfs_clean_extracted_text.json', 'r', encoding='utf-8') as f:
    clean = json.load(f)

print("Looking for \\n\\n before lowercase letters...")
print("="*80)

count = 0
for entry in clean:
    text = entry['text']
    # Find all occurrences of \n\n followed by lowercase
    matches = list(re.finditer(r'\n\n([a-záéíóúñü])', text))

    for match in matches:
        count += 1
        start = max(0, match.start() - 80)
        end = min(len(text), match.end() + 80)
        context = text[start:end]

        print(f"\nCase {count}: {entry['pdf_filename']} page {entry['page']}")
        print(f"Context: ...{context}...")
        print(f"Character before \\n\\n: '{text[match.start()-1]}'")
        print(f"Character after \\n\\n: '{match.group(1)}'")

        # Show the actual bytes
        snippet = text[match.start()-10:match.end()+10]
        print(f"Snippet: {repr(snippet)}")

print(f"\n{'='*80}")
print(f"Total false breaks found: {count}")
