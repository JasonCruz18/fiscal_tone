"""
Paragraph Segmentation for Cleaned Text

3-stage segmentation:
1. Merge paragraphs split across pages
2. Split by \\n\\n (natural segmentation)
3. Normalize paragraph length (semantic segmentation)
4. Remove duplicates (optional)

Output: Unified JSON with paragraph_num column
"""

import json
import re
from pathlib import Path
from tqdm import tqdm
import hashlib


def stage1_merge_split_paragraphs(data):
    """
    Stage 1: Merge paragraphs split across pages

    Rules:
    - If page N ends without period → likely continues on page N+1
    - If page N+1 doesn't start with \\n\\n → it's continuation

    Returns:
        Data with merged cross-page paragraphs
    """
    # Group by PDF
    pdf_groups = {}
    for entry in data:
        pdf = entry['pdf_filename']
        if pdf not in pdf_groups:
            pdf_groups[pdf] = []
        pdf_groups[pdf].append(entry)

    merged_data = []
    total_merges = 0

    for pdf_name, pages in pdf_groups.items():
        # Sort by page
        pages = sorted(pages, key=lambda x: x['page'])

        for i, page in enumerate(pages):
            text = page['text']

            # Check if this page's text should be merged with previous
            if i > 0 and 'merged_with_next' in pages[i-1]:
                # This page was already merged into previous, skip
                continue

            # Check if should merge with next page
            if i < len(pages) - 1:
                next_page = pages[i + 1]
                next_text = next_page['text']

                # Rule 1: Current page ends without period
                ends_without_period = not text.rstrip().endswith(('.', '!', '?', ':'))

                # Rule 2: Next page doesn't start with \\n\\n (is continuation)
                next_starts_continuation = not next_text.startswith('\\n\\n')

                if ends_without_period or next_starts_continuation:
                    # Merge next page into current
                    page['text'] = text.rstrip() + ' ' + next_text.lstrip()
                    page['merged_with_next'] = True
                    pages[i+1]['merged_into_previous'] = True
                    total_merges += 1

            # Add to merged data if not merged into previous
            if 'merged_into_previous' not in page:
                merged_data.append(page)

    print(f"  Stage 1: Merged {total_merges} cross-page paragraph splits")
    return merged_data


def stage2_split_by_paragraphs(data):
    """
    Stage 2: Split text by \n\n into individual paragraphs

    Each paragraph becomes a separate entry with paragraph_num.

    Returns:
        List of paragraph entries with pdf_filename, page, paragraph_num, text
    """
    paragraph_entries = []
    total_paragraphs = 0

    for entry in data:
        pdf = entry['pdf_filename']
        page = entry['page']
        text = entry['text']

        # Split by \n\n (double newline)
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        # Create entry for each paragraph
        for para_idx, para_text in enumerate(paragraphs, start=1):
            paragraph_entries.append({
                'pdf_filename': pdf,
                'page': page,
                'paragraph_num': para_idx,
                'text': para_text,
                'char_length': len(para_text),
                'word_count': len(para_text.split())
            })
            total_paragraphs += 1

    print(f"  Stage 2: Created {total_paragraphs} paragraphs from {len(data)} pages")
    return paragraph_entries


def stage3_normalize_paragraph_length(data, target_tokens=150, min_tokens=80, max_tokens=250):
    """
    Stage 3: Normalize paragraph length using semantic segmentation

    Combines very short paragraphs and splits very long paragraphs.

    Strategy:
    - Short paragraphs (<min_tokens): Merge with next if semantically coherent
    - Long paragraphs (>max_tokens): Split at sentence boundaries, avoiding connectors

    Args:
        data: List of paragraph entries
        target_tokens: Target average tokens per paragraph
        min_tokens: Minimum tokens (merge if below)
        max_tokens: Maximum tokens (split if above)

    Returns:
        Normalized paragraph list
    """
    # TODO: This is complex and requires careful implementation
    # For now, return data as-is
    # In production, implement smart merging/splitting

    normalized = []
    merges = 0
    splits = 0

    # Connectors to avoid splitting at
    connectors = [
        'Sin embargo', 'No obstante', 'Por otro lado', 'Asimismo',
        'Además', 'Por lo tanto', 'En consecuencia', 'De esta manera',
        'Por otra parte', 'En este sentido', 'Cabe mencionar'
    ]

    for entry in data:
        tokens = entry['word_count']
        text = entry['text']

        if tokens < min_tokens:
            # Too short - would merge with next, but keep for now
            normalized.append(entry)
        elif tokens > max_tokens:
            # Too long - split at sentence boundaries
            sentences = re.split(r'(?<=[.!?])\\s+', text)

            current_chunk = []
            current_tokens = 0

            for sent in sentences:
                sent_tokens = len(sent.split())

                # Check if sentence starts with connector
                starts_with_connector = any(sent.startswith(conn) for conn in connectors)

                if current_tokens + sent_tokens > max_tokens and current_chunk and not starts_with_connector:
                    # Save current chunk
                    chunk_text = ' '.join(current_chunk)
                    normalized.append({
                        **entry,
                        'text': chunk_text,
                        'char_length': len(chunk_text),
                        'word_count': len(chunk_text.split())
                    })
                    splits += 1

                    # Start new chunk
                    current_chunk = [sent]
                    current_tokens = sent_tokens
                else:
                    current_chunk.append(sent)
                    current_tokens += sent_tokens

            # Add final chunk
            if current_chunk:
                chunk_text = ' '.join(current_chunk)
                normalized.append({
                    **entry,
                    'text': chunk_text,
                    'char_length': len(chunk_text),
                    'word_count': len(chunk_text.split())
                })
        else:
            # Good length - keep as is
            normalized.append(entry)

    print(f"  Stage 3: Normalized lengths - {splits} paragraphs split")
    return normalized


