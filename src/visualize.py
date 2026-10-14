"""Charts for the segmentation report (saved as PNG to reports/figures/).

Every chart uses the same fixed colour per segment, so a reader who learns
"Champions are blue" can rely on it across the whole report.
"""

from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.transforms  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.ticker import FuncFormatter, PercentFormatter  # noqa: E402

from src.config import FIGURES_DIR  # noqa: E402
from src.segment import SEGMENT_ORDER  # noqa: E402

logger = logging.getLogger(__name__)

# Palette: validated categorical order (blue, orange, aqua, yellow, magenta, ...).
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
NEUTRAL_MARK = "#d6d5ce"
CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6"]
SEQUENTIAL = LinearSegmentedColormap.from_list("blue", ["#f0efec", "#9ec5f4", "#2a78d6", "#0d366b"])
DIVERGING = LinearSegmentedColormap.from_list("div", ["#e34948", "#f0efec", "#2a78d6"])

DPI = 150


def segment_colors(segments: list[str]) -> dict[str, str]:
    """Fixed colour per segment, assigned in value order (never by rank)."""
    present = [s for s in SEGMENT_ORDER if s in segments]
    return {s: CATEGORICAL[i] for i, s in enumerate(present)}


def apply_style() -> None:
    """Set a clean, recessive matplotlib style shared by every chart."""
    plt.rcParams.update({
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"],
        "font.size": 10,
        "text.color": INK,
        "axes.labelcolor": INK_2,
        "axes.edgecolor": AXIS,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "xtick.labelcolor": INK_2,
        "ytick.labelcolor": INK_2,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.titlelocation": "left",
        "axes.titlepad": 12,
        "legend.frameon": False,
    })


def _title(fig: plt.Figure, title: str, subtitle: str) -> None:
    """Figure-level title and subtitle, left aligned."""
    fig.text(0.012, 0.985, title, fontsize=14, fontweight="bold", color=INK, va="top")
    fig.text(0.012, 0.935, subtitle, fontsize=10, color=INK_2, va="top")


def _save(fig: plt.Figure, name: str) -> Path:
    path = FIGURES_DIR / name
    fig.savefig(path, dpi=DPI, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    logger.info("Saved figure %s", path.name)
    return path


def _gbp(x: float, _pos=None) -> str:
    if abs(x) >= 1e6:
        return f"£{x / 1e6:.1f}M"
    if abs(x) >= 1e3:
        return f"£{x / 1e3:.0f}K"
    return f"£{x:.0f}"


# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------

def plot_elbow(ks: list[int], inertia: list[float], chosen_k: int) -> Path:
    """Inertia vs k with the automatically detected elbow marked."""
    fig, ax = plt.subplots(figsize=(8, 4.8))
    fig.subplots_adjust(top=0.80)
    ax.plot(ks, inertia, color=CATEGORICAL[0], lw=2, marker="o", ms=7,
            markeredgecolor=SURFACE, markeredgewidth=2)
    i = ks.index(chosen_k)
    ax.plot([ks[0], ks[-1]], [inertia[0], inertia[-1]], color=AXIS, lw=1)
    ax.scatter([chosen_k], [inertia[i]], s=160, facecolor="none", edgecolor=INK, lw=1.5, zorder=3)
    ax.annotate(f"Elbow: k = {chosen_k}", (chosen_k, inertia[i]), xytext=(18, 18),
                textcoords="offset points", fontsize=10, fontweight="bold", color=INK)
    ax.set_xticks(ks)
    ax.set_xlabel("Number of clusters (k)")
    ax.set_ylabel("Inertia (within-cluster sum of squares)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1e3:.0f}K"))
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    _title(fig, "Elbow method: diminishing returns after k = %d" % chosen_k,
           "K-means inertia for k = 2-10. Elbow = point furthest below the grey line joining the ends.")
    return _save(fig, "01_elbow.png")


