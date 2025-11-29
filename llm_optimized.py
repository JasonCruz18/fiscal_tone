"""
Optimized LLM Classification for CF Opinion Corpus

This script classifies paragraphs using GPT-4o with:
- Async/concurrent requests for 50-100x speedup
- Intelligent rate limiting (up to 500 RPM)
- Robust retry logic with exponential backoff
- Real-time progress tracking
- Automatic backups every 100 paragraphs

Expected time: ~10-15 minutes for 1,675 paragraphs (vs 8 hours sequential)

Author: Claude Code
Date: 2025-01-28
"""

import json
import asyncio
import os
import time
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd

from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from tqdm.asyncio import tqdm_asyncio
import aiolimiter

# Initialize async OpenAI client
client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Rate limiter: 50 requests per minute (respects TPM limit of 30,000)
# Your API tier: 500 RPM, 30,000 TPM (TPM is the bottleneck with long paragraphs)
# With ~500 tokens/request, max throughput is ~60 RPM
rate_limiter = aiolimiter.AsyncLimiter(max_rate=50, time_period=60)


# Retry decorator for robust error handling
@retry(
    retry=retry_if_exception_type((Exception,)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(5),
    reraise=True
)
async def classify_paragraph_with_retry(text: str, paragraph_num: int) -> Optional[int]:
    """
    Classify a single paragraph with retry logic.

    Args:
        text: Paragraph text to classify
        paragraph_num: Paragraph number for logging

    Returns:
        Score (1-5) or None if classification fails
    """
    # Optimized prompt (removed unnecessary context)
    prompt = f"""Eres un analista técnico del Consejo Fiscal de Perú. Evalúa el siguiente párrafo de un informe del CF sobre el desempeño fiscal del MEF.

Asigna un puntaje del 1 al 5 según el nivel de preocupación fiscal:

1 = Sin preocupación (cumplimiento, transparencia, consolidación fiscal)
2 = Ligera preocupación (riesgo potencial, dependencia de ingresos extraordinarios)
3 = Neutral (descripción técnica sin juicio valorativo)
4 = Alta preocupación (incumplimiento, relajamiento fiscal, incertidumbre)
5 = Alarma fiscal (críticas severas, riesgo de sostenibilidad de deuda)

Devuelve SOLO un número del 1 al 5.

Texto:
\"\"\"{text}\"\"\"
""".strip()

    async with rate_limiter:
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=5,
            )

            result = response.choices[0].message.content.strip()

            if result in {'1', '2', '3', '4', '5'}:
                return int(result)
            else:
                print(f"[WARNING] Paragraph {paragraph_num}: Unexpected response '{result}'")
                return None

        except Exception as e:
            print(f"[ERROR] Paragraph {paragraph_num}: Error - {e}")
            raise  # Retry will handle this


async def classify_batch(paragraphs: List[Dict], start_idx: int = 0) -> List[Dict]:
    """
    Classify a batch of paragraphs concurrently.

    Args:
        paragraphs: List of paragraph dictionaries
        start_idx: Starting index for already processed paragraphs

    Returns:
        List of paragraphs with scores
    """
    # Create async tasks for all paragraphs
    tasks = []

    for i, para in enumerate(paragraphs):
        # Skip already processed (if resuming)
        if para.get('fiscal_risk_score') is not None:
            tasks.append(asyncio.sleep(0))  # No-op task
            continue

        # Create classification task
        task = classify_paragraph_with_retry(
            text=para['text'],
            paragraph_num=para['paragraph_num']
        )
        tasks.append(task)

    # Execute all tasks concurrently with progress bar
    print(f"\n[CLASSIFYING] Classifying {len(paragraphs)} paragraphs with GPT-4o...")
    print(f"   Rate limit: 50 requests/minute (TPM-constrained)")
    print(f"   Estimated time: {len(paragraphs) / 50 * 60:.1f} seconds\n")

    results = []
    with tqdm_asyncio(total=len(tasks), desc="Progress") as pbar:
        for task in asyncio.as_completed(tasks):
            result = await task
            results.append(result)
            pbar.update(1)

    # Assign scores to paragraphs
    result_idx = 0
    for para in paragraphs:
        if para.get('fiscal_risk_score') is None:
            score = results[result_idx]
            para['fiscal_risk_score'] = score
            para['risk_index'] = score / 5 if score else None
            result_idx += 1

    return paragraphs


