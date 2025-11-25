"""
Test Anexo pattern matching with various cases
"""
import re
import pdfplumber

pdf_path = r"C:\Users\Jason Cruz\OneDrive\Documentos\RA\CIUP\GitHub\FiscalTone\data\raw\editable\Opinion-MMM2023-2026-cNotaAclaratoria.pdf"

print("Testing Anexo pattern on Opinion-MMM2023-2026-cNotaAclaratoria")
print("="*80)

# Current pattern
current_pattern = r"(?mi)^ *Anexos?\b[\s\w]*:?"

# Test patterns
test_strings = [
    "Anexo",
    "Anexos",
    "ANEXO",
    "ANEXOS",
    "Anexo 1",
    "Anexos 2",
    "ANEXO 1",
    "ANEXOS 2",
    "Anexo I",
    "ANEXO I",
    "Anexo:",
    "ANEXO:",
    "ANEXO 1:",
    "Some text before\nAnexo\nMore text",
    "Some text before\nANEXO\nMore text",
    "Some text before\nANEXO 1\nMore text"
]

print("\nTesting current pattern:")
print(f"Pattern: {current_pattern}")
print()

for test in test_strings:
    match = re.search(current_pattern, test)
    status = "MATCH" if match else "NO MATCH"
    print(f"  {status}: '{test}'")

# Now check actual page 18
print("\n" + "="*80)
print("Checking actual page 18 content")
print("="*80)

try:
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) >= 18:
            page = pdf.pages[17]  # 0-indexed
            words = page.extract_words(extra_attrs=["size", "top"])

            # Get text (simulate extraction)
            text_words = [w.get("text", "") for w in words if 10.5 <= w.get("size", 0) <= 11.9]
            page_text = " ".join(text_words)

            print(f"\nFirst 300 chars of page 18:")
            print(page_text[:300])
            print()

            # Test current pattern
            match = re.search(current_pattern, page_text)
            if match:
                print(f"Current pattern MATCHED: '{match.group()}'")
                print(f"  Position: {match.start()}-{match.end()}")
            else:
                print("Current pattern DID NOT MATCH")

            # Look for "ANEXO" manually
            if "ANEXO" in page_text.upper():
                print(f"\nFound 'ANEXO' in text (case-insensitive)")
                # Find position
                upper_text = page_text.upper()
                pos = upper_text.find("ANEXO")
                context = page_text[max(0, pos-20):pos+30]
                print(f"  Context: '...{context}...'")
        else:
            print(f"PDF only has {len(pdf.pages)} pages")

except FileNotFoundError:
    print(f"File not found: {pdf_path}")
except Exception as e:
    print(f"Error: {e}")