def plot_silhouette(ks: list[int], sil: list[float], chosen_k: int) -> Path:
    """Silhouette score vs k with the chosen k highlighted."""
    fig, ax = plt.subplots(figsize=(8, 4.8))
    fig.subplots_adjust(top=0.80)
    colors = [CATEGORICAL[0] if k == chosen_k else NEUTRAL_MARK for k in ks]
    bars = ax.bar(ks, sil, color=colors, width=0.7, edgecolor=SURFACE, linewidth=2)
    for bar, s in zip(bars, sil):
        ax.text(bar.get_x() + bar.get_width() / 2, s + 0.004, f"{s:.2f}",
                ha="center", va="bottom", fontsize=9, color=INK_2)
    ax.set_xticks(ks)
    ax.set_xlabel("Number of clusters (k)")
    ax.set_ylabel("Mean silhouette score")
    ax.set_ylim(0, max(sil) * 1.18)
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    best = ks[int(np.argmax(sil))]
    tail = sil[ks.index(chosen_k) - 1:]
    _title(fig, f"Silhouette score: why k = {chosen_k}",
           f"Higher = better-separated clusters. k = {best} scores highest but only separates "
           f"engaged from disengaged customers - too coarse to act on.\n"
           f"k = {chosen_k} (blue) is the elbow; its score stays in the same "
           f"{min(tail):.2f}-{max(tail):.2f} band as k = {chosen_k - 1}-{ks[-1]}.")
    fig.subplots_adjust(top=0.76)
    return _save(fig, "02_silhouette.png")


# ---------------------------------------------------------------------------
# Segment overview
# ---------------------------------------------------------------------------

def plot_segment_share(summary: pd.DataFrame, colors: dict[str, str]) -> Path:
    """Share of customers vs share of revenue, as two 100% stacked bars."""
    fig, ax = plt.subplots(figsize=(10, 4.4))
    fig.subplots_adjust(top=0.74, bottom=0.22)
    rows = [("Share of customers", "pct_customers"), ("Share of revenue", "pct_revenue")]
    for y, (_, col) in enumerate(rows):
        left = 0.0
        for _, r in summary.iterrows():
            w = r[col]
            ax.barh(y, w, left=left, color=colors[r["segment"]], height=0.62,
                    edgecolor=SURFACE, linewidth=2)
            if w >= 5:
                ax.text(left + w / 2, y, f"{w:.0f}%", ha="center", va="center",
                        fontsize=10, fontweight="bold", color=INK)
            left += w
    ax.set_yticks(range(len(rows)), [r[0] for r in rows], fontsize=11, color=INK)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(PercentFormatter())
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    handles = [plt.Rectangle((0, 0), 1, 1, color=colors[s]) for s in summary["segment"]]
    ax.legend(handles, summary["segment"], loc="upper center", bbox_to_anchor=(0.5, -0.16),
              ncol=len(handles), fontsize=10, handlelength=1.2, columnspacing=1.6)
    top = summary.iloc[0]
    _title(fig, f"{top['pct_customers']:.0f}% of customers generate {top['pct_revenue']:.0f}% of revenue",
           f"{top['segment']} (blue) vs everyone else - share of the {summary['customers'].sum():,} "
           f"customers and £{summary['revenue_gbp'].sum() / 1e6:.1f}M revenue, Dec 2009 - Dec 2011")
    return _save(fig, "03_segment_share.png")


