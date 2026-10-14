"""Run the full customer segmentation pipeline end to end.

    python run_pipeline.py

Steps: download (if needed) -> clean -> features -> choose k -> cluster ->
name segments -> compare with GMM -> charts -> summary CSV + metrics JSON.
"""

from __future__ import annotations

import json
import logging
import random
import time

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from src import clean, features, segment, visualize
from src.config import (
    FIGURES_DIR, METRICS_JSON, PROCESSED_DIR, RANDOM_SEED, SEGMENT_SUMMARY_CSV, SEGMENTS_CSV,
)
from src.download_data import download

logger = logging.getLogger("pipeline")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s",
                        datefmt="%H:%M:%S")
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    start = time.time()
    for d in (PROCESSED_DIR, FIGURES_DIR):
        d.mkdir(parents=True, exist_ok=True)

    logger.info("== 1/6 Data ==")
    download()

    logger.info("== 2/6 Cleaning ==")
    tx = clean.run()

    logger.info("== 3/6 Features ==")
    feats, X, log_cols, skew = features.run(tx)

    logger.info("== 4/6 Choosing k ==")
    sel = segment.select_k(X)

    logger.info("== 5/6 Clustering (k=%d) ==", sel.chosen_k)
    km, km_metrics = segment.fit_kmeans(X, sel.chosen_k)
    names = segment.name_clusters(X, km.labels_)
    segments = pd.Series(km.labels_, index=X.index, name="Segment").map(names)
    gmm_labels, gmm_metrics = segment.compare_gmm(X, sel.chosen_k, km.labels_)
    summary = segment.summarise_segments(feats, segments)

    out = feats.join(segments).reset_index()
    out[["CustomerID", "Segment"] + features.FEATURE_COLUMNS].round(2).to_csv(SEGMENTS_CSV, index=False)
    summary.to_csv(SEGMENT_SUMMARY_CSV, index=False)

    logger.info("== 6/6 Charts ==")
    visualize.apply_style()
    colors = visualize.segment_colors(summary["segment"].tolist())
    centroids = X.groupby(segments).mean()
    pca = PCA(n_components=2, random_state=RANDOM_SEED)
    pcs = pca.fit_transform(X)
    # Orient PC1 so that "right = more valuable" (sign of a PCA axis is arbitrary).
    if np.corrcoef(pcs[:, 0], X["Monetary"])[0, 1] < 0:
        pcs[:, 0] *= -1

    visualize.plot_elbow(sel.ks, sel.inertia, sel.chosen_k)
    visualize.plot_silhouette(sel.ks, sel.silhouette, sel.chosen_k)
    visualize.plot_segment_share(summary, colors)
    _, pareto = visualize.plot_pareto(feats)
    visualize.plot_profiles(summary, centroids)
    visualize.plot_pca(pcs, pca.explained_variance_ratio_, segments, colors)
    visualize.plot_revenue_over_time(tx, segments, colors)
    visualize.plot_method_comparison(segments, gmm_labels, gmm_metrics["adjusted_rand_index_vs_kmeans"])

    metrics = {
        "data": {
            "clean_transactions": len(tx),
            "customers": int(feats.shape[0]),
            "invoices": int(tx["Invoice"].nunique()),
            "products": int(tx["StockCode"].nunique()),
            "period_start": f"{tx['InvoiceDate'].min():%Y-%m-%d}",
            "period_end": f"{tx['InvoiceDate'].max():%Y-%m-%d}",
            "snapshot_date": f"{features.snapshot_date(tx):%Y-%m-%d}",
            "total_revenue_gbp": round(float(tx["Revenue"].sum()), 2),
        },
        "features": {
            "used": features.FEATURE_COLUMNS,
            "log_transformed": log_cols,
            "skewness_before_after_log": skew,
            "scaling": "StandardScaler (zero mean, unit variance)",
        },
        "k_selection": {
            "k_range": sel.ks,
            "inertia": [round(v, 1) for v in sel.inertia],
            "silhouette": [round(v, 3) for v in sel.silhouette],
            "elbow_k": sel.elbow_k,
            "best_silhouette_k": sel.best_silhouette_k,
            "chosen_k": sel.chosen_k,
            "rule": "elbow (max distance below endpoint chord), silhouette must be >= "
                    f"{segment.MIN_SILHOUETTE}",
        },
        "kmeans": km_metrics,
        "gaussian_mixture": gmm_metrics,
        "pca_explained_variance": [round(float(v), 3) for v in pca.explained_variance_ratio_],
        "revenue_concentration": pareto,
        "segments": {
            r["segment"]: {"customers": int(r["customers"]), "pct_customers": r["pct_customers"],
                           "pct_revenue": r["pct_revenue"]}
            for _, r in summary.iterrows()
        },
        "random_seed": RANDOM_SEED,
    }
    METRICS_JSON.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    pd.set_option("display.width", 200)
    print("\n" + summary.drop(columns="recommended_action").to_string(index=False))
    logger.info("Done in %.0fs. Outputs: %s, %s, %s, %s", time.time() - start,
                SEGMENT_SUMMARY_CSV.name, SEGMENTS_CSV.name, METRICS_JSON.name, FIGURES_DIR.name)


if __name__ == "__main__":
    main()
