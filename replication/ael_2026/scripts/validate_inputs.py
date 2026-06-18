"""Validate the frozen AEL replication inputs and report sample definitions."""

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    corpus = pd.read_csv(
        ROOT / "data" / "processed" / "llm_output_paragraphs_with_context.csv",
        encoding_errors="replace",
    )
    filtered = pd.read_csv(
        ROOT / "data" / "processed" / "llm_input_text_dataset_true.csv",
        encoding="latin-1",
    )
    scored = pd.read_csv(
        ROOT / "data" / "scored" / "df_fiscal_scored_true.csv",
        encoding="latin-1",
    )
    ft0 = pd.read_excel(ROOT / "data" / "reference" / "FT0.xlsx")

    corpus_dates = pd.to_datetime(corpus["date"], errors="coerce")
    print(f"Context corpus paragraphs: {len(corpus):,}")
    print(f"Context corpus titles: {corpus['doc_title'].nunique():,}")
    print(
        "Context corpus dates: "
        f"{corpus_dates.min().date()} to {corpus_dates.max().date()}"
    )
    print(f"Keyword-filtered paragraphs: {len(filtered):,}")
    print(f"Originally scored paragraphs: {len(scored):,}")
    print(f"FT0 document rows: {len(ft0):,}")
    print(
        "FT0 non-missing tone indices: "
        f"{ft0['fiscal_tone_index'].notna().sum():,}"
    )

    assert len(corpus) == 1432
    assert corpus["doc_title"].nunique() == 77
    assert len(filtered) == 448
    assert len(scored) == 448
    assert len(ft0) == 70
    assert ft0["fiscal_tone_index"].notna().sum() == 68


if __name__ == "__main__":
    main()