def plot_pareto(features: pd.DataFrame) -> tuple[Path, dict]:
    """Cumulative revenue share vs cumulative customer share (Pareto curve)."""
    m = features["Monetary"].sort_values(ascending=False).to_numpy()
    cum_rev = np.cumsum(m) / m.sum() * 100
    cum_cust = np.arange(1, len(m) + 1) / len(m) * 100
    stats = {f"top_{p}pct_customers_revenue_share": round(float(np.interp(p, cum_cust, cum_rev)), 1)
             for p in (1, 10, 20)}

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.subplots_adjust(top=0.82)
    ax.plot(cum_cust, cum_rev, color=CATEGORICAL[0], lw=2)
    ax.plot([0, 100], [0, 100], color=AXIS, lw=1)
    ax.text(62, 55, "if every customer\nspent the same", color=MUTED, fontsize=9, rotation=0)
    for p in (10, 20):
        v = stats[f"top_{p}pct_customers_revenue_share"]
        ax.plot([p, p, 0], [0, v, v], color=GRID, lw=1, zorder=0)
        ax.scatter([p], [v], s=50, color=CATEGORICAL[0], edgecolor=SURFACE, lw=2, zorder=3)
        ax.annotate(f"Top {p}% of customers\n= {v:.0f}% of revenue", (p, v),
                    xytext=(14, -30 if p == 10 else -34), textcoords="offset points",
                    fontsize=10, color=INK)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 102)
    ax.xaxis.set_major_formatter(PercentFormatter())
    ax.yaxis.set_major_formatter(PercentFormatter())
    ax.set_xlabel("Customers, ranked from highest to lowest spend")
    ax.set_ylabel("Cumulative share of revenue")
    _title(fig, "Revenue is highly concentrated",
           f"Top 20% of customers account for {stats['top_20pct_customers_revenue_share']:.0f}% "
           "of all revenue")
    return _save(fig, "04_revenue_concentration.png"), stats


def plot_profiles(summary: pd.DataFrame, centroids: pd.DataFrame) -> Path:
    """Heatmap of segment profiles: colour = vs average customer, text = median value."""
    cols = [
        ("Recency", "median_recency_days", "Days since\nlast order", lambda v: f"{v:.0f}"),
        ("Frequency", "median_frequency_orders", "Orders", lambda v: f"{v:.0f}"),
        ("Monetary", "median_monetary_gbp", "Total spend", lambda v: f"£{v:,.0f}"),
        ("AvgOrderValue", "avg_order_value_gbp", "Avg order\nvalue", lambda v: f"£{v:,.0f}"),
        ("DistinctProducts", "avg_distinct_products", "Distinct\nproducts", lambda v: f"{v:.0f}"),
        ("TenureDays", "avg_tenure_days", "Days since\nfirst order", lambda v: f"{v:.0f}"),
    ]
    seg = summary["segment"].tolist()
    scores = centroids.loc[seg, [c[0] for c in cols]].copy()
    scores["Recency"] *= -1  # fewer days since last order = better
    z = scores.clip(-1.8, 1.8).to_numpy()

    fig, ax = plt.subplots(figsize=(10, 5.2))
    fig.subplots_adjust(top=0.80, left=0.17)
    ax.imshow(z, cmap=DIVERGING, vmin=-1.8, vmax=1.8, aspect="auto")
    for i, s in enumerate(seg):
        row = summary.set_index("segment").loc[s]
        for j, (_, src, _, fmt) in enumerate(cols):
            ax.text(j, i, fmt(row[src]), ha="center", va="center", fontsize=10.5,
                    color=INK, fontweight="bold" if abs(z[i, j]) > 1 else "normal")
    ax.set_xticks(range(len(cols)), [c[2] for c in cols], fontsize=10, color=INK)
    ax.set_yticks(range(len(seg)), [f"{s}\n({n:,})" for s, n in zip(seg, summary["customers"])],
                  fontsize=10, color=INK)
    ax.xaxis.tick_top()
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks(np.arange(-0.5, len(cols)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(seg)), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=3)
    ax.tick_params(which="minor", length=0)
    _title(fig, "Segment profiles",
           "Values: median (recency, orders, spend) or mean (others) per segment.  "
           "Colour: blue = better than the average customer, red = worse.")
    return _save(fig, "05_segment_profiles.png")


