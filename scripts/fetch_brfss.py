"""Download CDC BRFSS state estimates (Nutrition, Physical Activity, and Obesity)
and save the subset used in the analysis to data/brfss_npao_states.csv.

Source: https://data.cdc.gov/d/hn4x-zwk7 (public, no API key needed)
Usage:  uv run --group fetch python scripts/fetch_brfss.py
"""

from pathlib import Path

import pandas as pd
import requests

URL = "https://data.cdc.gov/resource/hn4x-zwk7.json"
QUESTIONS = ["Q018", "Q019", "Q036", "Q037", "Q043", "Q045", "Q046", "Q047"]
YEARS = (2011, 2024)
OUT = Path(__file__).resolve().parents[1] / "data" / "brfss_npao_states.csv"


def main() -> None:
    where = (
        "stratificationcategory1='Total' "
        f"AND questionid in({','.join(repr(q) for q in QUESTIONS)}) "
        f"AND yearstart between {YEARS[0]} and {YEARS[1]}"
    )
    params = {
        "$select": "yearstart,locationabbr,locationdesc,questionid,question,data_value,sample_size",
        "$where": where,
        "$limit": 50_000,
    }
    rows = requests.get(URL, params=params, timeout=120).json()
    df = pd.DataFrame(rows).rename(
        columns={
            "yearstart": "Year",
            "locationabbr": "LocationAbbr",
            "locationdesc": "LocationDesc",
            "questionid": "QuestionID",
            "question": "Question",
            "data_value": "Value",
            "sample_size": "SampleSize",
        }
    )
    df["Year"] = df["Year"].astype(int)
    df["Value"] = pd.to_numeric(df["Value"])
    df = df.dropna(subset=["Value"]).sort_values(["Year", "LocationAbbr", "QuestionID"])
    df.to_csv(OUT, index=False)
    print(f"Saved {len(df)} rows to {OUT}")


if __name__ == "__main__":
    main()
