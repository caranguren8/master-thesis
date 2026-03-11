#!/usr/bin/env python3
"""
Generate publication-quality figures for the master thesis.
All figures use a consistent academic style suitable for a thesis document.

Figures produced:
  1. fig1_rdd_runs_next.png     – RDD scatter: Runs in Next Election
  2. fig2_rdd_wins_next.png     – RDD scatter: Wins Seat in Next Election
  3. fig3_first_stage.png       – First-stage: Elected vs Running Variable
  4. fig4_density_test.png      – McCrary density histogram + local-linear
  5. fig5_bandwidth_sensitivity.png – BW sensitivity with 95% CIs
  6. fig6_covariate_balance.png – Balance test coefficient plot
"""

import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# ── Consistent thesis style ──────────────────────────────────────────────
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 10,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
})

LEFT_COLOR  = "#2166AC"   # blue
RIGHT_COLOR = "#B2182B"   # red
GREY        = "#888888"
LIGHT_GREY  = "#DDDDDD"

# ── Helpers ──────────────────────────────────────────────────────────────

def _bin_scatter(x, y, n_bins=15):
    """Return bin midpoints and bin means for a binned scatter."""
    finite = np.isfinite(x) & np.isfinite(y)
    x, y = x[finite], y[finite]
    edges = np.linspace(x.min(), x.max(), n_bins + 1)
    mids, means = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (x >= lo) & (x < hi) if hi < edges[-1] else (x >= lo) & (x <= hi)
        if mask.sum() > 0:
            mids.append((lo + hi) / 2)
            means.append(y[mask].mean())
    return np.array(mids), np.array(means)


def _local_linear(x, y, bw):
    """Triangular-kernel local-linear fit, returns (x_grid, y_hat)."""
    from numpy.linalg import lstsq
    grid = np.linspace(x.min(), x.max(), 200)
    y_hat = np.full_like(grid, np.nan)
    for i, x0 in enumerate(grid):
        w = np.maximum(1 - np.abs(x - x0) / bw, 0)
        if w.sum() < 3:
            continue
        X = np.column_stack([np.ones_like(x), x - x0])
        W = np.diag(w)
        try:
            beta = lstsq(W @ X, W @ y, rcond=None)[0]
            y_hat[i] = beta[0]
        except Exception:
            pass
    return grid, y_hat


# ── Figure builders ──────────────────────────────────────────────────────

def make_rdd_scatter(df, outcome_col, bw, title, ylabel, outpath):
    """Binned scatter with local-linear fit on each side of cutoff."""
    window = df[df["running_variable"].between(-bw, bw)].copy()
    window = window.dropna(subset=[outcome_col, "running_variable"])

    x = window["running_variable"].values.astype(float)
    y = window[outcome_col].values.astype(float)

    left  = x < 0
    right = x >= 0

    fig, ax = plt.subplots(figsize=(6, 4.5))

    # Binned scatter
    for mask, color, label in [(left, LEFT_COLOR, "Below cutoff"),
                                (right, RIGHT_COLOR, "Above cutoff")]:
        if mask.sum() < 5:
            continue
        mids, means = _bin_scatter(x[mask], y[mask], n_bins=15)
        ax.scatter(mids, means, c=color, s=40, zorder=5, alpha=0.8,
                   edgecolors="white", linewidths=0.5, label=label)

    # Local-linear fit
    for mask, color in [(left, LEFT_COLOR), (right, RIGHT_COLOR)]:
        if mask.sum() < 10:
            continue
        xg, yh = _local_linear(x[mask], y[mask], bw)
        valid = np.isfinite(yh)
        ax.plot(xg[valid], yh[valid], color=color, linewidth=2, zorder=4)

    ax.axvline(0, color="black", linewidth=0.8, linestyle="--", zorder=3)

    ax.set_xlabel("Running Variable (Vote Margin / Eligible Voters)")
    ax.set_ylabel(ylabel)
    ax.set_title(title, fontweight="bold")
    ax.legend(loc="best", framealpha=0.9)

    fig.tight_layout()
    fig.savefig(outpath)
    plt.close(fig)
    print(f"  ✓ {outpath}")