def stage4_remove_duplicates(data, similarity_threshold=0.95):
    """
    Stage 4: Remove duplicate paragraphs (optional)

    Uses text hash to detect exact duplicates.
    Could be extended to use fuzzy matching for near-duplicates.

    Returns:
        Deduplicated data
    """
    seen_hashes = set()
    deduplicated = []
    duplicates_removed = 0

    for entry in data:
        text = entry['text']

        # Create hash of normalized text
        normalized_text = re.sub(r'\\s+', ' ', text.lower().strip())
        text_hash = hashlib.md5(normalized_text.encode()).hexdigest()

        if text_hash not in seen_hashes:
            seen_hashes.add(text_hash)
            deduplicated.append(entry)
        else:
            duplicates_removed += 1

    print(f"  Stage 4: Removed {duplicates_removed} duplicate paragraphs")
    return deduplicated


def segment_paragraphs(scanned_json="data/raw/scanned_pdfs_clean_extracted_text.json",
                       editable_json="data/raw/editable_pdfs_clean_extracted_text.json",
                       output_json="data/raw/unified_paragraphs_segmented.json",
                       merge_split=True,
                       normalize_length=True,
                       remove_duplicates=True):
    """
    Segment and normalize paragraphs from both scanned and editable PDFs

    Pipeline:
    1. Merge paragraphs split across pages
    2. Split by \\n\\n into individual paragraphs
    3. Normalize paragraph length (semantic)
    4. Remove duplicates

    Args:
        scanned_json: Cleaned scanned PDFs text
        editable_json: Cleaned editable PDFs text
        output_json: Unified output with paragraphs
        merge_split: Enable stage 1
        normalize_length: Enable stage 3
        remove_duplicates: Enable stage 4

    Returns:
        Segmented paragraph data
    """
    scanned_json = Path(scanned_json)
    editable_json = Path(editable_json)
    output_json = Path(output_json)

    print(f"\\n{'='*80}")
    print("PARAGRAPH SEGMENTATION")
    print('='*80)
    print(f"Scanned JSON: {scanned_json}")
    print(f"Editable JSON: {editable_json}")
    print(f"Output JSON: {output_json}")
    print(f"\\nStages:")
    print(f"  1. Merge split paragraphs: {merge_split}")
    print(f"  2. Split by \\\\n\\\\n: Always enabled")
    print(f"  3. Normalize length: {normalize_length}")
    print(f"  4. Remove duplicates: {remove_duplicates}")
    print('='*80)

    # Load data
    with open(scanned_json, 'r', encoding='utf-8') as f:
        scanned_data = json.load(f)

    with open(editable_json, 'r', encoding='utf-8') as f:
        editable_data = json.load(f)

    # Combine data
    all_data = scanned_data + editable_data
    print(f"\\nTotal pages: {len(all_data)} ({len(scanned_data)} scanned + {len(editable_data)} editable)")

    # Stage 1: Merge split paragraphs
    if merge_split:
        all_data = stage1_merge_split_paragraphs(all_data)

    # Stage 2: Split by paragraphs (always enabled)
    print(f"\\nApplying segmentation stages...")
    paragraphs = stage2_split_by_paragraphs(all_data)

    # Stage 3: Normalize length
    if normalize_length:
        paragraphs = stage3_normalize_paragraph_length(paragraphs)

    # Stage 4: Remove duplicates
    if remove_duplicates:
        paragraphs = stage4_remove_duplicates(paragraphs)

    # Save output
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(paragraphs, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"\\n{'='*80}")
    print("SEGMENTATION COMPLETE")
    print('='*80)
    print(f"Total paragraphs: {len(paragraphs)}")
    print(f"Average length: {sum(p['char_length'] for p in paragraphs) / len(paragraphs):.0f} chars")
    print(f"Average words: {sum(p['word_count'] for p in paragraphs) / len(paragraphs):.0f} words")

    # Length distribution
    lengths = [p['word_count'] for p in paragraphs]
    print(f"\\nWord count distribution:")
    print(f"  Min: {min(lengths)}")
    print(f"  Max: {max(lengths)}")
    print(f"  Median: {sorted(lengths)[len(lengths)//2]}")

    print(f"\\nOutput saved to: {output_json}")
    print('='*80)

    return paragraphs


if __name__ == "__main__":
    segment_paragraphs(
        scanned_json="data/raw/scanned_pdfs_clean_extracted_text.json",
        editable_json="data/raw/editable_pdfs_clean_extracted_text.json",
        output_json="data/raw/unified_paragraphs_segmented.json",
        merge_split=True,
        normalize_length=True,
        remove_duplicates=True
    )