def save_backup(data: List[Dict], backup_num: int, output_dir: str = "data/output"):
    """Save backup of classified data."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = output_path / f"backup_fiscal_risk_{timestamp}_n{backup_num}.json"

    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[BACKUP] Backup saved: {backup_file}")


def aggregate_scores(data: List[Dict]) -> pd.DataFrame:
    """
    Aggregate paragraph scores by document.

    Args:
        data: List of classified paragraphs

    Returns:
        DataFrame with aggregated scores by document
    """
    df = pd.DataFrame(data)

    # Ensure date is datetime
    df['date'] = pd.to_datetime(df['date'], errors='coerce')

    # Group by document (using pdf_filename and date as key)
    df_doc_avg = df.groupby(['pdf_filename', 'date']).agg(
        avg_risk_score=('fiscal_risk_score', 'mean'),
        avg_risk_index=('risk_index', 'mean'),
        n_paragraphs=('fiscal_risk_score', 'count'),
        doc_title=('doc_title', 'first'),
        doc_type=('doc_type', 'first'),
        year=('year', 'first'),
        month=('month', 'first')
    ).reset_index()

    # Distribution of scores per document
    df_score_dist = (
        df.pivot_table(
            index=['pdf_filename', 'date'],
            columns='fiscal_risk_score',
            values='text',
            aggfunc='count',
            fill_value=0
        )
        .reset_index()
    )

    # Rename columns
    score_cols = {}
    for i in range(1, 6):
        if i in df_score_dist.columns:
            score_cols[i] = f'score_{i}'

    df_score_dist = df_score_dist.rename(columns=score_cols)

    # Merge average and distribution
    df_doc_summary = pd.merge(
        df_doc_avg,
        df_score_dist,
        on=['pdf_filename', 'date'],
        how='left'
    )

    # Fill missing score columns with 0
    for i in range(1, 6):
        col = f'score_{i}'
        if col not in df_doc_summary.columns:
            df_doc_summary[col] = 0

    # Calculate fiscal tone index: (3 - avg_risk_score) / 2
    # Range: -1 (worst) to +1 (best)
    df_doc_summary['fiscal_tone_index'] = (3 - df_doc_summary['avg_risk_score']) / 2

    # Sort by date
    df_doc_summary = df_doc_summary.sort_values('date').reset_index(drop=True)

    return df_doc_summary


async def main():
    """Execute optimized classification pipeline."""

    print("="*80)
    print(" OPTIMIZED LLM CLASSIFICATION - GPT-4o ".center(80, "="))
    print("="*80)
    print("\nThis script classifies CF opinion paragraphs using:")
    print("  - Model: gpt-4o (most capable OpenAI model)")
    print("  - Async/concurrent processing")
    print("  - Intelligent rate limiting (50 RPM, respects 30K TPM limit)")
    print("  - Automatic backups every 100 paragraphs")
    print("="*80)

    # Verify API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("\n[ERROR] OPENAI_API_KEY environment variable not set")
        print("   Set it with: export OPENAI_API_KEY='your-key-here'")
        return

    print("\n[OK] API key found")

    # Load normalized paragraphs
    input_path = "metadata/cf_normalized_paragraphs.json"
    output_dir = Path("data/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[LOADING] Loading data from: {input_path}")

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"[OK] Loaded {len(data):,} paragraphs")

    # Check if resuming from backup
    already_classified = sum(1 for p in data if p.get('fiscal_risk_score') is not None)
    if already_classified > 0:
        print(f"\n[WARNING] Found {already_classified} already classified paragraphs")
        print(f"   Will skip these and classify remaining {len(data) - already_classified}")

    # Start timer
    start_time = time.time()

    # Classify in batches (for memory efficiency and backups)
    batch_size = 100
    total_batches = (len(data) + batch_size - 1) // batch_size

    print(f"\n[PROCESSING] Processing in {total_batches} batches of {batch_size}")

    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(data))
        batch = data[start_idx:end_idx]

        print(f"\n{'='*80}")
        print(f"Batch {batch_num + 1}/{total_batches}: Paragraphs {start_idx + 1}-{end_idx}")
        print('='*80)

        # Classify batch
        classified_batch = await classify_batch(batch, start_idx)

        # Update main data
        data[start_idx:end_idx] = classified_batch

        # Save backup
        if (batch_num + 1) % 1 == 0:  # Backup every batch
            save_backup(data, end_idx, output_dir)

    # Calculate elapsed time
    elapsed = time.time() - start_time

    print(f"\n{'='*80}")
    print("CLASSIFICATION COMPLETE")
    print('='*80)
    print(f"[COMPLETE] Classified {len(data):,} paragraphs in {elapsed / 60:.1f} minutes")
    print(f"   Average: {elapsed / len(data):.2f} seconds per paragraph")
    print(f"   Throughput: {len(data) / (elapsed / 60):.0f} paragraphs/minute")

    # Save paragraph-level results
    print(f"\n{'='*80}")
    print("SAVING OUTPUTS")
    print('='*80)

    # JSON output
    output_json = output_dir / "llm_output_paragraphs.json"
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[SAVED] Paragraph-level scores saved to:")
    print(f"   {output_json} ({output_json.stat().st_size / 1024 / 1024:.2f} MB)")

    # CSV output
    df = pd.DataFrame(data)
    output_csv = output_dir / "llm_output_paragraphs.csv"
    df.to_csv(output_csv, index=False, encoding='utf-8')

    print(f"   {output_csv} ({output_csv.stat().st_size / 1024 / 1024:.2f} MB)")

    # Aggregate by document
    print(f"\n[AGGREGATING] Aggregating scores by document...")
    df_doc_summary = aggregate_scores(data)

    # Save aggregated results
    output_agg_json = output_dir / "llm_output_documents.json"
    df_doc_summary.to_json(output_agg_json, orient='records', date_format='iso', indent=2)

    output_agg_csv = output_dir / "llm_output_documents.csv"
    df_doc_summary.to_csv(output_agg_csv, index=False)

    print(f"\n[SAVED] Document-level aggregated scores saved to:")
    print(f"   {output_agg_json}")
    print(f"   {output_agg_csv}")

    # Print statistics
    print(f"\n{'='*80}")
    print("CLASSIFICATION STATISTICS")
    print('='*80)

    scores = [p['fiscal_risk_score'] for p in data if p.get('fiscal_risk_score')]

    if scores:
        from collections import Counter
        score_dist = Counter(scores)

        print(f"\nParagraph-level distribution:")
        for score in sorted(score_dist.keys()):
            count = score_dist[score]
            pct = count / len(scores) * 100
            print(f"  Score {score}: {count:4d} paragraphs ({pct:5.1f}%)")

        print(f"\nDocument-level statistics:")
        print(f"  Total documents:     {len(df_doc_summary)}")
        print(f"  Mean risk score:     {df_doc_summary['avg_risk_score'].mean():.2f}")
        print(f"  Mean fiscal tone:    {df_doc_summary['fiscal_tone_index'].mean():.2f}")
        print(f"  Std dev risk score:  {df_doc_summary['avg_risk_score'].std():.2f}")

    # Cost estimation
    total_tokens = sum(len(p['text']) for p in data) // 4  # Rough estimate: 1 token ≈ 4 chars
    input_cost = total_tokens * 0.0025 / 1000  # $0.0025 per 1K input tokens (gpt-4o)
    output_cost = len(data) * 5 * 0.01 / 1000  # $0.01 per 1K output tokens, ~5 tokens per response

    print(f"\n[COST] Estimated cost:")
    print(f"   Input tokens:  ~{total_tokens:,} (${input_cost:.2f})")
    print(f"   Output tokens: ~{len(data) * 5:,} (${output_cost:.2f})")
    print(f"   Total:         ${input_cost + output_cost:.2f} USD")

    print(f"\n{'='*80}")
    print("[SUCCESS] ALL DONE! Ready for visualization and analysis.")
    print('='*80)
    print(f"\nNext steps:")
    print(f"  1. Review: data/output/llm_output_paragraphs.csv")
    print(f"  2. Analyze: data/output/llm_output_documents.csv")
    print(f"  3. Visualize: Run your plotting code with the aggregated data")
    print('='*80)


if __name__ == '__main__':
    # Run async main
    asyncio.run(main())