def plot_pca(pcs: np.ndarray, explained: np.ndarray, segments: pd.Series,
             colors: dict[str, str]) -> Path:
    """Small multiples of the 2D PCA projection, one panel per segment."""
    order = [s for s in SEGMENT_ORDER if s in colors]
    n = len(order) + 1
    ncols = 3
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(12, 4 * nrows), sharex=True, sharey=True)
    axes = axes.ravel()
    seg = segments.to_numpy()
    rng = np.random.default_rng(0)
    idx = rng.permutation(len(seg))

    for ax, s in zip(axes, order):
        mask = seg == s
        ax.scatter(pcs[~mask, 0], pcs[~mask, 1], s=4, color=NEUTRAL_MARK, alpha=0.6, linewidths=0)
        ax.scatter(pcs[mask, 0], pcs[mask, 1], s=6, color=colors[s], alpha=0.7, linewidths=0)
        ax.set_title(f"{s}  ({mask.sum():,})", fontsize=11, color=INK)

    ax = axes[len(order)]
    ax.scatter(pcs[idx, 0], pcs[idx, 1], s=4, color=NEUTRAL_MARK, alpha=0.6, linewidths=0)
    for s in order:
        cx, cy = pcs[seg == s].mean(axis=0)
        ax.scatter([cx], [cy], s=110, color=colors[s], edgecolor=SURFACE, linewidth=2, zorder=3)
    _place_labels_without_overlap(ax, [(s, *pcs[seg == s].mean(axis=0)) for s in order])
    ax.set_title("Segment centres", fontsize=11, color=INK)
    for extra in axes[n:]:
        extra.set_visible(False)
    for ax in axes[:n]:
        ax.tick_params(labelsize=8)
    for ax in axes[(nrows - 1) * ncols:n]:
        ax.set_xlabel(f"PC1 ({explained[0]:.0%} of variance)")
    for ax in axes[::ncols]:
        ax.set_ylabel(f"PC2 ({explained[1]:.0%} of variance)")
    fig.subplots_adjust(top=0.86, hspace=0.32, wspace=0.08)
    _title(fig, "Customers in 2D (PCA projection of the six features)",
           f"PC1 = customer value (right = more orders, spend and products). "
           f"PC2 = customer age (up = longer since first and last order). "
           f"Together they explain {explained[:2].sum():.0%} of the variance.")
    return _save(fig, "06_pca_segments.png")


def _place_labels_without_overlap(ax: plt.Axes, points: list[tuple[str, float, float]]) -> None:
    """Label each point, trying positions around it until no label overlaps another
    label or marker."""
    candidates = [((0, 11), "center", "bottom"), ((0, -11), "center", "top"),
                  ((10, 0), "left", "center"), ((-10, 0), "right", "center")]
    fig = ax.figure
    renderer = fig.canvas.get_renderer()
    marker_boxes = []
    for _, x, y in points:
        px, py = ax.transData.transform((x, y))
        marker_boxes.append(matplotlib.transforms.Bbox([[px - 8, py - 8], [px + 8, py + 8]]))
    placed = []
    for i, (name, x, y) in enumerate(points):
        for offset, ha, va in candidates:
            t = ax.annotate(name, (x, y), xytext=offset, textcoords="offset points", ha=ha,
                            va=va, fontsize=9.5, fontweight="bold", color=INK)
            bb = t.get_window_extent(renderer).expanded(1.05, 1.15)
            others = placed + [b for j, b in enumerate(marker_boxes) if j != i]
            if not any(bb.overlaps(o) for o in others):
                placed.append(bb)
                break
            t.remove()
        else:  # nothing fits: keep the first position
            t = ax.annotate(name, (x, y), xytext=candidates[0][0], textcoords="offset points",
                            ha="center", va="bottom", fontsize=9.5, fontweight="bold", color=INK)


