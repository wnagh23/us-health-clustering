"""Download NOAA monthly station data (GSOM) and aggregate it to state x month.

Writes data/noaa_weather_monthly.csv (mean of all GHCN-Daily stations in a state).
Needs a free token: https://www.ncdc.noaa.gov/cdo-web/token
A full run takes several hours because of API rate limits. States already in the
output file are skipped (resume); delete the file to download everything again.

Usage:
    export NOAA_TOKEN=...                # PowerShell: $env:NOAA_TOKEN="..."
    uv run --group fetch python scripts/fetch_noaa.py

The committed file was produced by an earlier version of this script that also
downloaded ~20 other variables and wrote states with different column sets into one
CSV; that file was repaired once (columns re-aligned) before trimming to the
columns kept here.
"""

import os
import time
from pathlib import Path

import pandas as pd
import requests

TOKEN = os.environ["NOAA_TOKEN"]
API = "https://www.ncei.noaa.gov/cdo-web/api/v2/data"
STATIONS_URL = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt"
OUT = Path(__file__).resolve().parents[1] / "data" / "noaa_weather_monthly.csv"
RAW = OUT.parent / "raw"
COLUMNS = ["stan_fips", "stan_nazwa", "rok", "miesiac", "TAVG_mean", "PRCP_mean", "n_stacji"]
VARIABLES = ["TAVG", "TMAX", "TMIN", "PRCP"]
PERIODS = [("2011-01-01", "2020-12-31"), ("2021-01-01", "2023-12-31")]  # API max 10 years
POSTAL = dict(zip(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV "
    "NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split(),
    [f"{i:02d}" for i in range(1, 57) if i not in (3, 7, 11, 14, 43, 52)],
))
FULL_NAMES = dict(zip(POSTAL, [
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
    "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan",
    "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
    "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
    "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", "West Virginia",
    "Wisconsin", "Wyoming",
]))


def stations_by_state() -> dict:
    """US GHCN-Daily station ids per state, from NOAA's static station list (no token)."""
    cache = RAW / "ghcnd_stations_us.csv"
    if not cache.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        lines = requests.get(STATIONS_URL, timeout=120).text.splitlines()
        rows = [(l[0:11], l[38:40].strip()) for l in lines if l.startswith("US") and l[38:40].strip() in POSTAL]
        pd.DataFrame(rows, columns=["station", "state"]).to_csv(cache, index=False)
    df = pd.read_csv(cache)
    return {state: ("GHCND:" + grp["station"]).tolist() for state, grp in df.groupby("state")}


def api_get(params: dict) -> dict:
    for attempt in range(4):
        r = requests.get(API, headers={"token": TOKEN}, params=params, timeout=120)
        if r.status_code == 200:
            return r.json()
        time.sleep(15 * (attempt + 1))  # 429 / 503: back off
    return {}


def fetch_state(stations: list) -> pd.DataFrame:
    records = []
    for i in range(0, len(stations), 10):
        for start, end in PERIODS:
            offset = 1
            while True:
                data = api_get({
                    "datasetid": "GSOM", "stationid": ",".join(stations[i:i + 10]),
                    "datatypeid": ",".join(VARIABLES), "startdate": start, "enddate": end,
                    "units": "metric", "limit": 1000, "offset": offset,
                })
                records += data.get("results", [])
                total = data.get("metadata", {}).get("resultset", {}).get("count", 0)
                if offset + 1000 > total:
                    break
                offset += 1000
            time.sleep(0.3)
    return pd.DataFrame(records)


def aggregate(records: pd.DataFrame, state: str) -> pd.DataFrame:
    records["date"] = pd.to_datetime(records["date"])
    wide = records.pivot_table(index=["station", "date"], columns="datatype", values="value").reset_index()
    if "TAVG" not in wide:
        wide["TAVG"] = float("nan")
    if {"TMAX", "TMIN"} <= set(wide.columns):
        wide["TAVG"] = wide["TAVG"].fillna((wide["TMAX"] + wide["TMIN"]) / 2)
    wide["rok"], wide["miesiac"] = wide["date"].dt.year, wide["date"].dt.month
    out = wide.groupby(["rok", "miesiac"]).agg(
        TAVG_mean=("TAVG", "mean"), PRCP_mean=("PRCP", "mean"), n_stacji=("station", "nunique")
    ).reset_index()
    out.insert(0, "stan_nazwa", FULL_NAMES[state])
    out.insert(0, "stan_fips", "FIPS:" + POSTAL[state])
    return out[COLUMNS]  # fixed column order for every state


def main() -> None:
    done = set(pd.read_csv(OUT)["stan_nazwa"]) if OUT.exists() else set()
    for state, stations in stations_by_state().items():
        if FULL_NAMES[state] in done:
            continue
        print(f"{state}: {len(stations)} stations")
        records = fetch_state(stations)
        if records.empty:
            continue
        aggregate(records, state).to_csv(OUT, mode="a", header=not OUT.exists(), index=False)


if __name__ == "__main__":
    main()
