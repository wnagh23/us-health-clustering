"""PCA, the three clustering methods, data-driven cluster names and validation."""

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, davies_bouldin_score, silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from .data import label

SEED = 42

# Variables that define the "health risk" axis used to order clusters
RISK_UP = ["Obesity", "NoActivity", "pct_ubostwo_rodzin", "pct_bez_ubezpieczenia"]
RISK_DOWN = ["HighActivity", "mediana_dochodu_gosp_dom", "pct_wyksztalcenie_wyzsze"]


def fit_pca(X: np.ndarray, n_components: int = 2):
    """Standardize, fit full PCA, return (X_scaled, X_pca_all, pca)."""
    X_scaled = StandardScaler().fit_transform(X)
    pca = PCA(random_state=SEED).fit(X_scaled)
    return X_scaled, pca.transform(X_scaled), pca


def hierarchical(X: np.ndarray, k: int) -> np.ndarray:
    return fcluster(linkage(X, method="ward"), k, criterion="maxclust") - 1


# Several initialisations per fit: with a single/few starts both models land in
# different local optima depending on the seed (checked in notebook 01, section 9).
def gmm(X: np.ndarray, k: int, covariance_type: str = "tied", seed: int = SEED) -> np.ndarray:
    return GaussianMixture(
        k, covariance_type=covariance_type, random_state=seed, n_init=100
    ).fit_predict(X)


def kmeans(X: np.ndarray, k: int, seed: int = SEED) -> np.ndarray:
    return KMeans(k, random_state=seed, n_init=50).fit_predict(X)


def cluster_names(states: pd.DataFrame, labels: np.ndarray, cols, suffix: str = "") -> pd.Series:
    """Name clusters from their profiles instead of hard-coding cluster ids.

    Clusters are ranked by a risk score (mean z-score of RISK_UP minus RISK_DOWN)
    and described by the two features that deviate most from the overall mean.
    Names therefore stay correct when cluster ids change (other seed, period, data).
    suffix: appended to the risk variable names (e.g. "_mean" for trend features).
    """
    z = (states[cols] - states[cols].mean()) / states[cols].std()
    centers = z.groupby(labels).mean()
    up = [c + suffix for c in RISK_UP]
    down = [c + suffix for c in RISK_DOWN]
    risk = centers[up].mean(axis=1) - centers[down].mean(axis=1)
    order = risk.sort_values(ascending=False).index

    names = {}
    for rank, cluster in enumerate(order, start=1):
        top = centers.loc[cluster].abs().nlargest(2).index
        traits = ", ".join(
            f"{label(c).replace(' %', '')} {'↑' if centers.loc[cluster, c] > 0 else '↓'}"
            for c in top
        )
        names[cluster] = f"R{rank}: {traits}"
    return pd.Series(labels, index=states.index).map(names)


def scores(X: np.ndarray, labels: np.ndarray) -> dict:
    return {
        "silhouette": silhouette_score(X, labels),
        "davies_bouldin": davies_bouldin_score(X, labels),
        "n_clusters": len(np.unique(labels)),
    }


def k_sweep(X_pca2: np.ndarray, X_full: np.ndarray, ks=range(2, 9)) -> pd.DataFrame:
    """Silhouette for every method/k in the 2D PCA space and in the full feature space,
    plus GMM BIC (lower = better)."""
    rows = []
    for k in ks:
        row = {"k": k}
        for space, X in [("pca2", X_pca2), ("full", X_full)]:
            row[f"sil_ward_{space}"] = silhouette_score(X, hierarchical(X, k))
            row[f"sil_kmeans_{space}"] = silhouette_score(X, kmeans(X, k))
        row["sil_gmm_pca2"] = silhouette_score(X_pca2, gmm(X_pca2, k))
        row["bic_gmm_pca2"] = (
            GaussianMixture(k, covariance_type="tied", random_state=SEED, n_init=5)
            .fit(X_pca2)
            .bic(X_pca2)
        )
        row["bic_gmm_full"] = (
            GaussianMixture(k, covariance_type="diag", random_state=SEED, n_init=5)
            .fit(X_full)
            .bic(X_full)
        )
        rows.append(row)
    return pd.DataFrame(rows).set_index("k").round(3)


def agreement(labelings: dict) -> pd.DataFrame:
    """Pairwise Adjusted Rand Index between labelings (1 = identical partitions)."""
    names = list(labelings)
    return pd.DataFrame(
        [[adjusted_rand_score(labelings[a], labelings[b]) for b in names] for a in names],
        index=names,
        columns=names,
    ).round(2)


def seed_stability(X: np.ndarray, k: int, n_seeds: int = 100) -> pd.DataFrame:
    """ARI of each re-run (different random_state) against the seed=42 solution."""
    ref_km, ref_gmm = kmeans(X, k), gmm(X, k)
    rows = [
        {
            "seed": s,
            "kmeans": adjusted_rand_score(ref_km, kmeans(X, k, seed=s)),
            "gmm": adjusted_rand_score(ref_gmm, gmm(X, k, seed=s)),
        }
        for s in range(n_seeds)
    ]
    return pd.DataFrame(rows).set_index("seed")


def bootstrap_stability(X_raw: np.ndarray, reference: dict, n_boot: int = 100) -> pd.DataFrame:
    """Resample states with replacement, refit scaler + PCA(2) + model, and compare
    the labels of the original states with the reference solution (ARI).

    reference: {"ward": labels, "gmm": labels, "kmeans": labels}
    """
    rng = np.random.default_rng(SEED)
    k = {name: len(np.unique(lab)) for name, lab in reference.items()}
    rows = []
    for b in range(n_boot):
        idx = rng.choice(len(X_raw), len(X_raw), replace=True)
        scaler = StandardScaler().fit(X_raw[idx])
        pca = PCA(2).fit(scaler.transform(X_raw[idx]))
        X_boot = pca.transform(scaler.transform(X_raw[idx]))
        X_all = pca.transform(scaler.transform(X_raw))
        uniq = np.unique(idx)
        ward = AgglomerativeClustering(k["ward"], linkage="ward").fit_predict(X_all[uniq])
        km = KMeans(k["kmeans"], n_init=50, random_state=b).fit(X_boot).predict(X_all)
        gm = GaussianMixture(k["gmm"], covariance_type="tied", random_state=b, n_init=20).fit(X_boot)
        rows.append(
            {
                "ward": adjusted_rand_score(reference["ward"][uniq], ward),
                "kmeans": adjusted_rand_score(reference["kmeans"], km),
                "gmm": adjusted_rand_score(reference["gmm"], gm.predict(X_all)),
            }
        )
    return pd.DataFrame(rows)