def plot_revenue_over_time(transactions: pd.DataFrame, segments: pd.Series,
                           colors: dict[str, str]) -> Path:
    """Monthly revenue per segment (incomplete final month excluded)."""
    tx = transactions[["InvoiceDate", "CustomerID", "Revenue"]].copy()
    tx["Segment"] = tx["CustomerID"].map(segments)
    tx["Month"] = tx["InvoiceDate"].dt.to_period("M")
    last_month = tx["Month"].max()
    tx = tx[tx["Month"] < last_month]  # final month only covers its first few days
    monthly = tx.pivot_table(index="Month", columns="Segment", values="Revenue",
                             aggfunc="sum", fill_value=0)
    monthly.index = monthly.index.to_timestamp()
    order = [s for s in SEGMENT_ORDER if s in monthly.columns]

    fig, ax = plt.subplots(figsize=(11, 5.4))
    fig.subplots_adjust(top=0.84, right=0.82)
    for s in order:
        ax.plot(monthly.index, monthly[s], color=colors[s], lw=2, label=s)
        ax.annotate(s, (monthly.index[-1], monthly[s].iloc[-1]), xytext=(8, 0),
                    textcoords="offset points", va="center", fontsize=9.5, color=INK)
    _spread_end_labels(ax)
    ax.yaxis.set_major_formatter(FuncFormatter(_gbp))
    ax.set_ylabel("Monthly revenue")
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.set_ylim(bottom=0)
    ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%b %Y"))
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), fontsize=9.5, ncol=len(order))
    fig.subplots_adjust(bottom=0.2)
    _title(fig, "Monthly revenue by segment",
           "Champions drive the pre-Christmas peaks. Lapsed customers went quiet after "
           "Nov 2010, while New Customers grew through 2011.\n"
           f"({last_month.strftime('%b %Y')} excluded: only partially covered by the data)")
    fig.subplots_adjust(top=0.82)
    return _save(fig, "07_revenue_over_time.png")


def _spread_end_labels(ax: plt.Axes, min_gap_frac: float = 0.045) -> None:
    """Nudge right-hand line labels apart so they never overlap."""
    labels = [t for t in ax.texts]
    if not labels:
        return
    fig = ax.figure
    fig.canvas.draw()
    lo, hi = ax.get_ylim()
    gap = (hi - lo) * min_gap_frac
    labels.sort(key=lambda t: t.xy[1])
    ys = [t.xy[1] for t in labels]
    for i in range(1, len(ys)):
        ys[i] = max(ys[i], ys[i - 1] + gap)
    for t, y in zip(labels, ys):
        t.xy = (t.xy[0], y)


def plot_method_comparison(kmeans_segments: pd.Series, gmm_labels: np.ndarray,
                           ari: float) -> Path:
    """Row-normalised crosstab: where each K-means segment lands under GMM."""
    order = [s for s in SEGMENT_ORDER if s in set(kmeans_segments)]
    ct = pd.crosstab(kmeans_segments.to_numpy(), gmm_labels, normalize="index").loc[order] * 100
    # Order GMM components by the K-means segment they overlap most, for a readable diagonal.
    comp_order = sorted(ct.columns, key=lambda c: (order.index(ct[c].idxmax()), -ct[c].max()))
    ct = ct[comp_order]

    fig, ax = plt.subplots(figsize=(9, 4.8))
    fig.subplots_adjust(top=0.78, left=0.2)
    ax.imshow(ct.to_numpy(), cmap=SEQUENTIAL, vmin=0, vmax=100, aspect="auto")
    for i in range(ct.shape[0]):
        for j in range(ct.shape[1]):
            v = ct.iat[i, j]
            ax.text(j, i, f"{v:.0f}%", ha="center", va="center", fontsize=10,
                    color=SURFACE if v > 55 else INK)
    ax.set_xticks(range(ct.shape[1]), [f"GMM {k + 1}" for k in range(ct.shape[1])])
    ax.set_yticks(range(len(order)), order, color=INK)
    ax.set_xlabel("Gaussian Mixture component")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks(np.arange(-0.5, ct.shape[1]), minor=True)
    ax.set_yticks(np.arange(-0.5, len(order)), minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=3)
    ax.tick_params(which="minor", length=0)
    _title(fig, "K-means vs Gaussian Mixture",
           f"Share of each K-means segment assigned to each GMM component "
           f"(rows sum to 100%). Adjusted Rand index = {ari:.2f}")
    return _save(fig, "08_kmeans_vs_gmm.png")
