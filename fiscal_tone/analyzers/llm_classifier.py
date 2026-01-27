"""
LLM-based Fiscal Tone Classification.

This module provides GPT-4o based classification of fiscal policy text
into a 1-5 fiscal risk scale. It uses async/concurrent processing with
intelligent rate limiting.

Main Functions:
    classify_paragraph: Classify a single paragraph
    classify_paragraphs_batch: Classify multiple paragraphs concurrently
    run_classification: Complete classification pipeline

Key Features:
    - Full domain context for higher accuracy
    - Async processing with rate limiting (50 RPM)
    - Automatic backups during processing
    - Resume capability from backups

Example:
    >>> from fiscal_tone.analyzers.llm_classifier import run_classification_stage
    >>> import asyncio
    >>> asyncio.run(run_classification_stage())
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

import pandas as pd

from fiscal_tone.analyzers.prompt_templates import (
    build_classification_prompt,
    calculate_fiscal_tone_index,
)

# Check for optional dependencies
try:
    import aiolimiter
    from openai import AsyncOpenAI
    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )
    from tqdm.asyncio import tqdm as tqdm_asyncio

    HAS_LLM_DEPS = True
except ImportError:
    HAS_LLM_DEPS = False


# Default configuration
DEFAULT_MODEL = "gpt-4o"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 5
DEFAULT_REQUESTS_PER_MINUTE = 50
DEFAULT_BATCH_SIZE = 100


def _check_dependencies() -> None:
    """Check if LLM dependencies are installed."""
    if not HAS_LLM_DEPS:
        raise ImportError(
            "LLM dependencies not installed. Install with:\n"
            "  pip install openai aiolimiter tenacity tqdm"
        )


def _get_client() -> "AsyncOpenAI":
    """Get OpenAI async client."""
    _check_dependencies()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable not set.\n"
            "Set it with: export OPENAI_API_KEY='your-key-here'"
        )
    return AsyncOpenAI(api_key=api_key)


async def classify_paragraph(
    text: str,
    paragraph_id: int | str,
    client: "AsyncOpenAI",
    rate_limiter: "aiolimiter.AsyncLimiter",
    model: str = DEFAULT_MODEL,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    include_context: bool = True,
) -> int | None:
    """
    Classify a single paragraph using GPT-4o.

    Args:
        text: Paragraph text to classify.
        paragraph_id: Identifier for logging/debugging.
        client: AsyncOpenAI client instance.
        rate_limiter: Rate limiter for API calls.
        model: OpenAI model to use.
        temperature: Sampling temperature (0 = deterministic).
        max_tokens: Maximum tokens in response.
        include_context: Whether to include domain context.

    Returns:
        Fiscal risk score (1-5) or None if classification fails.
    """
    _check_dependencies()

    # Apply retry decorator dynamically
    @retry(
        retry=retry_if_exception_type((Exception,)),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def _classify() -> int | None:
        async with rate_limiter:
            try:
                prompt = build_classification_prompt(text, include_context)

                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

                result = response.choices[0].message.content.strip()

                if result in {"1", "2", "3", "4", "5"}:
                    return int(result)
                else:
                    print(f"[WARN] Paragraph {paragraph_id}: Unexpected '{result}'")
                    return None

            except Exception as e:
                print(f"[ERROR] Paragraph {paragraph_id}: {e}")
                raise

    return await _classify()


async def classify_paragraphs_batch(
    paragraphs: list[dict[str, Any]],
    client: "AsyncOpenAI",
    rate_limiter: "aiolimiter.AsyncLimiter",
    text_field: str = "text",
    id_field: str = "paragraph_num",
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """
    Classify a batch of paragraphs concurrently.

    Args:
        paragraphs: List of paragraph dictionaries.
        client: AsyncOpenAI client instance.
        rate_limiter: Rate limiter for API calls.
        text_field: Field name containing text to classify.
        id_field: Field name for paragraph identifier.
        **kwargs: Additional arguments passed to classify_paragraph.

    Returns:
        Updated paragraphs with fiscal_risk_score and risk_index.
    """
    _check_dependencies()

    # Create tasks for unclassified paragraphs
    tasks = []
    indices = []

    for i, para in enumerate(paragraphs):
        if para.get("fiscal_risk_score") is not None:
            continue  # Already classified

        task = classify_paragraph(
            text=para.get(text_field, ""),
            paragraph_id=para.get(id_field, i),
            client=client,
            rate_limiter=rate_limiter,
            **kwargs,
        )
        tasks.append(task)
        indices.append(i)

    if not tasks:
        print("[INFO] All paragraphs already classified")
        return paragraphs

    # Execute with progress bar
    print(f"\n[CLASSIFY] Processing {len(tasks)} paragraphs...")
    print(f"   Rate limit: {DEFAULT_REQUESTS_PER_MINUTE} requests/minute")

    results = []
    async for result in tqdm_asyncio(
        asyncio.as_completed(tasks),
        total=len(tasks),
        desc="Classifying",
    ):
        results.append(await result)

    # Update paragraphs with results
    for idx, score in zip(indices, results):
        paragraphs[idx]["fiscal_risk_score"] = score
        if score is not None:
            paragraphs[idx]["risk_index"] = calculate_fiscal_tone_index(score)

    return paragraphs


def save_backup(
    data: list[dict[str, Any]],
    output_dir: Path | str,
    prefix: str = "backup_llm",
) -> Path:
    """
    Save backup of classification progress.

    Args:
        data: List of paragraph dictionaries with scores.
        output_dir: Directory to save backup.
        prefix: Filename prefix.

    Returns:
        Path to saved backup file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_file = output_dir / f"{prefix}_{timestamp}_n{len(data)}.json"

    with open(backup_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[BACKUP] Saved: {backup_file}")
    return backup_file


def aggregate_scores(data: list[dict[str, Any]]) -> pd.DataFrame:
    """
    Aggregate paragraph-level scores to document-level statistics.

    Args:
        data: List of paragraph dictionaries with fiscal_risk_score.

    Returns:
        DataFrame with document-level metrics and score distributions.
    """
    df = pd.DataFrame(data)

    # Ensure date is datetime
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    # Aggregate by document
    agg_cols = {
        "fiscal_risk_score": ["mean", "count"],
        "risk_index": "mean",
    }

    # Add optional columns if present
    for col in ["doc_title", "doc_type", "doc_number", "year", "month"]:
        if col in df.columns:
            agg_cols[col] = "first"

    group_cols = ["pdf_filename"]
    if "date" in df.columns:
        group_cols.append("date")

    df_agg = df.groupby(group_cols).agg(agg_cols).reset_index()

    # Flatten column names
    df_agg.columns = [
        "_".join(col).strip("_") if isinstance(col, tuple) else col
        for col in df_agg.columns
    ]

    # Rename for clarity
    df_agg.rename(
        columns={
            "fiscal_risk_score_mean": "avg_risk_score",
            "fiscal_risk_score_count": "n_paragraphs",
            "risk_index_mean": "avg_risk_index",
        },
        inplace=True,
    )

    # Calculate fiscal tone index
    df_agg["fiscal_tone_index"] = df_agg["avg_risk_score"].apply(
        calculate_fiscal_tone_index
    )

    # Sort by date if available
    if "date" in df_agg.columns:
        df_agg = df_agg.sort_values("date").reset_index(drop=True)

    return df_agg


async def run_classification(
    input_path: str | Path = "metadata/cf_normalized_paragraphs_cleaned.json",
    output_dir: str | Path = "data/output",
    batch_size: int = DEFAULT_BATCH_SIZE,
    requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE,
) -> dict[str, Any]:
    """
    Run the complete LLM classification pipeline.

    Args:
        input_path: Path to input JSON with paragraphs.
        output_dir: Directory for output files.
        batch_size: Number of paragraphs per batch (for backups).
        requests_per_minute: API rate limit.

    Returns:
        Dictionary with results and statistics.
    """
    _check_dependencies()

    print("=" * 70)
    print("LLM CLASSIFICATION - GPT-4o WITH CONTEXT")
    print("=" * 70)

    # Initialize client and rate limiter
    client = _get_client()
    rate_limiter = aiolimiter.AsyncLimiter(
        max_rate=requests_per_minute,
        time_period=60,
    )

    # Load data
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n[LOAD] Loading: {input_path}")

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"[OK] Loaded {len(data):,} paragraphs")

    # Check for already classified
    already_done = sum(1 for p in data if p.get("fiscal_risk_score") is not None)
    if already_done > 0:
        print(f"[INFO] {already_done} already classified, {len(data) - already_done} remaining")

    # Start timer
    start_time = time.time()

    # Process in batches
    total_batches = (len(data) + batch_size - 1) // batch_size

    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(data))

        print(f"\n[BATCH {batch_num + 1}/{total_batches}] Paragraphs {start_idx + 1}-{end_idx}")

        batch = data[start_idx:end_idx]
        classified = await classify_paragraphs_batch(batch, client, rate_limiter)
        data[start_idx:end_idx] = classified

        # Save backup
        save_backup(data, output_dir)

    elapsed = time.time() - start_time

    # Save final outputs
    print(f"\n[SAVE] Saving outputs...")

    # Paragraph-level JSON
    para_json = output_dir / "llm_output_paragraphs_with_context.json"
    with open(para_json, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Paragraph-level CSV
    para_csv = output_dir / "llm_output_paragraphs_with_context.csv"
    pd.DataFrame(data).to_csv(para_csv, index=False, encoding="utf-8")

    # Document-level aggregation
    df_docs = aggregate_scores(data)

    doc_json = output_dir / "llm_output_documents_with_context.json"
    df_docs.to_json(doc_json, orient="records", indent=2, force_ascii=False)

    doc_csv = output_dir / "llm_output_documents_with_context.csv"
    df_docs.to_csv(doc_csv, index=False)

    print(f"[SAVED] {para_json}")
    print(f"[SAVED] {doc_json}")

    # Statistics
    df = pd.DataFrame(data)
    score_dist = df["fiscal_risk_score"].value_counts().sort_index()

    print(f"\n[STATS] Classification complete:")
    print(f"   Paragraphs: {len(data):,}")
    print(f"   Documents: {len(df_docs)}")
    print(f"   Time: {elapsed / 60:.1f} minutes")
    print(f"   Mean score: {df['fiscal_risk_score'].mean():.2f}")
    print(f"   Mean tone index: {df_docs['fiscal_tone_index'].mean():.3f}")

    return {
        "paragraphs": data,
        "documents": df_docs.to_dict("records"),
        "statistics": {
            "total_paragraphs": len(data),
            "total_documents": len(df_docs),
            "elapsed_seconds": elapsed,
            "score_distribution": score_dist.to_dict(),
        },
    }


def run_classification_stage(
    input_path: str | Path = "metadata/cf_normalized_paragraphs_cleaned.json",
    output_dir: str | Path = "data/output",
) -> dict[str, Any]:
    """
    Synchronous wrapper for run_classification.

    This is the entry point for the pipeline orchestrator.

    Args:
        input_path: Path to input JSON with paragraphs.
        output_dir: Directory for output files.

    Returns:
        Dictionary with results and statistics.
    """
    _check_dependencies()
    return asyncio.run(run_classification(input_path, output_dir))


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="LLM-based fiscal tone classification"
    )
    parser.add_argument(
        "--input",
        "-i",
        default="metadata/cf_normalized_paragraphs_cleaned.json",
        help="Input JSON file with paragraphs",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="data/output",
        help="Output directory",
    )
    parser.add_argument(
        "--rpm",
        type=int,
        default=DEFAULT_REQUESTS_PER_MINUTE,
        help=f"Requests per minute (default: {DEFAULT_REQUESTS_PER_MINUTE})",
    )

    args = parser.parse_args()

    asyncio.run(
        run_classification(
            input_path=args.input,
            output_dir=args.output,
            requests_per_minute=args.rpm,
        )
    )