def make_first_stage(df, bw, outpath):
    """First-stage plot: elected_dta vs running variable."""
    window = df[df["running_variable"].between(-bw, bw)].copy()
    window = window.dropna(subset=["elected_dta", "running_variable"])

    x = window["running_variable"].values.astype(float)
    y = window["elected_dta"].values.astype(float)

    left  = x < 0
    right = x >= 0

    fig, ax = plt.subplots(figsize=(6, 4.5))

    for mask, color, label in [(left, LEFT_COLOR, "Below cutoff"),
                                (right, RIGHT_COLOR, "Above cutoff")]:
        if mask.sum() < 5:
            continue
        mids, means = _bin_scatter(x[mask], y[mask], n_bins=15)
        ax.scatter(mids, means, c=color, s=40, zorder=5, alpha=0.8,
                   edgecolors="white", linewidths=0.5, label=label)

    for mask, color in [(left, LEFT_COLOR), (right, RIGHT_COLOR)]:
        if mask.sum() < 10:
            continue
        xg, yh = _local_linear(x[mask], y[mask], bw)
        valid = np.isfinite(yh)
        ax.plot(xg[valid], yh[valid], color=color, linewidth=2, zorder=4)

    ax.axvline(0, color="black", linewidth=0.8, linestyle="--", zorder=3)
    ax.set_xlabel("Running Variable (Vote Margin / Eligible Voters)")
    ax.set_ylabel("Probability of Being Elected")
    ax.set_title("First Stage: Election Status at the Cutoff", fontweight="bold")
    ax.set_ylim(-0.05, 1.05)
    ax.legend(loc="center left", framealpha=0.9)

    fig.tight_layout()
    fig.savefig(outpath)
    plt.close(fig)
    print(f"  ✓ {outpath}")


def make_density_test(df, bw, outpath):
    """McCrary-style density histogram."""
    window = df[df["running_variable"].between(-bw, bw)].copy()
    x = window["running_variable"].dropna().values.astype(float)

    left_x  = x[x < 0]
    right_x = x[x >= 0]

    fig, ax = plt.subplots(figsize=(6, 4.5))

    bins_l = np.linspace(-bw, 0, 16)
    bins_r = np.linspace(0, bw, 16)
    ax.hist(left_x, bins=bins_l, color=LEFT_COLOR, alpha=0.7, edgecolor="white", linewidth=0.5)
    ax.hist(right_x, bins=bins_r, color=RIGHT_COLOR, alpha=0.7, edgecolor="white", linewidth=0.5)
    ax.axvline(0, color="black", linewidth=0.8, linestyle="--", zorder=3)

    # Add annotation
    n_left = len(left_x)
    n_right = len(right_x)
    ratio = n_right / n_left if n_left > 0 else float("nan")
    ax.annotate(f"N left = {n_left}\nN right = {n_right}\nRatio = {ratio:.2f}",
                xy=(0.97, 0.97), xycoords="axes fraction",
                ha="right", va="top", fontsize=9,
                bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=GREY, alpha=0.9))

    ax.set_xlabel("Running Variable (Vote Margin / Eligible Voters)")
    ax.set_ylabel("Frequency")
    ax.set_title("McCrary Density Test: Running Variable Distribution", fontweight="bold")

    fig.tight_layout()
    fig.savefig(outpath)
    plt.close(fig)
    print(f"  ✓ {outpath}")


def make_bandwidth_sensitivity(bw_csv, outpath):
    """Bandwidth sensitivity plot with 95% CIs."""
    bw_df = pd.read_csv(bw_csv)

    # Filter to main analysis with cluster_prv_election SE
    main_df = bw_df[
        (bw_df["analysis_type"] == "main") &
        (bw_df["se_type"] == "cluster_prv_election")
    ].copy()

    outcomes = [("runs_next", "Runs in Next Election"),
                ("wins_next", "Wins Seat in Next Election")]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), sharey=False)

    for ax, (oc, label) in zip(axes, outcomes):
        sub = main_df[main_df["outcome"] == oc].sort_values("bandwidth")

        if sub.empty:
            ax.set_title(label)
            ax.text(0.5, 0.5, "No data", ha="center", va="center", transform=ax.transAxes)
            continue

        bw_vals  = sub["bandwidth"].values.astype(float)
        tau_vals = sub["tau"].values.astype(float)
        se_vals  = sub["se"].values.astype(float)

        ci_low = tau_vals - 1.96 * se_vals
        ci_high = tau_vals + 1.96 * se_vals

        ax.fill_between(bw_vals, ci_low, ci_high, alpha=0.2, color=LEFT_COLOR)
        ax.plot(bw_vals, tau_vals, "o-", color=LEFT_COLOR, markersize=6,
                linewidth=1.5, markeredgecolor="white", markeredgewidth=0.5)
        ax.axhline(0, color=GREY, linewidth=0.8, linestyle="--")
        ax.set_xlabel("Bandwidth")
        ax.set_ylabel("Estimated Effect (τ)")
        ax.set_title(label, fontweight="bold")

    fig.suptitle("Bandwidth Sensitivity Analysis", fontweight="bold", fontsize=14, y=1.02)
    fig.tight_layout()
    fig.savefig(outpath)
    plt.close(fig)
    print(f"  ✓ {outpath}")


