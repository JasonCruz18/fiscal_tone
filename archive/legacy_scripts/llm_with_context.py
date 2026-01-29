"""
LLM Classification with Full Context - GPT-4o

Classifies CF opinion paragraphs with domain context for higher quality.
Uses async/concurrent processing with intelligent rate limiting.

Key improvements over llm_optimized.py:
- Includes full domain context (Peruvian fiscal policy background)
- Uses cleaned paragraphs (no truncated/malformed text)
- Better scoring consistency and accuracy

Author: Claude Code
Date: 2025-01-28
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

import aiolimiter
import pandas as pd
from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from tqdm.asyncio import tqdm as tqdm_asyncio

# ============================================================================
# CONFIGURATION
# ============================================================================

# Initialize async OpenAI client
client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Rate limiter: 50 requests per minute (respects TPM limit of 30,000)
# Your API tier: 500 RPM, 30,000 TPM (TPM is the bottleneck with long paragraphs + context)
# With ~600 tokens/request (context + paragraph), max throughput is ~50 RPM
rate_limiter = aiolimiter.AsyncLimiter(max_rate=50, time_period=60)

# Domain context for classification
CONTEXT = """
Sabemos que desde aproximadamente 2016 el manejo de las finanzas públicas ha mostrado signos crecientes de deterioro.
La pérdida de disciplina fiscal, la falta de transparencia y el relajamiento de las reglas fiscales han sido temas
recurrentes en las opiniones del Consejo Fiscal. A ello se suma el impacto de la inestabilidad política —con frecuentes cambios
ministeriales— sobre la capacidad institucional para llevar una política fiscal prudente y sostenible. En este contexto,
el Consejo Fiscal ha venido alertando con más frecuencia y firmeza sobre el incumplimiento de metas fiscales, el deterioro del
balance público, y los riesgos de un endeudamiento creciente y potencialmente insostenible.

Criterios comunes en los informes y comunicados del Consejo Fiscal (según categoría):

1. Cumplimiento y disciplina fiscal:
(disciplina fiscal, incumplimiento de metas fiscales, relajamiento de reglas fiscales, uso inadecuado del gasto público, desviación del déficit fiscal, deterioro del marco fiscal, flexibilización sin justificación, política fiscal procíclica)

2. Riesgo y sostenibilidad:
(riesgo fiscal, riesgo de sostenibilidad de la deuda, endeudamiento excesivo, dependencia de ingresos extraordinarios, vulnerabilidad fiscal estructural, uso de medidas transitorias o no permanentes, incertidumbre macrofiscal)

3. Gobernanza e institucionalidad:
(transparencia fiscal, calidad del gasto público, incertidumbre institucional, falta de planificación multianual, cambios frecuentes en autoridades económicas, debilitamiento institucional, independencia fiscal comprometida, ausencia de reforma estructural)
"""

# ============================================================================
# CLASSIFICATION FUNCTION
# ============================================================================

@retry(
    retry=retry_if_exception_type((Exception,)),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    stop=stop_after_attempt(5),
    reraise=True
)
async def classify_paragraph_with_retry(text: str, paragraph_num: int) -> Optional[int]:
    """
    Classify a paragraph using GPT-4o with domain context.

    Returns fiscal risk score (1-5) or None if classification fails.
    """
    async with rate_limiter:
        try:
            # Construct prompt with context
            prompt = f"""{CONTEXT}

Clasifica el siguiente párrafo según su grado de preocupación o alerta fiscal. Usa SOLO un número del 1 al 5:

1 = Sin preocupación fiscal (consolidación, cumplimiento, transparencia)
2 = Leve preocupación (riesgos potenciales, dependencia de ingresos extraordinarios)
3 = Neutral o técnico (descripción sin juicio de valor)
4 = Alta preocupación (incumplimiento, relajamiento fiscal, incertidumbre)
5 = Alarma fiscal (crítica severa, riesgo de sostenibilidad de deuda)

Párrafo:
\"\"\"{text}\"\"\"

