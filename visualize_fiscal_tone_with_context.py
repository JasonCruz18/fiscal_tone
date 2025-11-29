"""
Fiscal Tone Visualization - WITH CONTEXT

Generates visualizations from context-enriched LLM classification results.

Author: Claude Code
Date: 2025-01-28
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from pathlib import Path

print("="*80)
print(" FISCAL TONE VISUALIZATION (WITH CONTEXT) ".center(80, "="))
print("="*80)

# Load document-level aggregated data
print("\n[LOADING] Loading aggregated data with context...")
df_doc_summary = pd.read_csv("data/output/llm_output_documents_with_context.csv")

# Ensure date is datetime
df_doc_summary['date'] = pd.to_datetime(df_doc_summary['date'], errors='coerce')

# Sort by date
df_doc_summary = df_doc_summary.sort_values("date").reset_index(drop=True)

# Create string column for X axis
df_doc_summary['date_str'] = df_doc_summary['date'].dt.strftime('%Y-%m-%d')

print(f"[OK] Loaded {len(df_doc_summary)} documents spanning {df_doc_summary['date'].min()} to {df_doc_summary['date'].max()}")

# ============================================================================
# CHART 1: STACKED AREA CHART - SCORE DISTRIBUTION
# ============================================================================

print("\n[PROCESSING] Generating stacked area chart...")

# Weights for smoothing (1-2-1)
weights = np.array([1, 2, 1])

# Apply centered moving average to score distribution
for col in ['score_1', 'score_2', 'score_3', 'score_4', 'score_5']:
    series = df_doc_summary[col].copy()

    # Middle values: weighted rolling average
    middle_cma = (
        series.rolling(window=3, center=True)
        .apply(lambda x: np.dot(x, weights) / 4, raw=True)
    )

    # Edge handling
    first = series.iloc[0]
    second = series.iloc[1]
    first_smoothed = (3 * first + second) / 4

    last = series.iloc[-1]
    penultimate = series.iloc[-2]
    last_smoothed = (3 * last + penultimate) / 4

    # Insert edge values
    middle_cma.iloc[0] = first_smoothed
    middle_cma.iloc[-1] = last_smoothed

    df_doc_summary[f'{col}_cma'] = middle_cma

# Chart configuration
cols_cma = ['score_1_cma', 'score_2_cma', 'score_3_cma', 'score_4_cma', 'score_5_cma']
labels = ['1 (bajo)', '2', '3', '4', '5 (alto)']
colors = ['#40312C', '#634C44', '#ff8575', '#ED2939', '#1F305E']

# Create figure
fig, ax = plt.subplots(figsize=(14, 6))

# Stacked area plot with smoothed data
ax.stackplot(df_doc_summary['date_str'],
             *[df_doc_summary[col] for col in cols_cma],
             labels=labels,
             colors=colors)

# Labels
ax.set_ylabel("Proporción de Párrafos", fontsize=16)

# X-axis
ax.tick_params(axis='x', labelrotation=90, labelsize=12)

# Y-axis with 2 decimals
ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.2f'))
ax.tick_params(axis='y', labelsize=12)

# Aesthetic grid
ax.grid(True, color='#f5f5f5', alpha=0.3, linewidth=1)

# Custom legend
legend = ax.legend(loc='upper left', frameon=True)
legend.get_frame().set_facecolor('#f5f5f5')
legend.get_frame().set_alpha(0.5)
legend.get_frame().set_edgecolor('#f5f5f5')
legend.get_frame().set_linewidth(2)

# Tight layout
plt.tight_layout()

# Save
output_file_1 = "Fig_Distribucion_Context.png"
plt.savefig(output_file_1, dpi=300)
print(f"[SAVED] {output_file_1}")
plt.close()

# ============================================================================
# CHART 2: FISCAL TONE INDEX TIME SERIES
# ============================================================================

print("\n[PROCESSING] Generating fiscal tone index chart...")

# Smoothing with CMA (1-2-1)
weights = np.array([1, 2, 1])
series = df_doc_summary["fiscal_tone_index"].copy()

cma = series.rolling(window=3, center=True).apply(lambda x: np.dot(x, weights) / 4, raw=True)
cma.iloc[0] = (3 * series.iloc[0] + series.iloc[1]) / 4
cma.iloc[-1] = (3 * series.iloc[-1] + series.iloc[-2]) / 4

df_doc_summary["fiscal_tone_index_cma"] = cma

# Create figure
fig, ax = plt.subplots(figsize=(14, 6))

# Original series (transparent)
ax.plot(df_doc_summary["date_str"], df_doc_summary["fiscal_tone_index"],
        label="Tono Fiscal", linestyle='--',
        marker='o', alpha=0.25, color="#634C44")

# Smoothed series (main)
ax.plot(df_doc_summary["date_str"], df_doc_summary["fiscal_tone_index_cma"],
        label="Tono Fiscal (Promedio Móvil)", linewidth=2, color="#40312C")

# Horizontal line at 0 (neutral tone)
ax.axhline(0, color='#292929', linestyle='-', linewidth=1)

# Y-axis
ax.yaxis.set_major_formatter(ticker.FormatStrFormatter('%.2f'))
ax.tick_params(axis='y', labelsize=12)

# X-axis
ax.tick_params(axis='x', labelrotation=90, labelsize=12)

# Grid only every 2 dates
x_ticks = np.arange(len(df_doc_summary["date_str"]))
ax.set_xticks(x_ticks)
ax.grid(False)

# Vertical lines every 2 ticks
for i in range(0, len(x_ticks), 2):
    ax.axvline(x=i, color='#f5f5f5', linewidth=1, zorder=0)

# Y-axis label
ax.set_ylabel("Índice de Tono Fiscal", fontsize=16)

# Custom legend
legend = ax.legend(loc='upper right', frameon=True)
legend.get_frame().set_facecolor('white')
legend.get_frame().set_alpha(0.5)
legend.get_frame().set_edgecolor('#f5f5f5')
legend.get_frame().set_linewidth(2.5)

# Tight layout
plt.tight_layout()

# Save
output_file_2 = "Fig_Tono_Context.png"
plt.savefig(output_file_2, dpi=300)
print(f"[SAVED] {output_file_2}")
plt.close()

# ============================================================================
# SUMMARY STATISTICS
# ============================================================================

print("\n" + "="*80)
print("VISUALIZATION COMPLETE")
print("="*80)

print(f"\nFiscal Tone Index Summary:")
print(f"  Mean:   {df_doc_summary['fiscal_tone_index'].mean():.3f}")
print(f"  Median: {df_doc_summary['fiscal_tone_index'].median():.3f}")
print(f"  Min:    {df_doc_summary['fiscal_tone_index'].min():.3f} ({df_doc_summary.loc[df_doc_summary['fiscal_tone_index'].idxmin(), 'date'].strftime('%Y-%m-%d')})")
print(f"  Max:    {df_doc_summary['fiscal_tone_index'].max():.3f} ({df_doc_summary.loc[df_doc_summary['fiscal_tone_index'].idxmax(), 'date'].strftime('%Y-%m-%d')})")

print(f"\nTemporal Trend:")
first_half = df_doc_summary.iloc[:len(df_doc_summary)//2]['fiscal_tone_index'].mean()
second_half = df_doc_summary.iloc[len(df_doc_summary)//2:]['fiscal_tone_index'].mean()
print(f"  First half avg:  {first_half:.3f}")
print(f"  Second half avg: {second_half:.3f}")
print(f"  Change:          {second_half - first_half:.3f} ({'worsening' if second_half < first_half else 'improving'})")

print(f"\nOutput files:")
print(f"  - {output_file_1}")
print(f"  - {output_file_2}")
print("="*80)
