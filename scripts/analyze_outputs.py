"""
Output Analysis and Comparison Script for FiscalTone.

Reads FT0.xlsx (reference/submitted paper data) and the current LLM outputs,
computes derived metrics (score shares, CMA), and generates comparison plots.

Usage:
    python scripts/analyze_outputs.py
    python scripts/analyze_outputs.py --save-fig
    python scripts/analyze_outputs.py --cma-window 5
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths (relative to project root)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent

FT0_PATH = ROOT / "Fiscal_ToneAEL" / "FT0.xlsx"
WITH_CTX_PATH = ROOT / "data" / "output" / "llm_output_documents_with_context.json"
NO_CTX_PATH = ROOT / "data" / "output" / "llm_output_documents.json"
FIG_OUTPUT = ROOT / "data" / "output" / "fiscal_tone_comparison.png"
COMPARISON_CSV = ROOT / "data" / "output" / "ft0_comparison.csv"


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_ft0() -> pd.DataFrame:
    """Load the FT0.xlsx reference data."""
    df = pd.read_excel(FT0_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def load_llm_json(path: Path, ts_milliseconds: bool = False) -> pd.DataFrame:
    """Load an LLM output JSON file into a DataFrame."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    if ts_milliseconds:
        df["date"] = pd.to_datetime(df["date"], unit="ms")
    else:
        df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Derived metrics
# ---------------------------------------------------------------------------

def add_score_shares(df: pd.DataFrame) -> pd.DataFrame:
    """Convert raw score counts to shares (fractions)."""
    df = df.copy()
    for i in range(1, 6):
        col = f"score_{i}"
        if col in df.columns:
            df[f"score_{i}_share"] = df[col] / df["n_paragraphs"]
    return df


