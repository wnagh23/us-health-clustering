"""Loading and merging the four data sources into a state-year panel."""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

BRFSS_QUESTIONS = {
    "Q036": "Obesity",
    "Q037": "Overweight",
    "Q047": "NoActivity",
    "Q045": "HighActivity",
    "Q043": "ModActivity",
    "Q046": "MuscleActivity",
    "Q018": "LowFruits",
    "Q019": "LowVeggies",
}

# Features used for PCA and clustering (state-level averages)
CLUSTER_COLS = [
    "Obesity",
    "NoActivity",
    "HighActivity",
    "mediana_dochodu_gosp_dom",
    "pct_ubostwo_rodzin",
    "pct_bezrobotni",
    "pct_wyksztalcenie_wyzsze",
    "pct_bez_ubezpieczenia",
    "pct_dojazd_samochod",
    "pct_praca_z_domu",
    "fitness_per_100k",
    "avg_temp",
]

# Short Polish labels for plots
LABELS = {
    "Obesity": "otyłość %",
    "NoActivity": "brak aktywności %",
    "HighActivity": "wysoka aktywność %",
    "mediana_dochodu_gosp_dom": "mediana dochodu",
    "pct_ubostwo_rodzin": "ubóstwo rodzin %",
    "pct_bezrobotni": "bezrobotni %",
    "pct_wyksztalcenie_wyzsze": "wyższe wykształcenie %",
    "pct_bez_ubezpieczenia": "bez ubezpieczenia %",
    "pct_dojazd_samochod": "dojazd autem %",
    "pct_praca_z_domu": "praca z domu %",
    "fitness_per_100k": "siłownie / 100k",
    "avg_temp": "śr. temperatura °C",
}

ID_COLS = ["LocationDesc", "LocationAbbr", "Region", "Division"]


def label(col: str) -> str:
    """Readable label, also for derived '<col>_mean' / '<col>_trend' features."""
    base, _, kind = col.rpartition("_")
    if kind == "mean" and base in LABELS:
        return LABELS[base]
    if kind == "trend" and base in LABELS:
        return "trend: " + LABELS[base].replace(" %", "")
    return LABELS.get(col, col)


def _load_health(data_dir: Path) -> pd.DataFrame:
    health = pd.read_csv(data_dir / "brfss_npao_states.csv")
    health["Metric"] = health["QuestionID"].map(BRFSS_QUESTIONS)
    return health.pivot_table(
        index=["Year", "LocationDesc", "LocationAbbr"], columns="Metric", values="Value"
    ).reset_index().rename_axis(columns=None)


def _load_census(data_dir: Path) -> pd.DataFrame:
    acs = pd.read_csv(data_dir / "acs_states.csv")

    # ACS Data Profile variable codes shift between years. The share of adults
    # with a bachelor's degree or higher is DP02_0068PE from 2019 on, but
    # DP02_0067PE in 2013-2018, which the download stored as
    # "pct_wyksztalcenie_srednie". Use the right code for each year.
    before_2019 = acs["rok"] < 2019
    acs.loc[before_2019, "pct_wyksztalcenie_wyzsze"] = acs.loc[
        before_2019, "pct_wyksztalcenie_srednie"
    ]
    acs = acs.drop(columns="pct_wyksztalcenie_srednie")

    # DP03_0096PE is the share WITH health insurance; convert to uninsured.
    acs["pct_bez_ubezpieczenia"] = 100 - acs["pct_bez_ubezpieczenia"]

    return acs.rename(
        columns={
            "rok": "Year",
            "stan_nazwa": "LocationDesc",
            # DP03_0119PE: families below the poverty level
            "pct_ubóstwo": "pct_ubostwo_rodzin",
            # DP03_0005PE: unemployed as % of population 16+ (not the unemployment rate)
            "pct_bezrobocie": "pct_bezrobotni",
        }
    ).drop(columns="stan_fips")


def _load_weather(data_dir: Path) -> pd.DataFrame:
    weather = pd.read_csv(data_dir / "noaa_weather_monthly.csv")
    return (
        weather.groupby(["stan_nazwa", "rok"])
        .agg(avg_temp=("TAVG_mean", "mean"), prcp_index=("PRCP_mean", "sum"))
        .reset_index()
        .rename(columns={"stan_nazwa": "LocationDesc", "rok": "Year"})
    )


def _load_business(data_dir: Path) -> pd.DataFrame:
    biz = pd.read_csv(data_dir / "cbp_businesses.csv")
    return biz.rename(columns={"year": "Year", "state_abbr": "LocationAbbr"})[
        ["Year", "LocationAbbr", "fitness_centers_estab", "liquor_stores_estab"]
    ]


def load_panel(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """State x year panel (50 states, 2013-2023 without 2020)."""
    regions = pd.read_csv(data_dir / "us_regions.csv").rename(
        columns={"State": "LocationDesc"}
    )
    panel = (
        _load_health(data_dir)
        .merge(_load_census(data_dir), on=["Year", "LocationDesc"], how="inner")
        .merge(_load_weather(data_dir), on=["Year", "LocationDesc"], how="left")
        .merge(_load_business(data_dir), on=["Year", "LocationAbbr"], how="left")
        .merge(regions, on="LocationDesc", how="inner")
    )
    panel["fitness_per_100k"] = panel["fitness_centers_estab"] / panel["populacja_total"] * 1e5
    return panel.sort_values(["LocationAbbr", "Year"]).reset_index(drop=True)


def state_profile(panel: pd.DataFrame, cols=CLUSTER_COLS, years=None) -> pd.DataFrame:
    """Average each feature per state; fill remaining gaps with the regional median."""
    if years is not None:
        panel = panel[panel["Year"].between(*years)]
    states = panel.groupby(ID_COLS)[cols].mean().reset_index()
    for col in cols:
        regional_median = states.groupby("Region")[col].transform("median")
        states[col] = states[col].fillna(regional_median)
    return states


def standardize(df: pd.DataFrame) -> pd.DataFrame:
    return (df - df.mean()) / df.std()

