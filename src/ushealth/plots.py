"""Plot helpers shared by the notebooks. Figures are saved to reports/figures."""

import warnings
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.io as pio
import seaborn as sns
from matplotlib.patches import Patch
from sklearn.metrics import silhouette_samples

from .data import label, standardize

FIG_DIR = Path(__file__).resolve().parents[2] / "reports" / "figures"

REGION_PALETTE = {
    "Northeast": "#4C72B0",
    "Midwest": "#DD8452",
    "South": "#55A868",
    "West": "#C44E52",
}
# From highest (R1) to lowest risk
RISK_COLORS = ["#C62828", "#EF6C00", "#F9A825", "#1565C0", "#2E7D32", "#6A1B9A"]


def setup() -> None:
    """Common style; static Plotly output so maps render on GitHub."""
    warnings.simplefilter("ignore", category=FutureWarning)
    sns.set_theme(style="whitegrid", font_scale=1.0)
    pio.renderers.default = "png"
    pio.defaults.default_width = 900
    pio.defaults.default_height = 500
    FIG_DIR.mkdir(parents=True, exist_ok=True)


def save(fig, name: str) -> None:
    """Save a matplotlib or plotly figure as reports/figures/<name>.png."""
    path = FIG_DIR / f"{name}.png"
    if hasattr(fig, "write_image"):
        fig.write_image(path, scale=2)
    else:
        fig.savefig(path, dpi=150, bbox_inches="tight")


def cluster_palette(names: pd.Series) -> dict:
    """Map 'R1: ...', 'R2: ...' names to colors by risk rank."""
    return {n: RISK_COLORS[int(n.split(":")[0][1:]) - 1] for n in names.unique()}


def sorted_names(names: pd.Series) -> list:
    return sorted(names.unique(), key=lambda n: int(n.split(":")[0][1:]))


def profile_heatmap(states: pd.DataFrame, names: pd.Series, cols, title: str):
    """Standardized cluster means (rows = clusters ordered by risk)."""
    centers = standardize(states[cols]).groupby(names).mean().loc[sorted_names(names)]
    centers.columns = [label(c) for c in cols]
    fig, ax = plt.subplots(figsize=(13, 0.6 * len(centers) + 1.8))
    sns.heatmap(centers, cmap="RdBu_r", center=0, annot=True, fmt=".2f",
                annot_kws={"size": 8}, linewidths=0.4, ax=ax)
    ax.set_title(title)
    ax.set_ylabel("")
    plt.tight_layout()
    return fig


def pca_scatter(states: pd.DataFrame, X_pca: np.ndarray, explained, hue: pd.Series,
                palette: dict, title: str):
    """States in the PC1-PC2 plane with state abbreviations."""
    fig, ax = plt.subplots(figsize=(10, 6.5))
    order = sorted_names(hue) if str(hue.iloc[0]).startswith("R") else sorted(hue.unique())
    for group in order:
        mask = (hue == group).values
        ax.scatter(X_pca[mask, 0], X_pca[mask, 1], s=60, alpha=0.85,
                   color=palette[group], label=group)
    for (x, y), abbr in zip(X_pca[:, :2], states["LocationAbbr"]):
        ax.annotate(abbr, (x, y), fontsize=7, ha="center", va="bottom",
                    xytext=(0, 3), textcoords="offset points")
    ax.axhline(0, color="lightgray", lw=0.8)
    ax.axvline(0, color="lightgray", lw=0.8)
    ax.set_xlabel(f"PC1 ({explained[0] * 100:.1f}%)")
    ax.set_ylabel(f"PC2 ({explained[1] * 100:.1f}%)")
    ax.set_title(title)
    ax.legend(fontsize=8, loc="best")
    plt.tight_layout()
    return fig


def silhouette_plot(X: np.ndarray, labels: np.ndarray, names: pd.Series,
                    regions: pd.Series, title: str):
    """Per-state silhouette values grouped by cluster, colored by Census region."""
    values = silhouette_samples(X, labels)
    fig, ax = plt.subplots(figsize=(11, 7))
    y = 10
    for name in sorted_names(names):
        mask = (names == name).values
        order = np.argsort(values[mask])
        for i, (v, region) in enumerate(zip(values[mask][order], regions[mask].values[order])):
            ax.barh(y + i, v, height=0.85, color=REGION_PALETTE[region], alpha=0.8)
        ax.text(-0.02, y + mask.sum() / 2, name, ha="right", va="center", fontsize=9)
        y += mask.sum() + 6
    ax.axvline(values.mean(), color="red", ls="--", lw=1.5,
               label=f"średnia: {values.mean():.3f}")
    ax.set_yticks([])
    ax.set_xlabel("współczynnik sylwetki")
    ax.set_title(title)
    handles = [Patch(color=c, label=r) for r, c in REGION_PALETTE.items()]
    ax.legend(handles=handles + [ax.lines[0]], fontsize=8, loc="lower right")
    plt.tight_layout()
    return fig


def cluster_map(states: pd.DataFrame, names: pd.Series, title: str):
    df = states.assign(Klaster=names.values)
    fig = px.choropleth(
        df,
        locations="LocationAbbr",
        locationmode="USA-states",
        color="Klaster",
        color_discrete_map=cluster_palette(names),
        category_orders={"Klaster": sorted_names(names)},
        scope="usa",
        hover_name="LocationDesc",
        title=title,
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=50, b=0),
        legend=dict(title_text="", orientation="h", yanchor="top", y=0.0, x=0.0),
    )
    return fig
