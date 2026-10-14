"""Cluster customers, choose k, compare methods and name the segments.

Choosing k
----------
For every k in ``K_RANGE`` we fit K-means and record inertia (within-cluster
sum of squares) and the silhouette score. The elbow is located
automatically as the point of the inertia curve furthest from the straight
line joining its endpoints (the "kneedle" idea), so the choice is
reproducible rather than eyeballed. The silhouette curve is used as a
sanity check: the chosen k must still show clear structure (silhouette
>= ``MIN_SILHOUETTE``).

Naming
------
K-means labels are arbitrary integers, so each cluster is matched to a
business archetype (Champions, New Customers, ...) by comparing its
centroid with an archetype profile on recency, frequency, monetary value and
tenure. The matching is a one-to-one assignment (Hungarian algorithm), so
names are unique and do not depend on label order.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.cluster import KMeans
from sklearn.metrics import (
    adjusted_rand_score, calinski_harabasz_score, davies_bouldin_score, silhouette_score,
)
from sklearn.mixture import GaussianMixture

from src.config import K_RANGE, RANDOM_SEED

logger = logging.getLogger(__name__)

MIN_SILHOUETTE = 0.20
N_INIT = 20
STABILITY_SEEDS = [0, 1, 2, 3, 4]

# Archetype profiles in standardised units (+ = better than the average
# customer). "Recency" is sign-flipped so that + means "bought recently".
ARCHETYPES = pd.DataFrame(
    {
        #                        Recency  Frequency  Monetary  TenureDays
        "Champions":            [ 1.0,     1.5,       1.5,      0.8],
        "Loyal Customers":      [ 0.4,     0.4,       0.4,      0.4],
        "New Customers":        [ 0.6,    -0.6,      -0.5,     -1.5],
        "Promising Customers":  [ 0.6,     0.0,       0.3,     -1.0],
        "At-Risk Big Spenders": [-0.8,     0.8,       1.0,      0.6],
        "Lapsed Customers":     [-1.2,    -0.4,      -0.3,      0.3],
        "Lost Customers":       [-1.2,    -1.0,      -1.2,      0.0],
    },
    index=["Recency", "Frequency", "Monetary", "TenureDays"],
).T

# Display order (most to least valuable) - also fixes each segment's colour.
SEGMENT_ORDER = [
    "Champions", "Loyal Customers", "At-Risk Big Spenders", "Promising Customers",
    "New Customers", "Lapsed Customers", "Lost Customers",
]

RECOMMENDATIONS = {
    "Champions": (
        "Protect and grow: VIP tier with early access to new ranges, a named account "
        "manager for the top accounts, referral rewards. Avoid blanket discounts - "
        "they already buy at full price."
    ),
    "Loyal Customers": (
        "Upgrade to Champions: personalised cross-sell from purchase history, volume-tier "
        "pricing and a points scheme that rewards order frequency."
    ),
    "Promising Customers": (
        "Build the habit: replenishment reminders and curated bundles timed to their "
        "re-order cycle."
    ),
    "New Customers": (
        "Win the second order: 3-email welcome series with best-sellers and a time-limited "
        "incentive on a second purchase within 30-60 days."
    ),
    "At-Risk Big Spenders": (
        "Personal outreach: account-manager call or tailored offer before they churn; "
        "ask what changed."
    ),
    "Lapsed Customers": (
        "Win-back campaign: 'we miss you' email with the new catalogue and one strong "
        "one-time offer; short survey on why they stopped; suppress after 2-3 unanswered "
        "touches."
    ),
    "Lost Customers": (
        "Low-cost reactivation only: include in the seasonal (pre-Christmas) newsletter, "
        "no paid-media spend; drop from active lists if they stay unengaged."
    ),
}


@dataclass
class KSelection:
    """Results of the elbow / silhouette search."""

    ks: list[int]
    inertia: list[float]
    silhouette: list[float]
    elbow_k: int
    best_silhouette_k: int
    chosen_k: int


def find_elbow(ks: list[int], inertia: list[float]) -> int:
    """Return the k whose (normalised) inertia is furthest below the endpoint chord."""
    x = (np.asarray(ks) - ks[0]) / (ks[-1] - ks[0])
    y = (np.asarray(inertia) - min(inertia)) / (max(inertia) - min(inertia))
    distance = (1 - x) - y  # chord from (0, 1) to (1, 0) is y = 1 - x
    return int(ks[int(np.argmax(distance))])


def select_k(X: pd.DataFrame) -> KSelection:
    """Evaluate K-means over ``K_RANGE`` and pick k at the elbow."""
    ks, inertia, sil = [], [], []
    for k in K_RANGE:
        model = KMeans(n_clusters=k, n_init=N_INIT, random_state=RANDOM_SEED).fit(X)
        ks.append(k)
        inertia.append(float(model.inertia_))
        sil.append(float(silhouette_score(X, model.labels_)))
        logger.info("k=%2d  inertia=%9.0f  silhouette=%.3f", k, inertia[-1], sil[-1])

    elbow_k = find_elbow(ks, inertia)
    chosen_sil = sil[ks.index(elbow_k)]
    if chosen_sil < MIN_SILHOUETTE:
        raise RuntimeError(
            f"Silhouette at the elbow (k={elbow_k}) is {chosen_sil:.3f} < {MIN_SILHOUETTE}; "
            "clusters are not well separated - revisit the features."
        )
    best_sil_k = ks[int(np.argmax(sil))]
    logger.info("Elbow at k=%d (silhouette %.3f); best silhouette at k=%d",
                elbow_k, chosen_sil, best_sil_k)
    return KSelection(ks, inertia, sil, elbow_k, best_sil_k, chosen_k=elbow_k)


def name_clusters(X: pd.DataFrame, labels: np.ndarray) -> dict[int, str]:
    """Map each cluster label to a unique business name."""
    centroids = X[ARCHETYPES.columns].groupby(labels).mean()
    centroids["Recency"] *= -1  # + now means "more recent"
    if len(centroids) > len(ARCHETYPES):
        raise ValueError(f"Only {len(ARCHETYPES)} archetypes for {len(centroids)} clusters")
    cost = ((centroids.values[:, None, :] - ARCHETYPES.values[None, :, :]) ** 2).sum(axis=2)
    rows, cols = linear_sum_assignment(cost)
    return {int(centroids.index[r]): ARCHETYPES.index[c] for r, c in zip(rows, cols)}


def cluster_metrics(X: pd.DataFrame, labels: np.ndarray) -> dict:
    """Standard internal validation metrics for one labelling."""
    return {
        "silhouette": round(float(silhouette_score(X, labels)), 3),
        "davies_bouldin": round(float(davies_bouldin_score(X, labels)), 3),
        "calinski_harabasz": round(float(calinski_harabasz_score(X, labels)), 1),
    }


def fit_kmeans(X: pd.DataFrame, k: int) -> tuple[KMeans, dict]:
    """Fit the final K-means model and measure stability across random seeds."""
    model = KMeans(n_clusters=k, n_init=N_INIT, random_state=RANDOM_SEED).fit(X)
    stability = [
        adjusted_rand_score(
            model.labels_,
            KMeans(n_clusters=k, n_init=N_INIT, random_state=seed).fit_predict(X),
        )
        for seed in STABILITY_SEEDS
    ]
    metrics = cluster_metrics(X, model.labels_)
    metrics["stability_ari_min_across_seeds"] = round(float(min(stability)), 3)
    return model, metrics


def compare_gmm(X: pd.DataFrame, k: int, kmeans_labels: np.ndarray) -> tuple[np.ndarray, dict]:
    """Fit a Gaussian Mixture with the same k and compare it with K-means."""
    gmm = GaussianMixture(
        n_components=k, covariance_type="full", n_init=5, random_state=RANDOM_SEED
    ).fit(X)
    labels = gmm.predict(X)
    metrics = cluster_metrics(X, labels)
    metrics["bic"] = round(float(gmm.bic(X)), 1)
    metrics["adjusted_rand_index_vs_kmeans"] = round(float(adjusted_rand_score(kmeans_labels, labels)), 3)
    metrics["cluster_sizes"] = sorted(np.bincount(labels).tolist(), reverse=True)
    return labels, metrics


def summarise_segments(features: pd.DataFrame, segments: pd.Series) -> pd.DataFrame:
    """One row per segment: size, revenue share, average profile and action."""
    df = features.assign(Segment=segments)
    g = df.groupby("Segment")
    summary = pd.DataFrame({
        "customers": g.size(),
        "revenue_gbp": g["Monetary"].sum().round(0),
        "avg_recency_days": g["Recency"].mean().round(1),
        "avg_frequency_orders": g["Frequency"].mean().round(1),
        "avg_monetary_gbp": g["Monetary"].mean().round(0),
        "median_recency_days": g["Recency"].median(),
        "median_frequency_orders": g["Frequency"].median(),
        "median_monetary_gbp": g["Monetary"].median().round(0),
        "avg_order_value_gbp": g["AvgOrderValue"].mean().round(0),
        "avg_distinct_products": g["DistinctProducts"].mean().round(0),
        "avg_tenure_days": g["TenureDays"].mean().round(0),
    })
    summary.insert(1, "pct_customers", (100 * summary["customers"] / summary["customers"].sum()).round(1))
    summary.insert(3, "pct_revenue", (100 * summary["revenue_gbp"] / summary["revenue_gbp"].sum()).round(1))
    summary["recommended_action"] = summary.index.map(RECOMMENDATIONS)
    order = [s for s in SEGMENT_ORDER if s in summary.index]
    return summary.loc[order].rename_axis("segment").reset_index()
