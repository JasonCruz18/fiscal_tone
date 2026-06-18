"""Run prompt-robustness experiments on the original FT0 corpus from _OLD_ANALYSIS."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Callable

import aiolimiter
import openai
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data" / "processed" / "llm_input_text_dataset_true.csv"
REFERENCE_PATH = ROOT / "data" / "paper_outputs" / "df_fiscal_scored_true.csv"
OUTPUT_DIR = ROOT / "data" / "prompt_robustness"
MODEL = "gpt-4o-2024-08-06"
RPM = 12
SAVE_EVERY = 50

PromptBuilder = Callable[[str], str]

FT0_PROMPT = """Eres un analista tecnico del Consejo Fiscal de Peru. Evalua el siguiente parrafo extraido de un informe tecnico del Consejo Fiscal (CF), donde se emite una opinion sobre el desempeno fiscal del Ministerio de Economia y Finanzas (MEF) en cuanto al cumplimiento de las metas fiscales.\n\nTu tarea es asignar un puntaje del 1 al 5 segun el nivel de preocupacion o alerta fiscal expresado en el texto.\n\nInterpretacion:\n- 1 = Sin preocupacion fiscal (cumplimiento de metas, transparencia fiscal, planificacion multianual)\n- 2 = Ligera preocupacion (riesgo fiscal potencial, desviacion del deficit, dependencia de ingresos extraordinarios)\n- 3 = Neutral (descripcion tecnica, gestion dentro del marco, sin juicio valorativo)\n- 4 = Alta preocupacion (incumplimiento de metas, relajamiento fiscal, incertidumbre macroeconomica)\n- 5 = Alarma fiscal (criticas severas, riesgo de sostenibilidad de la deuda, independencia fiscal comprometida)\n\nDevuelve solo un numero del 1 al 5.\n\nTexto:\n\"\"\"{text}\"\"\""""

NEUTRAL_PROMPT = """You are reading a paragraph from an official fiscal policy document.\n\nAssign a single score from 1 to 5 based only on the degree of fiscal concern or reassurance expressed in the paragraph itself.\n\nInterpretation:\n1 = Clearly reassuring or favorable fiscal assessment\n2 = Mild concern or limited caution\n3 = Neutral or mainly descriptive\n4 = Strong concern or explicit criticism\n5 = Very strong alarm or severe fiscal warning\n\nDo not use any external background. Do not infer more than what the paragraph states. Respond with ONLY one number: 1, 2, 3, 4, or 5.\n\nParagraph:\n\"\"\"{text}\"\"\""""

MINIMAL_PROMPT = """You are classifying the tone of a paragraph from an official fiscal policy communication.\n\nAssign a score from 1 to 5 according to the level of fiscal concern expressed in the paragraph:\n\n1 = Positive fiscal assessment or explicit validation\n2 = Mild concern or limited warning\n3 = Neutral or descriptive discussion\n4 = Strong concern or clear criticism\n5 = Severe fiscal alarm, explicit sustainability warning, or crisis-level criticism\n\nBase the score only on the paragraph. Respond with ONLY one number: 1, 2, 3, 4, or 5.\n\nParagraph:\n\"\"\"{text}\"\"\""""

PROMPTS: dict[str, PromptBuilder] = {
    "ft0_original": lambda text: FT0_PROMPT.format(text=text),
    "neutral": lambda text: NEUTRAL_PROMPT.format(text=text),
    "minimal_taxonomy": lambda text: MINIMAL_PROMPT.format(text=text),
}


def calc_tau(score: float) -> float:
    return (3 - score) / 2


def load_rows(output_path: Path) -> list[dict[str, Any]]:
    df = pd.read_csv(INPUT_PATH, encoding="latin-1")
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    rows = []
    for idx, row in df.iterrows():
        rows.append({
            "row_idx": int(idx),
            "title": str(row.get("title", "")),
            "doc_type": str(row.get("doc_type", "")),
            "doc_id": row.get("doc_id"),
            "year": row.get("year"),
            "date": str(row.get("date", "")),
            "page": row.get("page"),
            "paragraph_id": row.get("paragraph_id"),
            "text": str(row.get("text", "")),
            "fiscal_risk_score": None,
            "risk_index": None,
        })
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        by_idx = {r["row_idx"]: r for r in existing if r.get("fiscal_risk_score") is not None}
        for row in rows:
            prior = by_idx.get(row["row_idx"])
            if prior is not None:
                row["fiscal_risk_score"] = prior["fiscal_risk_score"]
                row["risk_index"] = prior.get("risk_index")
    return rows