Responde SOLO con un número (1, 2, 3, 4 o 5):"""

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
        start_idx: Starting index for progress display

    Returns:
        Updated paragraphs with fiscal_risk_score and risk_index
    """
    # Skip already classified paragraphs
    tasks = []
    for i, para in enumerate(paragraphs):
        if para.get('fiscal_risk_score') is not None:
            # Already classified - create dummy task
            tasks.append(asyncio.sleep(0))
            continue

        task = classify_paragraph_with_retry(
            text=para['text'],
            paragraph_num=para['paragraph_num']
        )
        tasks.append(task)

    # Execute all tasks concurrently with progress bar
    print(f"\n[CLASSIFYING] Classifying {len(paragraphs)} paragraphs with GPT-4o...")
    print(f"   Rate limit: 50 requests/minute (TPM-constrained with context)")
    print(f"   Estimated time: {len(paragraphs) / 50 * 60:.1f} seconds\n")

    results = []
    with tqdm_asyncio(total=len(tasks), desc="Progress") as pbar:
        for task in asyncio.as_completed(tasks):
            result = await task
            results.append(result)
            pbar.update(1)

    # Update paragraphs with results
    result_idx = 0
    for i, para in enumerate(paragraphs):
        if para.get('fiscal_risk_score') is None:
            score = results[result_idx]
            para['fiscal_risk_score'] = score
            if score is not None:
                # Calculate risk index: (3 - score) / 2
                para['risk_index'] = (3 - score) / 2
            result_idx += 1

    return paragraphs


