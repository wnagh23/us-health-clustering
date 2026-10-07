"""Download Census ACS 1-Year (Data Profile) and County Business Patterns state data.

Writes data/acs_states.csv and data/cbp_businesses.csv.
Needs a free API key: https://api.census.gov/data/key_signup.html

Usage:
    export CENSUS_API_KEY=...            # PowerShell: $env:CENSUS_API_KEY="..."
    uv run --group fetch python scripts/fetch_census.py

Note: Data Profile variable codes are not stable across years (e.g. DP02_0068PE is
"bachelor's degree or higher" only from 2019; in 2013-2018 that is DP02_0067PE).
Codes below are downloaded as-is; the year-specific fixes live in
src/ushealth/data.py so they are visible next to the analysis.
"""

import os
import time
from pathlib import Path

import pandas as pd
import requests

KEY = os.environ["CENSUS_API_KEY"]
DATA = Path(__file__).resolve().parents[1] / "data"
YEARS = [y for y in range(2013, 2024) if y != 2020]  # no ACS 1-Year release for 2020
# 50 states (DC excluded): FIPS code -> postal abbreviation
STATES = dict(zip(
    [f"{i:02d}" for i in range(1, 57) if i not in (3, 7, 11, 14, 43, 52)],
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV "
    "NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split(),
))

ACS_VARS = {
    "DP05_0001E": "populacja_total",
    "DP03_0062E": "mediana_dochodu_gosp_dom",
    "DP03_0119PE": "pct_ubóstwo",            # families below poverty level
    "DP03_0004PE": "pct_zatrudnieni",
    "DP03_0005PE": "pct_bezrobocie",         # unemployed, % of population 16+
    "DP03_0019PE": "pct_dojazd_samochod",    # drove alone
    "DP03_0020PE": "pct_dojazd_carpool",
    "DP03_0021PE": "pct_dojazd_transport_pub",
    "DP03_0022PE": "pct_dojazd_pieszo",
    "DP03_0024PE": "pct_praca_z_domu",
    "DP03_0025E": "sredni_czas_dojazdu_min",
    "DP02_0067PE": "pct_wyksztalcenie_srednie",
    "DP02_0068PE": "pct_wyksztalcenie_wyzsze",
    "DP03_0096PE": "pct_bez_ubezpieczenia",  # actually % WITH health insurance
}
CBP_NAICS = {"713940": "fitness_centers", "445310": "liquor_stores"}


def get(url: str, params: dict) -> list:
    for attempt in range(3):
        r = requests.get(url, params={**params, "key": KEY}, timeout=60)
        if r.status_code == 200:
            return r.json()
        time.sleep(5 * (attempt + 1))
    r.raise_for_status()


def fetch_acs() -> pd.DataFrame:
    frames = []
    for year in YEARS:
        rows = get(
            f"https://api.census.gov/data/{year}/acs/acs1/profile",
            {"get": "NAME," + ",".join(ACS_VARS), "for": "state:*"},
        )
        df = pd.DataFrame(rows[1:], columns=rows[0])
        df = df[df["state"].isin(STATES)]
        df.insert(0, "rok", year)
        df.insert(1, "stan_fips", "FIPS:" + df["state"])
        df = df.rename(columns={"NAME": "stan_nazwa", **ACS_VARS}).drop(columns="state")
        frames.append(df)
    acs = pd.concat(frames, ignore_index=True)
    num = list(ACS_VARS.values())
    acs[num] = acs[num].apply(pd.to_numeric, errors="coerce").mask(lambda x: x < -1e8)
    return acs


def fetch_cbp() -> pd.DataFrame:
    frames = []
    for year in range(2012, 2024):
        naics_var = "NAICS2017" if year >= 2017 else "NAICS2012"
        for code, name in CBP_NAICS.items():
            rows = get(
                f"https://api.census.gov/data/{year}/cbp",
                {"get": f"{naics_var},ESTAB", "for": "state:*", naics_var: code},
            )
            df = pd.DataFrame(rows[1:], columns=rows[0])
            frames.append(df.assign(year=year, category=name))
    cbp = pd.concat(frames)
    cbp = cbp[cbp["state"].isin(STATES)]
    cbp["ESTAB"] = pd.to_numeric(cbp["ESTAB"])
    wide = cbp.pivot_table(index=["year", "state"], columns="category", values="ESTAB").reset_index()
    return pd.DataFrame({
        "year": wide["year"],
        "state_fips": wide["state"].astype(int),
        "state_abbr": wide["state"].map(STATES),
        "fitness_centers_estab": wide["fitness_centers"],
        "liquor_stores_estab": wide["liquor_stores"],
    })


if __name__ == "__main__":
    fetch_acs().to_csv(DATA / "acs_states.csv", index=False)
    fetch_cbp().to_csv(DATA / "cbp_businesses.csv", index=False)
    print("Saved data/acs_states.csv and data/cbp_businesses.csv")
