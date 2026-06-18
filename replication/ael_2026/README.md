# Applied Economics Letters replication package

This directory freezes the inputs and code associated with the Fiscal Tone
article submitted to *Applied Economics Letters*. It is intentionally separate
from the repository's evolving extraction pipeline.

## Sample definitions

The manuscript describes a corpus of 77 Fiscal Council publication titles
covering January 2016 through October 2025. The context-classification corpus
contains 1,432 paragraphs.

The original keyword-filtered workflow used to construct `FT0.xlsx` is a
different analytical layer:

- `llm_input_text_dataset_true.csv` contains 448 selected paragraphs.
- `df_fiscal_scored_true.csv` contains the original GPT scores for those rows.
- `FT0.xlsx` contains 70 document rows. Sixty-eight rows have a non-missing
  fiscal-tone index; the August and October 2025 additions have paragraph
  information but no index stored in the workbook.

These distinctions are retained rather than silently treating the corpus size
and the number of usable document-level observations as identical.

## Directory layout

```text
replication/ael_2026/
├── data/
│   ├── processed/       # Frozen classification inputs
│   ├── scored/          # Original paragraph-level scores
│   ├── reference/       # FT0 and macroeconomic inputs
│   └── robustness/      # Neutral-prompt results
├── notebooks/           # Original LLM scoring notebook
├── scripts/             # Reproducible preprocessing and analysis scripts
└── outputs/             # Regenerated tables and diagnostics
```

## Reproduction order

1. Inspect the frozen data:

   ```bash
   python replication/ael_2026/scripts/validate_inputs.py
   ```

2. To reproduce the original preprocessing from raw extracted text:

   ```bash
   python replication/ael_2026/scripts/text_preprocessing_pipeline.py
   ```

3. To rerun a prompt specification, set `OPENAI_API_KEY` and run:

   ```bash
   python replication/ael_2026/scripts/run_prompt_robustness.py \
     --prompt-style neutral
   ```

4. To reproduce the predictive-regression table using the non-missing FT0
   document-level observations:

   ```bash
   python replication/ael_2026/scripts/run_ft0_predictive.py
   ```

LLM reruns are not expected to be bit-for-bit deterministic across API service
dates, even with temperature set to zero. The original scored files are
therefore included as frozen research outputs.

## Repository status

The broader FiscalTone repository contains an ongoing, more sophisticated PDF
extraction and text-processing pipeline. That pipeline is useful for future
extensions but does not replace this frozen article-specific package.