def save_rows(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


async def score_one(client: openai.AsyncOpenAI, limiter: aiolimiter.AsyncLimiter, prompt_style: str, text: str) -> int | None:
    async with limiter:
        try:
            response = await client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": PROMPTS[prompt_style](text)}],
                temperature=0,
                max_tokens=5,
            )
        except openai.RateLimitError:
            await asyncio.sleep(10)
            return None
        except Exception:
            return None
    raw = response.choices[0].message.content.strip()
    return int(raw) if raw in {"1", "2", "3", "4", "5"} else None


def aggregate(rows: list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df = df[df["fiscal_risk_score"].notna()].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    docs = (
        df.groupby(["date", "title"], as_index=False)
        .agg(avg_risk_score=("fiscal_risk_score", "mean"), n_paragraphs=("fiscal_risk_score", "size"))
        .sort_values(["date", "title"])
        .reset_index(drop=True)
    )
    docs["fiscal_tone_index"] = docs["avg_risk_score"].apply(calc_tau)
    return docs


def compare(rows: list[dict[str, Any]], docs: pd.DataFrame) -> dict[str, float]:
    ref_rows = pd.read_csv(REFERENCE_PATH, encoding="latin-1")
    merged_rows = ref_rows.merge(pd.DataFrame(rows)[["row_idx", "fiscal_risk_score"]], left_index=True, right_on="row_idx")
    paragraph_mae = (merged_rows["fiscal_risk_score_y"] - merged_rows["fiscal_risk_score_x"]).abs().mean()
    paragraph_match = (merged_rows["fiscal_risk_score_x"] == merged_rows["fiscal_risk_score_y"]).mean()

    ref_docs = pd.read_csv(ROOT / "data" / "paper_outputs" / "df_fiscal_tone_true.csv")
    ref_docs["date"] = pd.to_datetime(ref_docs["date"], errors="coerce")
    merged_docs = ref_docs[["date", "fiscal_tone_index"]].drop_duplicates("date").merge(
        docs[["date", "fiscal_tone_index"]].rename(columns={"fiscal_tone_index": "our_tau"}),
        on="date",
        how="inner",
    )
    merged_docs = merged_docs.rename(columns={"fiscal_tone_index": "ft0_tau"})
    diff = merged_docs["our_tau"] - merged_docs["ft0_tau"]
    return {
        "paragraph_exact_match": float(paragraph_match),
        "paragraph_mae": float(paragraph_mae),
        "corr_vs_ft0": float(merged_docs["our_tau"].corr(merged_docs["ft0_tau"])),
        "mae_vs_ft0": float(diff.abs().mean()),
        "bias_vs_ft0": float(diff.mean()),
        "matched_docs": float(len(merged_docs)),
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-style", choices=sorted(PROMPTS), default="neutral")
    args = parser.parse_args()

    output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"ft0_{args.prompt_style}"
    paragraph_output = output_dir / f"{stem}_paragraphs.json"
    doc_output = output_dir / f"{stem}_documents.csv"
    summary_output = output_dir / f"{stem}_summary.json"

    rows = load_rows(paragraph_output)
    pending = [row for row in rows if row["fiscal_risk_score"] is None]
    print(f"[INFO] prompt_style={args.prompt_style}")
    print(f"[INFO] {len(rows)} paragraphs total, {len(pending)} to score")

    if pending:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        client = openai.AsyncOpenAI(api_key=api_key)
        limiter = aiolimiter.AsyncLimiter(RPM, 60)
        for i, row in enumerate(pending, start=1):
            score = await score_one(client, limiter, args.prompt_style, row["text"])
            if score is not None:
                row["fiscal_risk_score"] = score
                row["risk_index"] = calc_tau(score)
            if i % SAVE_EVERY == 0 or i == len(pending):
                save_rows(rows, paragraph_output)
                done = sum(1 for item in rows if item["fiscal_risk_score"] is not None)
                print(f"[SAVE] {done}/{len(rows)} scored")

    save_rows(rows, paragraph_output)
    docs = aggregate(rows)
    docs.to_csv(doc_output, index=False, encoding="utf-8")
    summary = {"prompt_style": args.prompt_style, **compare(rows, docs)}
    summary_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