def add_cma(df: pd.DataFrame, col: str, window: int = 5) -> pd.DataFrame:
    """Add a centered moving average column."""
    df = df.copy()
    df[f"{col}_cma"] = (
        df[col]
        .rolling(window=window, center=True, min_periods=max(1, window // 2))
        .mean()
    )
    return df


def add_fiscal_tone_index(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure fiscal_tone_index column exists using formula (3 - avg_risk_score) / 2."""
    df = df.copy()
    if "fiscal_tone_index" not in df.columns:
        df["fiscal_tone_index"] = (3 - df["avg_risk_score"]) / 2
    return df


# ---------------------------------------------------------------------------
# Merge / comparison
# ---------------------------------------------------------------------------

def compare_with_ft0(
    df_current: pd.DataFrame,
    ft0: pd.DataFrame,
    label: str = "current",
) -> pd.DataFrame:
    """
    Merge current output with FT0 by nearest date.

    Returns a combined DataFrame with columns suffixed _ft0 and _current.
    """
    df_c = df_current[["date", "avg_risk_score", "fiscal_tone_index", "n_paragraphs"]].copy()
    df_c = df_c.rename(columns={
        "avg_risk_score": f"avg_risk_score_{label}",
        "fiscal_tone_index": f"fiscal_tone_{label}",
        "n_paragraphs": f"n_paragraphs_{label}",
    })

    ft0_sub = ft0[["date", "avg_risk_score", "fiscal_tone_index", "n_paragraphs"]].copy()
    ft0_sub = ft0_sub.rename(columns={
        "avg_risk_score": "avg_risk_score_ft0",
        "fiscal_tone_index": "fiscal_tone_ft0",
        "n_paragraphs": "n_paragraphs_ft0",
    })

    merged = pd.merge_asof(
        ft0_sub.sort_values("date"),
        df_c.sort_values("date"),
        on="date",
        direction="nearest",
        tolerance=pd.Timedelta("35 days"),
    )
    merged["fiscal_tone_diff"] = merged[f"fiscal_tone_{label}"] - merged["fiscal_tone_ft0"]
    return merged


# ---------------------------------------------------------------------------
# Printing utilities
# ---------------------------------------------------------------------------

def print_stats(df: pd.DataFrame, label: str, col: str = "fiscal_tone_index") -> None:
    s = df[col].dropna()
    print(f"\n  {label} (n={len(s)}):")
    print(f"    mean = {s.mean():+.4f}")
    print(f"    std  = {s.std():.4f}")
    print(f"    min  = {s.min():+.4f}")
    print(f"    max  = {s.max():+.4f}")


def print_comparison_table(merged: pd.DataFrame, label: str = "with_ctx") -> None:
    cols_of_interest = ["date", "fiscal_tone_ft0", f"fiscal_tone_{label}", "fiscal_tone_diff"]
    available = [c for c in cols_of_interest if c in merged.columns]
    sub = merged[available].dropna()
    sub["date"] = sub["date"].dt.strftime("%Y-%m-%d")
    print(sub.to_string(index=False, float_format=lambda x: f"{x:+.3f}"))


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

COLORS = {
    "ft0": "#2c3e50",
    "with_ctx": "#2980b9",
    "no_ctx": "#e74c3c",
    "score_1": "#1a5276",
    "score_2": "#28b463",
    "score_3": "#f1c40f",
    "score_4": "#e67e22",
    "score_5": "#c0392b",
}


def plot_comparison(
    ft0: pd.DataFrame,
    df_ctx: pd.DataFrame,
    df_no: pd.DataFrame,
    cma_window: int = 5,
    save: bool = False,
) -> None:
    """Generate 3-panel comparison figure."""
    # Compute CMAs
    df_ctx = add_cma(df_ctx, "fiscal_tone_index", cma_window)
    df_no = add_cma(df_no, "fiscal_tone_index", cma_window)

    fig, axes = plt.subplots(3, 1, figsize=(14, 13), constrained_layout=True)
    fig.suptitle("FiscalTone: Current Output vs Reference (FT0)", fontsize=13, y=1.01)

    # ---- Panel 1: Raw fiscal tone index ----
    ax1 = axes[0]
    ax1.axhline(0, color="gray", linewidth=0.7, linestyle="--", zorder=0)
    ax1.plot(
        ft0["date"], ft0["fiscal_tone_index"],
        color=COLORS["ft0"], linewidth=1.2, linestyle="--",
        label="FT0 reference", alpha=0.8,
    )
    ax1.plot(
        df_ctx["date"], df_ctx["fiscal_tone_index"],
        color=COLORS["with_ctx"], linewidth=1.0, alpha=0.7,
        label="With context (current)",
    )
    ax1.plot(
        df_no["date"], df_no["fiscal_tone_index"],
        color=COLORS["no_ctx"], linewidth=1.0, alpha=0.6,
        label="Without context",
    )
    ax1.set_ylabel("Fiscal Tone Index")
    ax1.set_title("Raw per-document Fiscal Tone Index (τ)")
    ax1.legend(fontsize=9)
    ax1.set_ylim(-1.1, 1.1)
    _format_xaxis(ax1)

    # ---- Panel 2: CMA comparison ----
    ax2 = axes[1]
    ax2.axhline(0, color="gray", linewidth=0.7, linestyle="--", zorder=0)
    if "fiscal_tone_index_cma" in ft0.columns:
        ax2.plot(
            ft0["date"], ft0["fiscal_tone_index_cma"],
            color=COLORS["ft0"], linewidth=2.0, linestyle="--",
            label="FT0 CMA (reference)", alpha=0.9,
        )
    ax2.plot(
        df_ctx["date"], df_ctx["fiscal_tone_index_cma"],
        color=COLORS["with_ctx"], linewidth=2.2,
        label=f"With context CMA (w={cma_window})",
    )
    ax2.plot(
        df_no["date"], df_no["fiscal_tone_index_cma"],
        color=COLORS["no_ctx"], linewidth=2.0, linestyle=":",
        label=f"Without context CMA (w={cma_window})",
    )
    ax2.set_ylabel("Fiscal Tone Index (CMA)")
    ax2.set_title(f"Centered Moving Average (window={cma_window} documents)")
    ax2.legend(fontsize=9)
    ax2.set_ylim(-1.1, 1.1)
    _format_xaxis(ax2)

    # ---- Panel 3: Score composition stacked area (with context) ----
    ax3 = axes[2]
    if "score_1_share" in df_ctx.columns:
        share_cols = [f"score_{i}_share" for i in range(1, 6)]
        colors_stack = [COLORS[f"score_{i}"] for i in range(1, 6)]
        ax3.stackplot(
            df_ctx["date"],
            [df_ctx[c] for c in share_cols],
            labels=[f"Score {i}" for i in range(1, 6)],
            colors=colors_stack,
            alpha=0.8,
        )
        ax3.set_ylabel("Share of paragraphs")
        ax3.set_title("Score Distribution — With Context")
        ax3.legend(loc="upper left", fontsize=8, ncol=5)
        ax3.set_ylim(0, 1)
        _format_xaxis(ax3)

    if save:
        FIG_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(FIG_OUTPUT, dpi=150, bbox_inches="tight")
        print(f"\nFigure saved -> {FIG_OUTPUT}")
    else:
        plt.show()

    plt.close(fig)


def _format_xaxis(ax: plt.Axes) -> None:
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4, 7, 10]))
    ax.tick_params(axis="x", which="major", labelsize=9)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze FiscalTone outputs vs FT0 reference")
    parser.add_argument("--save-fig", action="store_true", help="Save figure to data/output/")
    parser.add_argument("--cma-window", type=int, default=5, help="CMA window size (default: 5)")
    parser.add_argument("--no-plot", action="store_true", help="Skip plotting")
    parser.add_argument("--export-csv", action="store_true", help="Export comparison CSV")
    args = parser.parse_args()

    # ------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("LOADING DATA")
    print("=" * 65)

    if not FT0_PATH.exists():
        print(f"[ERROR] FT0.xlsx not found at {FT0_PATH}")
        sys.exit(1)

    ft0 = load_ft0()
    print(f"  FT0 loaded:          {len(ft0)} documents  ({ft0['date'].min().date()} – {ft0['date'].max().date()})")

    df_ctx = None
    if WITH_CTX_PATH.exists():
        df_ctx = load_llm_json(WITH_CTX_PATH, ts_milliseconds=True)
        df_ctx = add_score_shares(df_ctx)
        df_ctx = add_fiscal_tone_index(df_ctx)
        print(f"  With-context loaded: {len(df_ctx)} documents  ({df_ctx['date'].min().date()} – {df_ctx['date'].max().date()})")
    else:
        print(f"  [WARN] With-context JSON not found: {WITH_CTX_PATH}")

    df_no = None
    if NO_CTX_PATH.exists():
        df_no = load_llm_json(NO_CTX_PATH, ts_milliseconds=False)
        df_no = add_score_shares(df_no)
        df_no = add_fiscal_tone_index(df_no)
        print(f"  No-context loaded:   {len(df_no)} documents  ({df_no['date'].min().date()} – {df_no['date'].max().date()})")
    else:
        print(f"  [WARN] No-context JSON not found: {NO_CTX_PATH}")

    # ------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("SUMMARY STATISTICS — fiscal_tone_index")
    print("=" * 65)

    print_stats(ft0, "FT0 (reference)")
    if df_ctx is not None:
        print_stats(df_ctx, "With context (current best)")
    if df_no is not None:
        print_stats(df_no, "Without context")

    # ------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("DOCUMENT-LEVEL COMPARISON: FT0 vs With-Context")
    print("=" * 65)

    if df_ctx is not None:
        merged_ctx = compare_with_ft0(df_ctx, ft0, label="with_ctx")
        print_comparison_table(merged_ctx, "with_ctx")

        mae = merged_ctx["fiscal_tone_diff"].abs().mean()
        bias = merged_ctx["fiscal_tone_diff"].mean()
        print(f"\n  MAE  (with_ctx vs FT0): {mae:.4f}")
        print(f"  Bias (with_ctx vs FT0): {bias:+.4f}  ({'over-estimates concern' if bias < 0 else 'under-estimates concern'})")

        if args.export_csv:
            merged_ctx.to_csv(COMPARISON_CSV, index=False)
            print(f"\nComparison CSV saved -> {COMPARISON_CSV}")

    if df_no is not None:
        merged_no = compare_with_ft0(df_no, ft0, label="no_ctx")
        mae_no = merged_no["fiscal_tone_diff"].abs().mean()
        bias_no = merged_no["fiscal_tone_diff"].mean()
        print(f"\n  MAE  (no_ctx  vs FT0): {mae_no:.4f}")
        print(f"  Bias (no_ctx  vs FT0): {bias_no:+.4f}  ({'over-estimates concern' if bias_no < 0 else 'under-estimates concern'})")

    # ------------------------------------------------------------------
    print("\n" + "=" * 65)
    print("RECENT DOCUMENTS — With-Context (2022–2025)")
    print("=" * 65)

    if df_ctx is not None:
        recent = df_ctx[df_ctx["date"] >= "2022-01-01"][
            ["date", "doc_title", "n_paragraphs", "avg_risk_score", "fiscal_tone_index"]
        ].copy()
        recent["date"] = recent["date"].dt.strftime("%Y-%m-%d")
        recent["doc_title"] = recent["doc_title"].str[:60]
        print(recent.to_string(index=False))

    # ------------------------------------------------------------------
    if not args.no_plot:
        if df_ctx is not None and df_no is not None:
            print("\nGenerating comparison figure...")
            plot_comparison(ft0, df_ctx, df_no, cma_window=args.cma_window, save=args.save_fig)
        elif df_ctx is not None:
            print("[WARN] Only with-context data available; skipping full comparison plot.")


if __name__ == "__main__":
    main()