def make_covariate_balance(balance_csv, outpath):
    """Coefficient plot for covariate balance at the cutoff."""
    bal = pd.read_csv(balance_csv)

    # Filter to bw=0.05 and unique outcomes
    bal_05 = bal[bal["bandwidth"] == 0.05].copy()
    if bal_05.empty:
        # Take smallest bandwidth available
        bal_05 = bal[bal["bandwidth"] == bal["bandwidth"].min()].copy()

    labels_raw = bal_05["outcome"].values
    taus = bal_05["tau"].values.astype(float)
    ses  = bal_05["se"].values.astype(float)

    # Clean up labels
    label_map = {
        "blank_vote_share": "Blank Vote Share",
        "female": "Female Share",
        "list_pos": "List Position",
        "log_p_votes": "Log Party Votes",
        "p_seats": "Party Seats",
    }
    clean_labels = [label_map.get(str(l), str(l).replace("_", " ").title()) for l in labels_raw]

    fig, ax = plt.subplots(figsize=(6, 4))
    y_pos = np.arange(len(clean_labels))

    # Color significant covariates differently
    colors = []
    for p_tau, p_se in zip(taus, ses):
        p = 2 * (1 - __import__("scipy.stats", fromlist=["norm"]).norm.cdf(abs(p_tau / p_se))) if p_se > 0 else 1
        colors.append(RIGHT_COLOR if p < 0.05 else LEFT_COLOR)

    for i, (t, s, c) in enumerate(zip(taus, ses, colors)):
        ax.errorbar(t, i, xerr=1.96 * s, fmt="o", color=c,
                    markersize=7, capsize=4, capthick=1.5, linewidth=1.5,
                    markeredgecolor="white", markeredgewidth=0.5)

    ax.axvline(0, color=GREY, linewidth=0.8, linestyle="--")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(clean_labels)
    ax.set_xlabel("RDD Estimate (τ)")
    ax.set_title("Covariate Balance at the Cutoff (BW = 0.05)", fontweight="bold")
    ax.invert_yaxis()

    fig.tight_layout()
    fig.savefig(outpath)
    plt.close(fig)
    print(f"  ✓ {outpath}")


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate thesis figures")
    parser.add_argument("--data-dir", default="data/processed",
                        help="Path to processed data directory")
    parser.add_argument("--fig-dir", default="data/processed/thesis_figures",
                        help="Output directory for figures")
    args = parser.parse_args()

    data_dir = args.data_dir
    fig_dir  = args.fig_dir
    os.makedirs(fig_dir, exist_ok=True)

    # Load master dataset
    master_path = os.path.join(data_dir, "rdd_outcomes_enriched.csv")
    if not os.path.exists(master_path):
        print(f"ERROR: {master_path} not found.")
        sys.exit(1)

    print("Loading master dataset ...")
    df = pd.read_csv(master_path, low_memory=False)
    print(f"  {len(df)} rows loaded.")

    bw = 0.05

    # Figure 1: RDD scatter – runs_next
    print("\nFigure 1: RDD scatter – Runs in Next Election")
    make_rdd_scatter(df, "runs_next", bw,
                     title="Incumbency Effect on Running in Next Election",
                     ylabel="Pr(Runs in Next Election)",
                     outpath=os.path.join(fig_dir, "fig1_rdd_runs_next.png"))

    # Figure 2: RDD scatter – wins_next
    print("Figure 2: RDD scatter – Wins Seat in Next Election")
    make_rdd_scatter(df, "wins_next", bw,
                     title="Incumbency Effect on Winning Seat in Next Election",
                     ylabel="Pr(Wins Seat in Next Election)",
                     outpath=os.path.join(fig_dir, "fig2_rdd_wins_next.png"))

    # Figure 3: First stage
    print("Figure 3: First-stage – Elected vs Running Variable")
    make_first_stage(df, bw,
                     outpath=os.path.join(fig_dir, "fig3_first_stage.png"))

    # Figure 4: McCrary density test
    print("Figure 4: McCrary density test")
    make_density_test(df, bw,
                      outpath=os.path.join(fig_dir, "fig4_density_test.png"))

    # Figure 5: Bandwidth sensitivity
    bw_csv = os.path.join(data_dir, "rdd_baseline_estimates.csv")
    print("Figure 5: Bandwidth sensitivity")
    make_bandwidth_sensitivity(bw_csv,
                               outpath=os.path.join(fig_dir, "fig5_bandwidth_sensitivity.png"))

    # Figure 6: Covariate balance
    balance_csv = os.path.join(data_dir, "rdd_balance_placebo_checks.csv")
    print("Figure 6: Covariate balance")
    if os.path.exists(balance_csv):
        make_covariate_balance(balance_csv,
                               outpath=os.path.join(fig_dir, "fig6_covariate_balance.png"))
    else:
        print(f"  ⚠ {balance_csv} not found, skipping.")

    print("\n✅ All figures saved to", fig_dir)


if __name__ == "__main__":
    main()
