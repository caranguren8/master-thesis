#!/usr/bin/env python3
"""Create thesis-ready RDD result tables in CSV, LaTeX, and Markdown."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_SHARP_FUZZY = "data/processed/rdd_sharp_vs_fuzzy_comparison.csv"
DEFAULT_SELECTED_BW = "data/processed/rdd_baseline_estimates_selected_bw.csv"
DEFAULT_SELECTED_FUZZY = "data/processed/rdd_fuzzy_estimates_selected_bw.csv"
DEFAULT_BW_SELECTION = "data/processed/rdd_bandwidth_selection.csv"
DEFAULT_OUTCOME_DEFINITION = "data/processed/rdd_person_id_vs_string_estimates_long.csv"
DEFAULT_PLACEBO_CUTOFF = "data/processed/rdd_placebo_cutoff_tests.csv"
DEFAULT_DONUT_HOLE = "data/processed/rdd_donut_hole_robustness.csv"
DEFAULT_LOCAL_QUADRATIC = "data/processed/rdd_local_quadratic_robustness.csv"
DEFAULT_DESCRIPTIVE_STATS = "data/processed/rdd_descriptive_statistics.csv"
DEFAULT_BALANCE = "data/processed/rdd_balance_placebo_checks.csv"
DEFAULT_BALANCE_PRETREATMENT = "data/processed/rdd_balance_placebo_pretreatment.csv"
DEFAULT_DENSITY = "data/processed/rdd_running_variable_density_summary.csv"
DEFAULT_OUTDIR = "data/processed/thesis_tables"
DEFAULT_PREFERRED_SE = "cluster_prv_election"
DEFAULT_BW_GRID = "0.025,0.05,0.075,0.10"
DEFAULT_SE_TABLE_BW = 0.05
DEFAULT_OUTCOME_DEF_BW = 0.05

SE_ORDER = ["hc1", "cluster_prv_election", "cluster_prv_election_party"]
OUTCOME_ORDER = ["runs_next", "wins_next"]
OUTCOME_FAMILY_ORDER = ["runs", "wins"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build main and robustness thesis tables from latest RDD outputs."
    )
    parser.add_argument(
        "--sharp-fuzzy-csv",
        default=DEFAULT_SHARP_FUZZY,
        help=f"Sharp-vs-fuzzy estimate file (default: {DEFAULT_SHARP_FUZZY})",
    )
    parser.add_argument(
        "--selected-sharp-csv",
        default=DEFAULT_SELECTED_BW,
        help=f"Selected-bandwidth sharp estimates file (default: {DEFAULT_SELECTED_BW})",
    )
    parser.add_argument(
        "--selected-fuzzy-csv",
        default=DEFAULT_SELECTED_FUZZY,
        help=(
            "Selected-bandwidth fuzzy estimates file. If missing, "
            "falls back to nearest grid value in --sharp-fuzzy-csv "
            f"(default: {DEFAULT_SELECTED_FUZZY})"
        ),
    )
    parser.add_argument(
        "--bw-selection-csv",
        default=DEFAULT_BW_SELECTION,
        help=f"Bandwidth-selection file (default: {DEFAULT_BW_SELECTION})",
    )
    parser.add_argument(
        "--outcome-definition-csv",
        default=DEFAULT_OUTCOME_DEFINITION,
        help=f"Outcome-definition comparison file (default: {DEFAULT_OUTCOME_DEFINITION})",
    )
    parser.add_argument(
        "--preferred-se",
        default=DEFAULT_PREFERRED_SE,
        choices=SE_ORDER,
        help=f"Preferred SE type for main/bandwidth tables (default: {DEFAULT_PREFERRED_SE})",
    )
    parser.add_argument(
        "--bandwidth-grid",
        default=DEFAULT_BW_GRID,
        help=f"Bandwidth grid for robustness table (default: {DEFAULT_BW_GRID})",
    )
    parser.add_argument(
        "--se-table-bandwidth",
        type=float,
        default=DEFAULT_SE_TABLE_BW,
        help=f"Target bandwidth for SE-types table (default: {DEFAULT_SE_TABLE_BW})",
    )
    parser.add_argument(
        "--outcome-definition-bandwidth",
        type=float,
        default=DEFAULT_OUTCOME_DEF_BW,
        help=(
            "Target bandwidth for outcome-definition table "
            f"(default: {DEFAULT_OUTCOME_DEF_BW})"
        ),
    )
    parser.add_argument(
        "--outdir",
        default=DEFAULT_OUTDIR,
        help=f"Output directory for thesis tables (default: {DEFAULT_OUTDIR})",
    )
    return parser.parse_args()


def _parse_bw_grid(text: str) -> list[float]:
    values: list[float] = []
    for token in text.split(","):
        token = token.strip()
        if not token:
            continue
        val = float(token)
        if val <= 0:
            raise ValueError(f"Bandwidth must be positive, got {val}.")
        values.append(val)
    if not values:
        raise ValueError("Bandwidth grid is empty.")
    return sorted(set(values))


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    return pd.read_csv(path)


def _read_csv_optional(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path)


def _nearest_row(df: pd.DataFrame, bandwidth_col: str, target_bw: float) -> pd.Series:
    work = df.copy()
    work["_bw_distance"] = (pd.to_numeric(work[bandwidth_col], errors="coerce") - target_bw).abs()
    work = work.sort_values("_bw_distance")
    if work.empty:
        raise ValueError("Cannot select nearest row from empty table.")
    return work.iloc[0]


def _sort_outcomes(df: pd.DataFrame, col: str) -> pd.DataFrame:
    order_map = {name: i for i, name in enumerate(OUTCOME_ORDER)}
    out = df.copy()
    out["_ord"] = out[col].map(order_map).fillna(999).astype(int)
    out = out.sort_values(["_ord", col]).drop(columns=["_ord"])
    return out.reset_index(drop=True)


def _build_main_table(
    selected_sharp: pd.DataFrame,
    sharp_fuzzy: pd.DataFrame,
    selected_fuzzy: pd.DataFrame | None,
    preferred_se: str,
) -> pd.DataFrame:
    sharp_sel = selected_sharp[selected_sharp["se_type"] == preferred_se].copy()
    sharp_sel = sharp_sel[sharp_sel["outcome"].isin(OUTCOME_ORDER)].copy()
    if sharp_sel.empty:
        raise ValueError(
            f"No selected-bandwidth sharp rows found for se_type='{preferred_se}'."
        )

    use_selected_fuzzy = selected_fuzzy is not None and not selected_fuzzy.empty
    if use_selected_fuzzy:
        sf = selected_fuzzy[selected_fuzzy["se_type"] == preferred_se].copy()
        if sf.empty:
            raise ValueError(
                f"No selected-bandwidth fuzzy rows found for se_type='{preferred_se}'."
            )
    else:
        sf = sharp_fuzzy[sharp_fuzzy["se_type"] == preferred_se].copy()
        if sf.empty:
            raise ValueError(f"No sharp-fuzzy rows found for se_type='{preferred_se}'.")

    rows: list[dict[str, float | int | str]] = []
    for _, sharp_row in sharp_sel.iterrows():
        outcome = str(sharp_row["outcome"])
        selected_bw = float(sharp_row["bandwidth"])
        fuzzy_pool = sf[sf["outcome"] == outcome].copy()
        if fuzzy_pool.empty:
            continue

        if use_selected_fuzzy:
            exact = fuzzy_pool[np.isclose(fuzzy_pool["bandwidth"], selected_bw, atol=1e-12)].copy()
            if exact.empty:
                raise ValueError(
                    "Selected-bandwidth fuzzy estimates missing exact match for "
                    f"outcome='{outcome}', se_type='{preferred_se}', bandwidth={selected_bw}."
                )
            fuzzy_row = exact.iloc[0]
            fuzzy_exact = 1
        else:
            exact = fuzzy_pool[np.isclose(fuzzy_pool["bandwidth"], selected_bw, atol=1e-12)].copy()
            if not exact.empty:
                fuzzy_row = exact.iloc[0]
                fuzzy_exact = 1
            else:
                fuzzy_row = _nearest_row(fuzzy_pool, "bandwidth", selected_bw)
                fuzzy_exact = 0

        fuzzy_bw = float(fuzzy_row["bandwidth"])
        rows.append(
            {
                "outcome": outcome,
                "se_type": preferred_se,
                "selected_bandwidth": selected_bw,
                "sharp_tau": float(sharp_row["tau"]),
                "sharp_se": float(sharp_row["se"]),
                "sharp_p_value": float(sharp_row["p_value"]),
                "fuzzy_tau": float(fuzzy_row["fuzzy_tau"]),
                "fuzzy_se": float(fuzzy_row["fuzzy_se"]),
                "fuzzy_p_value": float(fuzzy_row["fuzzy_p_value"]),
                "first_stage_tau": float(fuzzy_row["first_stage_tau"]),
                "first_stage_se": float(fuzzy_row["first_stage_se"]),
                "first_stage_p_value": float(fuzzy_row["first_stage_p_value"]),
                "fuzzy_bandwidth_used": fuzzy_bw,
                "fuzzy_bw_distance": abs(fuzzy_bw - selected_bw),
                "fuzzy_exact_bw_match": fuzzy_exact,
            }
        )

    out = pd.DataFrame(rows)
    return _sort_outcomes(out, "outcome")


def _build_bandwidth_grid_table(
    sharp_fuzzy: pd.DataFrame,
    preferred_se: str,
    bw_grid: list[float],
) -> pd.DataFrame:
    sf = sharp_fuzzy[sharp_fuzzy["se_type"] == preferred_se].copy()
    rows: list[pd.Series] = []
    for outcome in OUTCOME_ORDER:
        sub = sf[sf["outcome"] == outcome].copy()
        for bw in bw_grid:
            exact = sub[np.isclose(sub["bandwidth"], bw, atol=1e-12)].copy()
            if not exact.empty:
                row = exact.iloc[0]
            else:
                row = _nearest_row(sub, "bandwidth", bw)
            rows.append(row)

    out = pd.DataFrame(rows).copy()
    out["requested_bandwidth"] = np.tile(bw_grid, len(OUTCOME_ORDER))
    out["bandwidth_distance"] = (out["bandwidth"] - out["requested_bandwidth"]).abs()
    out = out[
        [
            "outcome",
            "se_type",
            "requested_bandwidth",
            "bandwidth",
            "bandwidth_distance",
            "sharp_tau",
            "sharp_se",
            "sharp_p_value",
            "fuzzy_tau",
            "fuzzy_se",
            "fuzzy_p_value",
            "first_stage_tau",
            "first_stage_se",
            "first_stage_p_value",
        ]
    ].rename(columns={"bandwidth": "bandwidth_used"})
    out = _sort_outcomes(out, "outcome")
    return out.reset_index(drop=True)


def _build_se_types_table(
    sharp_fuzzy: pd.DataFrame,
    target_bw: float,
) -> pd.DataFrame:
    sf = sharp_fuzzy.copy()
    rows: list[dict[str, float | int | str]] = []
    for outcome in OUTCOME_ORDER:
        for se_type in SE_ORDER:
            sub = sf[(sf["outcome"] == outcome) & (sf["se_type"] == se_type)].copy()
            if sub.empty:
                continue
            best = _nearest_row(sub, "bandwidth", target_bw)
            bw_used = float(best["bandwidth"])
            rows.append(
                {
                    "outcome": outcome,
                    "se_type": se_type,
                    "target_bandwidth": target_bw,
                    "bandwidth_used": bw_used,
                    "bandwidth_distance": abs(bw_used - target_bw),
                    "sharp_tau": float(best["sharp_tau"]),
                    "sharp_se": float(best["sharp_se"]),
                    "sharp_p_value": float(best["sharp_p_value"]),
                    "fuzzy_tau": float(best["fuzzy_tau"]),
                    "fuzzy_se": float(best["fuzzy_se"]),
                    "fuzzy_p_value": float(best["fuzzy_p_value"]),
                    "first_stage_tau": float(best["first_stage_tau"]),
                    "first_stage_se": float(best["first_stage_se"]),
                    "first_stage_p_value": float(best["first_stage_p_value"]),
                }
            )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    se_order_map = {name: i for i, name in enumerate(SE_ORDER)}
    out = _sort_outcomes(out, "outcome")
    out["_se_ord"] = out["se_type"].map(se_order_map).fillna(999).astype(int)
    out = out.sort_values(["outcome", "_se_ord", "se_type"]).drop(columns=["_se_ord"])
    return out.reset_index(drop=True)


def _build_outcome_definition_table(
    outcome_def_long: pd.DataFrame,
    target_bw: float,
    preferred_se: str,
) -> pd.DataFrame:
    needed_defs = {"person_same_prv", "person_any_prv"}
    sub = outcome_def_long[outcome_def_long["definition"].isin(needed_defs)].copy()
    if "se_type" in sub.columns:
        sub = sub[sub["se_type"] == preferred_se].copy()
    if sub.empty:
        raise ValueError(
            "No person-based outcome-definition rows found for "
            f"se_type='{preferred_se}'."
        )

    rows: list[dict[str, float | int | str]] = []
    for family in OUTCOME_FAMILY_ORDER:
        fam = sub[sub["outcome_family"] == family].copy()
        if fam.empty:
            continue
        same_pool = fam[fam["definition"] == "person_same_prv"].copy()
        any_pool = fam[fam["definition"] == "person_any_prv"].copy()
        if same_pool.empty or any_pool.empty:
            continue

        same_row = _nearest_row(same_pool, "bandwidth", target_bw)
        any_row = _nearest_row(any_pool, "bandwidth", target_bw)

        same_bw = float(same_row["bandwidth"])
        any_bw = float(any_row["bandwidth"])
        same_tau = float(same_row["tau"])
        any_tau = float(any_row["tau"])

        rows.append(
            {
                "outcome_family": family,
                "se_type_source": str(same_row["se_type"]),
                "target_bandwidth": target_bw,
                "same_prv_bandwidth_used": same_bw,
                "any_prv_bandwidth_used": any_bw,
                "same_prv_bw_distance": abs(same_bw - target_bw),
                "any_prv_bw_distance": abs(any_bw - target_bw),
                "same_prv_tau": same_tau,
                "same_prv_se": float(same_row["se"]),
                "same_prv_p_value": float(same_row["p_value"]),
                "any_prv_tau": any_tau,
                "any_prv_se": float(any_row["se"]),
                "any_prv_p_value": float(any_row["p_value"]),
                "any_minus_same_tau": any_tau - same_tau,
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    order_map = {name: i for i, name in enumerate(OUTCOME_FAMILY_ORDER)}
    out["_ord"] = out["outcome_family"].map(order_map).fillna(999).astype(int)
    out = out.sort_values(["_ord", "outcome_family"]).drop(columns=["_ord"]).reset_index(drop=True)
    return out


def _fmt_value(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, (np.integer, int)):
        return str(int(value))
    if isinstance(value, (np.floating, float)):
        v = float(value)
        av = abs(v)
        if av >= 1e4 or (av > 0 and av < 1e-4):
            return f"{v:.3e}"
        return f"{v:.4f}"
    return str(value)


def _to_display_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        out[col] = out[col].map(_fmt_value)
    return out


def _render_markdown(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns.tolist()]
    rows = [[str(v) for v in row] for row in df.itertuples(index=False, name=None)]
    widths = [len(c) for c in cols]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    header = "| " + " | ".join(cols[i].ljust(widths[i]) for i in range(len(cols))) + " |"
    sep = "| " + " | ".join("-" * widths[i] for i in range(len(cols))) + " |"
    body = [
        "| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(cols))) + " |"
        for row in rows
    ]
    return "\n".join([header, sep, *body]) + "\n"


def _stars(p: float) -> str:
    """Return significance stars for a p-value."""
    if pd.isna(p):
        return ""
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def _build_placebo_cutoff_table(
    placebo_df: pd.DataFrame,
    preferred_se: str,
) -> pd.DataFrame:
    """Placebo cutoff test table: RDD at fake cutoffs (median of each side)."""
    sub = placebo_df[placebo_df["se_type"] == preferred_se].copy()
    if sub.empty:
        sub = placebo_df.copy()

    rows: list[dict[str, float | int | str]] = []
    for _, r in sub.iterrows():
        rows.append(
            {
                "outcome": str(r["outcome"]),
                "bandwidth": float(r["bandwidth"]),
                "placebo_cutoff": float(r.get("placebo_cutoff", np.nan)),
                "placebo_label": str(r.get("placebo_label", "")),
                "tau": float(r["tau"]),
                "se": float(r["se"]),
                "p_value": float(r["p_value"]),
                "significance": _stars(float(r["p_value"])),
                "n_window": int(r["n_window"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["outcome", "bandwidth", "placebo_label"])


def _build_donut_hole_table(
    donut_df: pd.DataFrame,
    preferred_se: str,
) -> pd.DataFrame:
    """Donut-hole robustness table: RDD excluding observations near cutoff."""
    sub = donut_df[donut_df["se_type"] == preferred_se].copy()
    if sub.empty:
        sub = donut_df.copy()

    rows: list[dict[str, float | int | str]] = []
    for _, r in sub.iterrows():
        rows.append(
            {
                "outcome": str(r["outcome"]),
                "bandwidth": float(r["bandwidth"]),
                "donut_radius": float(r.get("donut_radius", np.nan)),
                "tau": float(r["tau"]),
                "se": float(r["se"]),
                "p_value": float(r["p_value"]),
                "significance": _stars(float(r["p_value"])),
                "n_window": int(r["n_window"]),
            }
        )
    return pd.DataFrame(rows).sort_values(["outcome", "bandwidth", "donut_radius"])


def _build_polynomial_robustness_table(
    quad_df: pd.DataFrame,
    main_estimates_csv: str = "data/processed/rdd_baseline_estimates.csv",
    preferred_se: str = "hc1",
) -> pd.DataFrame:
    """Compare local-linear vs local-quadratic estimates."""
    quad_sub = quad_df[quad_df["se_type"] == preferred_se].copy()
    if quad_sub.empty:
        quad_sub = quad_df.copy()

    # Try to load main (local-linear) estimates for comparison.
    main_path = Path(main_estimates_csv)
    main_df = pd.read_csv(main_path) if main_path.exists() else None

    rows: list[dict[str, float | int | str]] = []
    for _, r in quad_sub.iterrows():
        outcome = str(r["outcome"])
        bw = float(r["bandwidth"])
        row: dict[str, float | int | str] = {
            "outcome": outcome,
            "bandwidth": bw,
            "quadratic_tau": float(r["tau"]),
            "quadratic_se": float(r["se"]),
            "quadratic_p_value": float(r["p_value"]),
        }
        # Attach matching local-linear result.
        if main_df is not None:
            linear_match = main_df[
                (main_df["outcome"] == outcome)
                & (main_df["se_type"] == preferred_se)
                & (np.isclose(main_df["bandwidth"], bw, atol=1e-12))
            ]
            if not linear_match.empty:
                lr = linear_match.iloc[0]
                row["linear_tau"] = float(lr["tau"])
                row["linear_se"] = float(lr["se"])
                row["linear_p_value"] = float(lr["p_value"])
            else:
                row["linear_tau"] = np.nan
                row["linear_se"] = np.nan
                row["linear_p_value"] = np.nan
        rows.append(row)

    return pd.DataFrame(rows).sort_values(["outcome", "bandwidth"])


def _build_balance_table(
    balance_df: pd.DataFrame,
    bw_grid: list[float],
) -> pd.DataFrame:
    """Build a pivoted balance test table: covariates as rows, bandwidths as columns."""
    rows: list[dict[str, float | int | str]] = []
    covariates = sorted(balance_df["outcome"].unique().tolist())
    for cov in covariates:
        row: dict[str, float | int | str] = {"covariate": cov}
        sub = balance_df[balance_df["outcome"] == cov]
        for bw in bw_grid:
            match = sub[np.isclose(sub["bandwidth"], bw, atol=1e-12)]
            if not match.empty:
                r = match.iloc[0]
                tau = float(r["tau"])
                se = float(r["se"])
                p = float(r["p_value"])
                row[f"tau_bw{bw:.3f}"] = tau
                row[f"se_bw{bw:.3f}"] = se
                row[f"p_bw{bw:.3f}"] = p
                row[f"stars_bw{bw:.3f}"] = _stars(p)
            else:
                row[f"tau_bw{bw:.3f}"] = np.nan
                row[f"se_bw{bw:.3f}"] = np.nan
                row[f"p_bw{bw:.3f}"] = np.nan
                row[f"stars_bw{bw:.3f}"] = ""
        rows.append(row)
    return pd.DataFrame(rows)


def _write_table(df: pd.DataFrame, outdir: Path, stem: str) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / f"{stem}.csv"
    tex_path = outdir / f"{stem}.tex"
    md_path = outdir / f"{stem}.md"

    df.to_csv(csv_path, index=False)

    display_df = _to_display_df(df)
    latex = display_df.to_latex(index=False, escape=True)
    md = _render_markdown(display_df)

    tex_path.write_text(latex, encoding="utf-8")
    md_path.write_text(md, encoding="utf-8")


def main() -> None:
    args = parse_args()
    outdir = Path(args.outdir)
    bw_grid = _parse_bw_grid(args.bandwidth_grid)

    sharp_fuzzy = _read_csv(Path(args.sharp_fuzzy_csv))
    selected_sharp = _read_csv(Path(args.selected_sharp_csv))
    selected_fuzzy = _read_csv_optional(Path(args.selected_fuzzy_csv))
    _ = _read_csv(Path(args.bw_selection_csv))
    outcome_def_long = _read_csv(Path(args.outcome_definition_csv))

    main_table = _build_main_table(
        selected_sharp=selected_sharp,
        sharp_fuzzy=sharp_fuzzy,
        selected_fuzzy=selected_fuzzy,
        preferred_se=args.preferred_se,
    )
    bw_table = _build_bandwidth_grid_table(
        sharp_fuzzy=sharp_fuzzy,
        preferred_se=args.preferred_se,
        bw_grid=bw_grid,
    )
    se_table = _build_se_types_table(
        sharp_fuzzy=sharp_fuzzy,
        target_bw=float(args.se_table_bandwidth),
    )
    outcome_def_table = _build_outcome_definition_table(
        outcome_def_long=outcome_def_long,
        target_bw=float(args.outcome_definition_bandwidth),
        preferred_se=args.preferred_se,
    )

    _write_table(main_table, outdir=outdir, stem="thesis_main_sharp_fuzzy_selected_bw")
    _write_table(bw_table, outdir=outdir, stem="thesis_robustness_bandwidth_grid")
    _write_table(se_table, outdir=outdir, stem="thesis_robustness_se_types")
    _write_table(outcome_def_table, outdir=outdir, stem="thesis_robustness_outcome_definition")

    table_count = 4

    # New robustness tables.
    placebo_path = Path(DEFAULT_PLACEBO_CUTOFF)
    if placebo_path.exists():
        placebo_df = _read_csv(placebo_path)
        placebo_table = _build_placebo_cutoff_table(placebo_df, preferred_se=args.preferred_se)
        _write_table(placebo_table, outdir=outdir, stem="thesis_robustness_placebo_cutoff")
        table_count += 1
        print(f"Placebo cutoff table rows: {len(placebo_table)}")

    donut_path = Path(DEFAULT_DONUT_HOLE)
    if donut_path.exists():
        donut_df = _read_csv(donut_path)
        donut_table = _build_donut_hole_table(donut_df, preferred_se=args.preferred_se)
        _write_table(donut_table, outdir=outdir, stem="thesis_robustness_donut_hole")
        table_count += 1
        print(f"Donut-hole table rows: {len(donut_table)}")

    quad_path = Path(DEFAULT_LOCAL_QUADRATIC)
    if quad_path.exists():
        quad_df = _read_csv(quad_path)
        quad_table = _build_polynomial_robustness_table(
            quad_df, preferred_se=args.preferred_se
        )
        _write_table(quad_table, outdir=outdir, stem="thesis_robustness_polynomial_order")
        table_count += 1
        print(f"Polynomial order table rows: {len(quad_table)}")

    desc_path = Path(DEFAULT_DESCRIPTIVE_STATS)
    if desc_path.exists():
        desc_df = _read_csv(desc_path)
        _write_table(desc_df, outdir=outdir, stem="thesis_descriptive_statistics")
        table_count += 1
        print(f"Descriptive statistics table rows: {len(desc_df)}")

    balance_path = Path(DEFAULT_BALANCE)
    if balance_path.exists():
        balance_df = _read_csv(balance_path)
        balance_table = _build_balance_table(balance_df, bw_grid=bw_grid)
        _write_table(balance_table, outdir=outdir, stem="thesis_balance_covariates")
        table_count += 1
        print(f"Balance covariates table rows: {len(balance_table)}")

    pretreatment_path = Path(DEFAULT_BALANCE_PRETREATMENT)
    if pretreatment_path.exists():
        pretreatment_df = _read_csv(pretreatment_path)
        pretreatment_table = _build_balance_table(pretreatment_df, bw_grid=bw_grid)
        _write_table(pretreatment_table, outdir=outdir, stem="thesis_balance_pretreatment")
        table_count += 1
        print(f"Pre-treatment balance table rows: {len(pretreatment_table)}")

    density_path = Path(DEFAULT_DENSITY)
    if density_path.exists():
        density_df = _read_csv(density_path)
        _write_table(density_df, outdir=outdir, stem="thesis_density_test")
        table_count += 1
        print(f"Density test table rows: {len(density_df)}")

    print(f"\nThesis tables created: {table_count} tables.")
    print(f"Output directory: {outdir}")
    print(f"Main table rows: {len(main_table)}")
    print(f"Bandwidth robustness rows: {len(bw_table)}")
    print(f"SE-types robustness rows: {len(se_table)}")
    print(f"Outcome-definition robustness rows: {len(outcome_def_table)}")
    if selected_fuzzy is None or selected_fuzzy.empty:
        print("Main table note: selected fuzzy file missing; used nearest bandwidth fallback.")
    print("\nMain table preview:")
    print(main_table.to_string(index=False))


if __name__ == "__main__":
    main()