def save_backup(data: List[Dict], batch_num: int):
    """Save backup after each batch."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_file = Path("data/output") / f"backup_context_fiscal_risk_{timestamp}_n{len(data)}.json"

    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[BACKUP] Backup saved: {backup_file}")


def aggregate_scores(data: List[Dict]) -> pd.DataFrame:
    """
    Aggregate paragraph-level scores to document-level statistics.

    Returns:
        DataFrame with document-level metrics and score distributions
    """
    df = pd.DataFrame(data)

    # Ensure date is datetime
    df['date'] = pd.to_datetime(df['date'], errors='coerce')

    # Aggregate by document
    df_doc_avg = df.groupby(['pdf_filename', 'date']).agg(
        avg_risk_score=('fiscal_risk_score', 'mean'),
        avg_risk_index=('risk_index', 'mean'),
        n_paragraphs=('fiscal_risk_score', 'count'),
        doc_title=('doc_title', 'first'),
        doc_type=('doc_type', 'first'),
        doc_number=('doc_number', 'first'),
        year=('year', 'first'),
        month=('month', 'first'),
    ).reset_index()

    # Score distribution (pivot table)
    df_score_dist = df.pivot_table(
        index=['pdf_filename', 'date'],
        columns='fiscal_risk_score',
        values='text',
        aggfunc='count',
        fill_value=0
    ).reset_index()

    # Rename columns
    score_cols = {}
    for col in df_score_dist.columns:
        if isinstance(col, (int, float)) and col in [1, 2, 3, 4, 5]:
            score_cols[col] = f'score_{int(col)}'
    df_score_dist.rename(columns=score_cols, inplace=True)

    # Ensure all score columns exist
    for score in [1, 2, 3, 4, 5]:
        col_name = f'score_{score}'
        if col_name not in df_score_dist.columns:
            df_score_dist[col_name] = 0

    # Merge aggregated stats with score distribution
    df_doc_summary = pd.merge(df_doc_avg, df_score_dist, on=['pdf_filename', 'date'])

    # Calculate fiscal tone index: (3 - avg_risk_score) / 2
    df_doc_summary['fiscal_tone_index'] = (3 - df_doc_summary['avg_risk_score']) / 2

    # Sort by date
    df_doc_summary = df_doc_summary.sort_values('date').reset_index(drop=True)

    return df_doc_summary


# ============================================================================
# MAIN EXECUTION
# ============================================================================

async def main():
    """Main execution flow."""
    print("="*80)
    print(" OPTIMIZED LLM CLASSIFICATION - GPT-4o WITH CONTEXT ".center(80, "="))
    print("="*80)
    print("\nThis script classifies CF opinion paragraphs using:")
    print("  - Model: gpt-4o (most capable OpenAI model)")
    print("  - Full domain context (Peruvian fiscal policy)")
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

    # Load cleaned normalized paragraphs
    input_path = "metadata/cf_normalized_paragraphs_cleaned.json"
    output_dir = Path("data/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[LOADING] Loading data from: {input_path}")

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"[OK] Loaded {len(data):,} cleaned paragraphs")

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

        print(f"\n{'='*80}")
        print(f"Batch {batch_num + 1}/{total_batches}: Paragraphs {start_idx + 1}-{end_idx}")
        print('='*80)

        batch = data[start_idx:end_idx]
        classified_batch = await classify_batch(batch, start_idx)

        # Update data with classified results
        data[start_idx:end_idx] = classified_batch

        # Save backup after each batch
        save_backup(data, batch_num + 1)

    # End timer
    elapsed = time.time() - start_time

    print(f"\n{'='*80}")
    print("CLASSIFICATION COMPLETE")
    print('='*80)
    print(f"[COMPLETE] Classified {len(data):,} paragraphs in {elapsed / 60:.1f} minutes")
    print(f"   Average: {elapsed / len(data):.2f} seconds per paragraph")
    print(f"   Throughput: {len(data) / (elapsed / 60):.0f} paragraphs/minute")

    # ========================================================================
    # SAVE OUTPUTS
    # ========================================================================

    print(f"\n{'='*80}")
    print("SAVING OUTPUTS")
    print('='*80)

    # Save paragraph-level results (JSON)
    output_json = output_dir / "llm_output_paragraphs_with_context.json"
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n[SAVED] Paragraph-level scores saved to:")
    print(f"   {output_json} ({output_json.stat().st_size / 1024 / 1024:.2f} MB)")

    # CSV output
    df = pd.DataFrame(data)
    output_csv = output_dir / "llm_output_paragraphs_with_context.csv"
    df.to_csv(output_csv, index=False, encoding='utf-8')

    print(f"   {output_csv} ({output_csv.stat().st_size / 1024 / 1024:.2f} MB)")

    # Aggregate by document
    print(f"\n[AGGREGATING] Aggregating scores by document...")
    df_doc_summary = aggregate_scores(data)

    # Save aggregated results
    output_agg_json = output_dir / "llm_output_documents_with_context.json"
    df_doc_summary.to_json(output_agg_json, orient='records', indent=2, force_ascii=False)

    output_agg_csv = output_dir / "llm_output_documents_with_context.csv"
    df_doc_summary.to_csv(output_agg_csv, index=False)

    print(f"\n[SAVED] Document-level aggregated scores saved to:")
    print(f"   {output_agg_json}")
    print(f"   {output_agg_csv}")

    # ========================================================================
    # PRINT STATISTICS
    # ========================================================================

    print(f"\n{'='*80}")
    print("CLASSIFICATION STATISTICS")
    print('='*80)

    # Score distribution
    score_counts = df['fiscal_risk_score'].value_counts().sort_index()
    print(f"\nParagraph-level distribution:")
    for score in [1, 2, 3, 4, 5]:
        count = score_counts.get(score, 0)
        pct = count / len(data) * 100
        print(f"  Score {score}:   {count:>4} paragraphs ({pct:>5.1f}%)")

    # Document-level stats
    print(f"\nDocument-level statistics:")
    print(f"  Total documents:     {len(df_doc_summary)}")
    print(f"  Mean risk score:     {df_doc_summary['avg_risk_score'].mean():.2f}")
    print(f"  Mean fiscal tone:    {df_doc_summary['fiscal_tone_index'].mean():.2f}")
    print(f"  Std dev risk score:  {df_doc_summary['avg_risk_score'].std():.2f}")

    # Cost estimation
    total_tokens = sum(len(p['text']) + len(CONTEXT) for p in data) // 4  # Rough estimate
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
    print(f"  1. Review: data/output/llm_output_paragraphs_with_context.csv")
    print(f"  2. Analyze: data/output/llm_output_documents_with_context.csv")
    print(f"  3. Visualize: Run your plotting code with the aggregated data")
    print('='*80)


if __name__ == "__main__":
    asyncio.run(main())
