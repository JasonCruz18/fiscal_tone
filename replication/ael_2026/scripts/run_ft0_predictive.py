"""Estimate the revised predictive specification on the original FT0 index."""

from pathlib import Path

import pandas as pd
import statsmodels.api as sm
from statsmodels.regression.linear_model import OLS


ROOT = Path(__file__).resolve().parents[1]
FT0 = ROOT / "data" / "reference" / "FT0.xlsx"
MACRO = ROOT / "data" / "reference" / "bcrp_macro.csv"
OUTPUT = ROOT / "outputs" / "ft0_predictive_results.csv"


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    tone = pd.read_excel(FT0)
    tone = tone.loc[
        tone["fiscal_tone_index"].notna(), ["date", "fiscal_tone_index"]
    ].rename(columns={"fiscal_tone_index": "tau"})
    tone["date"] = pd.to_datetime(tone["date"]) + pd.offsets.MonthEnd(0)

    macro = pd.read_csv(MACRO, parse_dates=["date"]).sort_values("date")
    return tone.sort_values("date").reset_index(drop=True), macro.set_index("date")


def estimate(
    tone: pd.DataFrame,
    macro: pd.DataFrame,
    horizons: tuple[int, ...] = (3, 6, 9, 12),
) -> pd.DataFrame:
    base = tone.copy()
    macro_map = macro.to_dict()
    for variable in ["deficit", "gdp_growth", "inflation", "copper_yoy"]:
        base[f"{variable}_t"] = base["date"].map(macro_map[variable])

    rows = []
    for horizon in horizons:
        data = base.copy()
        future_dates = data["date"] + pd.DateOffset(months=horizon)
        future_dates = future_dates.apply(lambda date: date + pd.offsets.MonthEnd(0))
        data["def_h"] = future_dates.map(macro["deficit"].to_dict())

        controls = ["deficit_t", "gdp_growth_t", "inflation_t", "copper_yoy_t"]
        estimation = data[["tau", *controls, "def_h"]].dropna()
        design = sm.add_constant(estimation[["tau", *controls]].values)
        result = OLS(estimation["def_h"].values, design).fit(
            cov_type="HAC", cov_kwds={"maxlags": 4}
        )
        p_value = float(result.pvalues[1])
        rows.append(
            {
                "h": horizon,
                "beta_tau": float(result.params[1]),
                "se_tau": float(result.bse[1]),
                "t_tau": float(result.tvalues[1]),
                "p_tau": p_value,
                "stars": (
                    "***"
                    if p_value < 0.01
                    else "**"
                    if p_value < 0.05
                    else "*"
                    if p_value < 0.10
                    else ""
                ),
                "n_obs": int(result.nobs),
                "r2": float(result.rsquared),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    tone, macro = load_inputs()
    results = estimate(tone, macro)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(OUTPUT, index=False)
    print(f"FT0 usable documents: {len(tone)}")
    print(results.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
