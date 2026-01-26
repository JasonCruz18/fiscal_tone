"""
Semantic Paragraph Normalization for CF Opinion Corpus

This script normalizes paragraph lengths using sentence embeddings and
similarity-based splitting/merging to create optimal chunks for LLM classification.

Strategy:
- Split long paragraphs (>1000 chars) into semantically coherent chunks
- Merge short paragraphs (<200 chars) with similar neighbors
- Maintain medium paragraphs (400-700 chars) as-is
- Target range: 400-700 characters for optimal LLM context

Uses sentence-transformers for multilingual Spanish embeddings.

Author: Claude Code
Date: 2025-01-28
"""

import json
import sys
import io
from pathlib import Path
from typing import List, Dict, Tuple
import re
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Fix encoding for Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Try to import required libraries
try:
    from sentence_transformers import SentenceTransformer
    print("✓ sentence-transformers loaded")
except ImportError:
    print("ERROR: sentence-transformers not installed")
    print("Please install: pip install sentence-transformers")
    sys.exit(1)

try:
    import spacy
    print("✓ spacy loaded")
except ImportError:
    print("ERROR: spacy not installed")
    print("Please install: pip install spacy")
    print("Then download Spanish model: python -m spacy download es_core_news_sm")
    sys.exit(1)


class SemanticParagraphNormalizer:
    """
    Normalize paragraph lengths using semantic coherence.

    Uses sentence embeddings to split long paragraphs and merge short ones
    while maintaining semantic coherence.
    """

    def __init__(
        self,
        model_name: str = 'paraphrase-multilingual-MiniLM-L12-v2',
        min_length: int = 200,
        max_length: int = 1000,
        target_min: int = 400,
        target_max: int = 700
    ):
        """
        Initialize normalizer with embedding model and length thresholds.

        Args:
            model_name: Sentence transformer model (multilingual for Spanish)
            min_length: Paragraphs below this are candidates for merging
            max_length: Paragraphs above this are candidates for splitting
            target_min: Target minimum length after normalization
            target_max: Target maximum length after normalization
        """
        print(f"\n{'='*80}")
        print("INITIALIZING SEMANTIC PARAGRAPH NORMALIZER")
        print('='*80)

        print(f"\n📊 Length Thresholds:")
        print(f"  Min length (merge candidates):  {min_length} chars")
        print(f"  Max length (split candidates):  {max_length} chars")
        print(f"  Target range:                    {target_min}-{target_max} chars")

        # Load sentence transformer model
        print(f"\n🤖 Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        print("✓ Model loaded successfully")

        # Load spaCy for sentence tokenization
        print("\n📝 Loading spaCy Spanish model...")
        try:
            self.nlp = spacy.load('es_core_news_sm')
            print("✓ spaCy model loaded successfully")
        except:
            print("⚠ Spanish model not found. Installing...")
            import subprocess
            subprocess.run([sys.executable, '-m', 'spacy', 'download', 'es_core_news_sm'])
            self.nlp = spacy.load('es_core_news_sm')
            print("✓ spaCy model installed and loaded")

        self.min_length = min_length
        self.max_length = max_length
        self.target_min = target_min
        self.target_max = target_max

        print("\n✅ Normalizer initialized successfully")

    def split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences using spaCy.

        Args:
            text: Input text

        Returns:
            List of sentences
        """
        doc = self.nlp(text)
        sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
        return sentences

    def split_long_paragraph(self, paragraph: Dict) -> List[Dict]:
        """
        Split a long paragraph into semantically coherent chunks.

        Strategy:
        1. Split into sentences
        2. Generate embeddings for each sentence
        3. Group similar consecutive sentences
        4. Create chunks targeting optimal length

        Args:
            paragraph: Dictionary with 'text' and metadata

        Returns:
            List of new paragraph dictionaries
        """
        text = paragraph['text']

        # Split into sentences
        sentences = self.split_into_sentences(text)

        if len(sentences) <= 1:
            # Can't split further
            return [paragraph]

        # Generate embeddings
        embeddings = self.model.encode(sentences)

        # Calculate similarity between consecutive sentences
        similarities = []
        for i in range(len(sentences) - 1):
            sim = cosine_similarity([embeddings[i]], [embeddings[i+1]])[0][0]
            similarities.append(sim)

        # Find split points (low similarity = topic change)
        # Use adaptive threshold based on distribution
        if similarities:
            threshold = np.mean(similarities) - 0.5 * np.std(similarities)
            split_points = [i+1 for i, sim in enumerate(similarities) if sim < threshold]
        else:
            split_points = []

        # Add boundaries
        split_points = [0] + split_points + [len(sentences)]

        # Create chunks
        chunks = []
        for i in range(len(split_points) - 1):
            start = split_points[i]
            end = split_points[i + 1]
            chunk_sentences = sentences[start:end]
            chunk_text = ' '.join(chunk_sentences)

            # Only create chunk if it's not too small
            if len(chunk_text) >= self.min_length or i == len(split_points) - 2:
                chunks.append(chunk_text)

        # If chunking resulted in too many small pieces, merge them
        final_chunks = []
        current_chunk = ""

        for chunk in chunks:
            if not current_chunk:
                current_chunk = chunk
            elif len(current_chunk) + len(chunk) <= self.target_max:
                current_chunk += " " + chunk
            else:
                final_chunks.append(current_chunk)
                current_chunk = chunk

        if current_chunk:
            final_chunks.append(current_chunk)

        # Create new paragraph dictionaries
        result = []
        for i, chunk_text in enumerate(final_chunks):
            new_para = paragraph.copy()
            new_para['text'] = chunk_text
            new_para['length'] = len(chunk_text)
            new_para['normalized'] = True
            new_para['original_paragraph_num'] = paragraph['paragraph_num']
            new_para['chunk_index'] = i
            new_para['total_chunks'] = len(final_chunks)
            result.append(new_para)

        return result

    def should_merge_paragraphs(self, para1: Dict, para2: Dict, similarity_threshold: float = 0.7) -> bool:
        """
        Determine if two paragraphs should be merged based on semantic similarity.

        Args:
            para1: First paragraph
            para2: Second paragraph
            similarity_threshold: Minimum cosine similarity to merge

        Returns:
            True if paragraphs should be merged
        """
        # Check if they're from the same document
        if para1['pdf_filename'] != para2['pdf_filename']:
            return False

        # Check combined length
        combined_length = para1['length'] + para2['length']
        if combined_length > self.max_length:
            return False

        # Calculate semantic similarity
        emb1 = self.model.encode([para1['text']])[0]
        emb2 = self.model.encode([para2['text']])[0]
        similarity = cosine_similarity([emb1], [emb2])[0][0]

        return similarity >= similarity_threshold

    def merge_short_paragraphs(self, paragraphs: List[Dict]) -> List[Dict]:
        """
        Merge short paragraphs with semantically similar neighbors.

        Args:
            paragraphs: List of paragraph dictionaries

        Returns:
            List with merged paragraphs
        """
        result = []
        i = 0

        while i < len(paragraphs):
            current = paragraphs[i]

            # If current is short, try to merge
            if current['length'] < self.min_length and i + 1 < len(paragraphs):
                next_para = paragraphs[i + 1]

                # Check if should merge with next
                if self.should_merge_paragraphs(current, next_para):
                    # Merge
                    merged_text = current['text'] + " " + next_para['text']
                    merged = current.copy()
                    merged['text'] = merged_text
                    merged['length'] = len(merged_text)
                    merged['normalized'] = True
                    merged['merged_with'] = next_para['paragraph_num']
                    result.append(merged)
                    i += 2  # Skip next paragraph as it's been merged
                    continue

            # No merge, add as-is
            result.append(current)
            i += 1

        return result

    def normalize_corpus(self, paragraphs: List[Dict]) -> List[Dict]:
        """
        Normalize entire corpus using semantic splitting and merging.

        Args:
            paragraphs: List of paragraph dictionaries

        Returns:
            Normalized list of paragraphs
        """
        print(f"\n{'='*80}")
        print("NORMALIZING CORPUS")
        print('='*80)

        # Statistics
        original_count = len(paragraphs)
        split_count = 0
        merge_count = 0
        maintain_count = 0

        # Phase 1: Split long paragraphs
        print("\n📊 Phase 1: Splitting long paragraphs (>1000 chars)")
        phase1_result = []

        for i, para in enumerate(paragraphs):
            if i % 100 == 0:
                print(f"  Processing paragraph {i+1}/{len(paragraphs)}...", end='\r')

            if para['length'] > self.max_length:
                # Split
                chunks = self.split_long_paragraph(para)
                phase1_result.extend(chunks)
                split_count += 1
            else:
                # Keep as-is
                phase1_result.append(para)

        print(f"  ✓ Split {split_count} long paragraphs into {len(phase1_result)} chunks")

        # Phase 2: Merge short paragraphs
        print(f"\n📊 Phase 2: Merging short paragraphs (<{self.min_length} chars)")
        phase2_result = self.merge_short_paragraphs(phase1_result)
        merge_count = len(phase1_result) - len(phase2_result)
        print(f"  ✓ Merged {merge_count} paragraph pairs")

        # Count maintained paragraphs
        maintain_count = original_count - split_count - merge_count

        # Renumber paragraphs
        for i, para in enumerate(phase2_result, 1):
            para['paragraph_num'] = i

        # Print summary
        print(f"\n{'='*80}")
        print("NORMALIZATION SUMMARY")
        print('='*80)
        print(f"\nOriginal paragraphs:     {original_count:,}")
        print(f"Normalized paragraphs:   {len(phase2_result):,}")
        print(f"  - Split:               {split_count:,}")
        print(f"  - Merged:              {merge_count:,}")
        print(f"  - Maintained:          {maintain_count:,}")

        # Length statistics
        lengths = [p['length'] for p in phase2_result]
        print(f"\nLength statistics after normalization:")
        print(f"  Mean:    {np.mean(lengths):.0f} chars")
        print(f"  Median:  {np.median(lengths):.0f} chars")
        print(f"  Std:     {np.std(lengths):.0f} chars")
        print(f"  Min:     {min(lengths):,} chars")
        print(f"  Max:     {max(lengths):,} chars")

        # Distribution
        very_short = sum(1 for l in lengths if l < 200)
        short = sum(1 for l in lengths if 200 <= l < 400)
        medium = sum(1 for l in lengths if 400 <= l < 700)
        long = sum(1 for l in lengths if 700 <= l < 1000)
        very_long = sum(1 for l in lengths if l >= 1000)

        print(f"\nDistribution:")
        print(f"  Very short (<200):   {very_short:4d} ({very_short/len(lengths)*100:5.1f}%)")
        print(f"  Short (200-400):     {short:4d} ({short/len(lengths)*100:5.1f}%)")
        print(f"  Medium (400-700):    {medium:4d} ({medium/len(lengths)*100:5.1f}%)")
        print(f"  Long (700-1000):     {long:4d} ({long/len(lengths)*100:5.1f}%)")
        print(f"  Very long (1000+):   {very_long:4d} ({very_long/len(lengths)*100:5.1f}%)")

        target_range = sum(1 for l in lengths if self.target_min <= l <= self.target_max)
        print(f"\n🎯 Target range ({self.target_min}-{self.target_max}): {target_range:4d} ({target_range/len(lengths)*100:5.1f}%)")

        return phase2_result


def main():
    """Execute semantic normalization pipeline."""

    print('='*80)
    print(' SEMANTIC PARAGRAPH NORMALIZATION '.center(80, '='))
    print('='*80)
    print('\nThis script normalizes paragraph lengths using sentence embeddings')
    print('and similarity-based splitting/merging for optimal LLM input.')
    print('='*80)

    # Paths
    input_path = 'metadata/cf_comprehensive_metadata.json'
    output_path = 'metadata/cf_normalized_paragraphs.json'

    # Load data
    print(f"\n📂 Loading comprehensive metadata from: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"✅ Loaded {len(data):,} paragraphs")

    # Initialize normalizer
    normalizer = SemanticParagraphNormalizer(
        min_length=200,
        max_length=1000,
        target_min=400,
        target_max=700
    )

    # Normalize
    normalized = normalizer.normalize_corpus(data)

    # Save output
    print(f"\n{'='*80}")
    print("SAVING NORMALIZED CORPUS")
    print('='*80)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)

    file_size = output_file.stat().st_size
    print(f"\n✅ Normalized corpus saved to: {output_file}")
    print(f"   Size: {file_size:,} bytes ({file_size / 1024 / 1024:.2f} MB)")
    print(f"   Paragraphs: {len(normalized):,}")

    # Final message
    print(f"\n{'='*80}")
    print("NORMALIZATION COMPLETE")
    print('='*80)
    print("\n🎯 Corpus is now optimized for LLM classification!")
    print(f"   Ready for fiscal tone scoring (1-5 scale)")
    print('='*80)


if __name__ == '__main__':
    main()
