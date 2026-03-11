#!/usr/bin/env python3
"""Baseline local-linear RDD around cutoff on Spain master dataset.

Includes:
- Bandwidth sensitivity grid.
- RDD binned-scatter plots with local-linear fits.
- Balance/placebo checks on selected covariates.
"""

from __future__ import annotations

import argparse
import os
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import norm, t as t_dist

# Keep plotting stable in headless/dev environments.
_MPL_CACHE_DIR = Path("tmp/mpl-cache").resolve()
_MPL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str(_MPL_CACHE_DIR))
import matplotlib.pyplot as plt


DEFAULT_DATA = "data/processed/spain_master_dataset.csv"
DEFAULT_OUTPUT = "data/processed/rdd_baseline_estimates.csv"
DEFAULT_BALANCE_OUTPUT = "data/processed/rdd_balance_placebo_checks.csv"
DEFAULT_BALANCE_PRETREATMENT_OUTPUT = "data/processed/rdd_balance_placebo_pretreatment.csv"
DEFAULT_SAMPLE_OUTPUT = "data/processed/rdd_outcomes_enriched.csv"
DEFAULT_VALIDATION_OUTPUT = "data/processed/rdd_treatment_validation.csv"
DEFAULT_VALIDATION_MISMATCH_OUTPUT = "data/processed/rdd_treatment_mismatches.csv"
DEFAULT_FEMALE_DIAG_OUTPUT = "data/processed/rdd_female_placebo_diagnostics.csv"
DEFAULT_FEMALE_CLOSEST_OUTPUT = "data/processed/rdd_female_placebo_closest20.csv"
DEFAULT_PERSON_ID_MAP_INPUT = "data/processed/person_id_map.csv"
DEFAULT_PERSON_ID_OUTPUT = "data/processed/rdd_person_id_assignment.csv"
DEFAULT_PERSON_ID_VALIDATION_OUTPUT = "data/processed/rdd_person_id_validation_report.csv"
DEFAULT_COMPARISON_OUTPUT = "data/processed/rdd_person_id_vs_string_comparison.csv"
DEFAULT_COMPARISON_LONG_OUTPUT = "data/processed/rdd_person_id_vs_string_estimates_long.csv"
DEFAULT_FUZZY_OUTPUT = "data/processed/rdd_fuzzy_estimates.csv"
DEFAULT_FUZZY_SELECTED_BW_OUTPUT = "data/processed/rdd_fuzzy_estimates_selected_bw.csv"
DEFAULT_SHARP_FUZZY_COMPARISON_OUTPUT = "data/processed/rdd_sharp_vs_fuzzy_comparison.csv"
DEFAULT_DENSITY_BINS_OUTPUT = "data/processed/rdd_running_variable_density_bins.csv"
DEFAULT_DENSITY_SUMMARY_OUTPUT = "data/processed/rdd_running_variable_density_summary.csv"
DEFAULT_BW_SELECTION_OUTPUT = "data/processed/rdd_bandwidth_selection.csv"
DEFAULT_MAIN_SELECTED_BW_OUTPUT = "data/processed/rdd_baseline_estimates_selected_bw.csv"
DEFAULT_FIG_DIR = "data/processed/figures"
DEFAULT_WINDOWS_DIR = "data/processed/windows"
DEFAULT_BANDWIDTH_GRID = "0.025,0.05,0.075,0.10"
DEFAULT_BALANCE_COVARIATES = "female,list_pos,log_p_votes,p_seats,blank_vote_share"
DEFAULT_BALANCE_PRETREATMENT_COVARIATES = (
    "female,lag_party_vote_share,lag_p_seats,lag_log_p_votes,lag_province_turnout,lag_province_blank_share"
)
DEFAULT_PERSON_ID_METHOD = "auto"
DEFAULT_PERSON_ID_LT_DISTANCE_THRESHOLD = 0.10
DEFAULT_PERSON_ID_FUZZY_SIM_THRESHOLD = 0.94
DEFAULT_PERSON_ID_MAX_BLOCK_SIZE = 120
DEFAULT_SE_TYPES = "hc1,cluster_prv_election,cluster_prv_election_party"


@dataclass
class RddEstimate:
    analysis_type: str
    outcome: str
    bandwidth: float
    se_type: str
    cluster_spec: str
    n_clusters_left: int
    n_clusters_right: int
    n_window: int
    n_left: int
    n_right: int
    mean_left: float
    mean_right: float
    tau: float
    se: float
    ci95_low: float
    ci95_high: float
    p_value: float

    def as_dict(self) -> dict[str, float | int | str]:
        return {
            "analysis_type": self.analysis_type,
            "outcome": self.outcome,
            "bandwidth": self.bandwidth,
            "se_type": self.se_type,
            "cluster_spec": self.cluster_spec,
            "n_clusters_left": self.n_clusters_left,
            "n_clusters_right": self.n_clusters_right,
            "n_window": self.n_window,
            "n_left": self.n_left,
            "n_right": self.n_right,
            "mean_left": self.mean_left,
            "mean_right": self.mean_right,
            "tau": self.tau,
            "se": self.se,
            "ci95_low": self.ci95_low,
            "ci95_high": self.ci95_high,
            "p_value": self.p_value,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Estimate baseline local-linear RDD at running variable cutoff 0."
    )
    parser.add_argument(
        "--data",
        default=DEFAULT_DATA,
        help=f"Input dataset path (default: {DEFAULT_DATA})",
    )
    parser.add_argument(
        "--running-col",
        default="running_variable",
        help="Running variable column name (default: running_variable).",
    )
    parser.add_argument(
        "--bandwidth",
        type=float,
        default=0.05,
        help="Reference bandwidth used for RDD binned plots (default: 0.05).",
    )
    parser.add_argument(
        "--bandwidth-grid",
        default=DEFAULT_BANDWIDTH_GRID,
        help=f"Comma-separated sensitivity grid (default: {DEFAULT_BANDWIDTH_GRID}).",
    )
    parser.add_argument(
        "--outcome",
        choices=["wins_next", "runs_next", "both"],
        default="both",
        help="Main outcome(s) to estimate (default: both).",
    )
    parser.add_argument(
        "--se-types",
        default=DEFAULT_SE_TYPES,
        help=(
            "Comma-separated SE estimators for main results. Supported: "
            "hc1, cluster_prv_election, cluster_prv_election_party "
            f"(default: {DEFAULT_SE_TYPES})."
        ),
    )
    parser.add_argument(
        "--balance-covariates",
        default=DEFAULT_BALANCE_COVARIATES,
        help=(
            "Comma-separated covariates for balance/placebo checks "
            f"(default: {DEFAULT_BALANCE_COVARIATES})."
        ),
    )
    parser.add_argument(
        "--min-side-n",
        type=int,
        default=30,
        help="Minimum observations required on each side of cutoff (default: 30).",
    )
    parser.add_argument(
        "--bins-per-side",
        type=int,
        default=15,
        help="Number of bins per side for RDD plots (default: 15).",
    )
    parser.add_argument(
        "--output-csv",
        default=DEFAULT_OUTPUT,
        help=f"Output CSV path for main estimates (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--balance-output-csv",
        default=DEFAULT_BALANCE_OUTPUT,
        help=f"Output CSV path for balance/placebo checks (default: {DEFAULT_BALANCE_OUTPUT})",
    )
    parser.add_argument(
        "--balance-pretreatment-output-csv",
        default=DEFAULT_BALANCE_PRETREATMENT_OUTPUT,
        help=(
            "Output CSV path for pre-treatment-only balance/placebo checks "
            f"(default: {DEFAULT_BALANCE_PRETREATMENT_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--balance-pretreatment-covariates",
        default=DEFAULT_BALANCE_PRETREATMENT_COVARIATES,
        help=(
            "Comma-separated pre-treatment covariates for dedicated placebo checks "
            f"(default: {DEFAULT_BALANCE_PRETREATMENT_COVARIATES})."
        ),
    )
    parser.add_argument(
        "--sample-output-csv",
        default=DEFAULT_SAMPLE_OUTPUT,
        help=f"Output CSV path for analysis sample (default: {DEFAULT_SAMPLE_OUTPUT})",
    )
    parser.add_argument(
        "--windows-dir",
        default=DEFAULT_WINDOWS_DIR,
        help=f"Output directory for per-bandwidth estimation windows (default: {DEFAULT_WINDOWS_DIR})",
    )
    parser.add_argument(
        "--validation-output-csv",
        default=DEFAULT_VALIDATION_OUTPUT,
        help=(
            "Output CSV path for treatment-vs-election validation summary "
            f"(default: {DEFAULT_VALIDATION_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--validation-mismatches-csv",
        default=DEFAULT_VALIDATION_MISMATCH_OUTPUT,
        help=(
            "Output CSV path for treatment-vs-election mismatching rows "
            f"(default: {DEFAULT_VALIDATION_MISMATCH_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--female-diagnostics-csv",
        default=DEFAULT_FEMALE_DIAG_OUTPUT,
        help=(
            "Output CSV path for female placebo diagnostics "
            f"(default: {DEFAULT_FEMALE_DIAG_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--female-closest-csv",
        default=DEFAULT_FEMALE_CLOSEST_OUTPUT,
        help=(
            "Output CSV path for closest female-placebo observations "
            f"(default: {DEFAULT_FEMALE_CLOSEST_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--person-id-map-csv",
        default=DEFAULT_PERSON_ID_MAP_INPUT,
        help=(
            "Input person-ID map produced by src/data/build_person_id.py "
            f"(default: {DEFAULT_PERSON_ID_MAP_INPUT})."
        ),
    )
    parser.add_argument(
        "--person-id-map-col",
        default="person_id",
        help="Person ID column name in --person-id-map-csv (default: person_id).",
    )
    parser.add_argument(
        "--person-id-method",
        choices=["auto", "existing", "linktransformer", "heuristic"],
        default=DEFAULT_PERSON_ID_METHOD,
        help=(
            "How to create stable person_id: use existing panel ID if available, "
            "LinkTransformer clustering, or heuristic local fuzzy matching "
            f"(default: {DEFAULT_PERSON_ID_METHOD})."
        ),
    )
    parser.add_argument(
        "--panel-id-csv",
        default="",
        help=(
            "Optional external panel-ID table (.csv/.xlsx) to merge before fuzzy matching. "
            "Expected either row keys (election_ym, prv_code, p_code, list_pos) "
            "or candidate-level keys."
        ),
    )
    parser.add_argument(
        "--panel-id-col",
        default="",
        help=(
            "Optional column name in --panel-id-csv to use as panel/person ID. "
            "If omitted, auto-detected from common names."
        ),
    )
    parser.add_argument(
        "--person-id-lt-distance-threshold",
        type=float,
        default=DEFAULT_PERSON_ID_LT_DISTANCE_THRESHOLD,
        help=(
            "Distance threshold for LinkTransformer hierarchical clustering "
            f"(default: {DEFAULT_PERSON_ID_LT_DISTANCE_THRESHOLD})."
        ),
    )
    parser.add_argument(
        "--person-id-fuzzy-sim-threshold",
        type=float,
        default=DEFAULT_PERSON_ID_FUZZY_SIM_THRESHOLD,
        help=(
            "Similarity threshold for heuristic fuzzy clustering in [0,1] "
            f"(default: {DEFAULT_PERSON_ID_FUZZY_SIM_THRESHOLD})."
        ),
    )
    parser.add_argument(
        "--person-id-max-block-size",
        type=int,
        default=DEFAULT_PERSON_ID_MAX_BLOCK_SIZE,
        help=(
            "Maximum block size for pairwise fuzzy comparisons; larger blocks skip "
            f"fuzzy linking (default: {DEFAULT_PERSON_ID_MAX_BLOCK_SIZE})."
        ),
    )
    parser.add_argument(
        "--person-id-output-csv",
        default=DEFAULT_PERSON_ID_OUTPUT,
        help=f"Output CSV for person_id assignment/mapping (default: {DEFAULT_PERSON_ID_OUTPUT})",
    )
    parser.add_argument(
        "--person-id-validation-output-csv",
        default=DEFAULT_PERSON_ID_VALIDATION_OUTPUT,
        help=(
            "Output CSV for person_id threshold/method validation report "
            f"(default: {DEFAULT_PERSON_ID_VALIDATION_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--comparison-output-csv",
        default=DEFAULT_COMPARISON_OUTPUT,
        help=(
            "Output CSV for person-id vs string-based RDD comparison "
            f"(default: {DEFAULT_COMPARISON_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--comparison-long-output-csv",
        default=DEFAULT_COMPARISON_LONG_OUTPUT,
        help=(
            "Output CSV for long-format RDD estimates by outcome definition "
            f"(default: {DEFAULT_COMPARISON_LONG_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--fuzzy-output-csv",
        default=DEFAULT_FUZZY_OUTPUT,
        help=(
            "Output CSV for fuzzy-RD (Wald/LATE) estimates and first stage "
            f"(default: {DEFAULT_FUZZY_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--fuzzy-selected-bw-output-csv",
        default=DEFAULT_FUZZY_SELECTED_BW_OUTPUT,
        help=(
            "Output CSV for fuzzy-RD estimates at selected data-driven bandwidths "
            f"(default: {DEFAULT_FUZZY_SELECTED_BW_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--sharp-fuzzy-comparison-output-csv",
        default=DEFAULT_SHARP_FUZZY_COMPARISON_OUTPUT,
        help=(
            "Output CSV comparing sharp vs fuzzy estimates side-by-side "
            f"(default: {DEFAULT_SHARP_FUZZY_COMPARISON_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--density-bins-output-csv",
        default=DEFAULT_DENSITY_BINS_OUTPUT,
        help=(
            "Output CSV for running-variable binned counts/densities "
            f"(default: {DEFAULT_DENSITY_BINS_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--density-summary-output-csv",
        default=DEFAULT_DENSITY_SUMMARY_OUTPUT,
        help=(
            "Output CSV for running-variable density discontinuity diagnostics "
            f"(default: {DEFAULT_DENSITY_SUMMARY_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--bw-selection-output-csv",
        default=DEFAULT_BW_SELECTION_OUTPUT,
        help=(
            "Output CSV reporting selected data-driven bandwidth per outcome "
            f"(default: {DEFAULT_BW_SELECTION_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--main-selected-bw-output-csv",
        default=DEFAULT_MAIN_SELECTED_BW_OUTPUT,
        help=(
            "Output CSV for main estimates run at selected data-driven bandwidths "
            f"(default: {DEFAULT_MAIN_SELECTED_BW_OUTPUT})"
        ),
    )
    parser.add_argument(
        "--fig-dir",
        default=DEFAULT_FIG_DIR,
        help=f"Output directory for figures (default: {DEFAULT_FIG_DIR})",
    )
    return parser.parse_args()


def _assert_columns(df: pd.DataFrame, cols: Iterable[str]) -> None:
    missing = sorted(set(cols) - set(df.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def _parse_bandwidth_grid(grid_text: str) -> list[float]:
    values: list[float] = []
    for part in grid_text.split(","):
        token = part.strip()
        if not token:
            continue
        value = float(token)
        if value <= 0:
            raise ValueError(f"Bandwidth must be positive, got {value}.")
        values.append(value)
    unique_sorted = sorted(set(values))
    if not unique_sorted:
        raise ValueError("Bandwidth grid is empty.")
    return unique_sorted


def _parse_se_types(se_text: str) -> list[str]:
    allowed = {"hc1", "cluster_prv_election", "cluster_prv_election_party"}
    parsed = [s.strip().lower() for s in se_text.split(",") if s.strip()]
    if not parsed:
        raise ValueError("SE types are empty.")
    invalid = sorted(set(parsed) - allowed)
    if invalid:
        raise ValueError(f"Unsupported SE type(s): {invalid}. Allowed: {sorted(allowed)}")
    deduped: list[str] = []
    for s in parsed:
        if s not in deduped:
            deduped.append(s)
    return deduped


def _resolve_available_se_types(df: pd.DataFrame, requested: list[str]) -> tuple[list[str], list[str]]:
    available: list[str] = []
    skipped: list[str] = []
    for se_type in requested:
        if se_type == "cluster_prv_election_party" and "p_code" not in df.columns:
            skipped.append(f"{se_type}:missing_p_code")
            continue
        if se_type.startswith("cluster") and (
            "prv_code" not in df.columns or "election_ym" not in df.columns
        ):
            skipped.append(f"{se_type}:missing_cluster_keys")
            continue
        available.append(se_type)
    if not available:
        available = ["hc1"]
        skipped.append("all_requested_cluster_types_unavailable:fallback_hc1")
    return available, skipped


def _normalize_person_name(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = " ".join(text.split())
    return text


def _name_block_key(name_norm: str) -> str:
    tokens = name_norm.split()
    if not tokens:
        return "__EMPTY__"
    first = tokens[0][:3]
    last = tokens[-1][:4]
    return f"{first}|{last}|{len(tokens)}"


def _resolve_person_id_col(columns: Iterable[str], explicit_col: str = "") -> str:
    if explicit_col:
        if explicit_col in columns:
            return explicit_col
        raise ValueError(f"--panel-id-col='{explicit_col}' not found in provided data.")
    candidates = [
        "person_id",
        "panel_id",
        "Panel_ID",
        "panelid",
        "PanelID",
        "cluster_id",
    ]
    for col in candidates:
        if col in columns:
            return col
    return ""


def _auto_detect_panel_id_csv(search_dir: Path) -> str:
    if not search_dir.exists():
        return ""
    candidate_paths = (
        sorted(search_dir.glob("*panel*.csv"))
        + sorted(search_dir.glob("*Panel*.csv"))
        + sorted(search_dir.glob("*panel*.xlsx"))
        + sorted(search_dir.glob("*Panel*.xlsx"))
    )
    for path in candidate_paths:
        try:
            if path.suffix.lower() in {".xlsx", ".xls"}:
                sample = pd.read_excel(path, nrows=5)
            else:
                sample = pd.read_csv(path, nrows=5)
        except Exception:
            continue
        id_col = _resolve_person_id_col(sample.columns, explicit_col="")
        has_row_keys = {"election_ym", "prv_code", "p_code", "list_pos"}.issubset(sample.columns)
        has_candidate = "candidate" in sample.columns
        if id_col and (has_row_keys or has_candidate):
            return str(path)
    return ""


def _read_table_with_auto_format(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def merge_person_id_map(
    df: pd.DataFrame,
    person_id_map_path: Path,
    person_id_col: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not person_id_map_path.exists():
        raise ValueError(
            "Person-ID map not found. Run:\n"
            "python3 src/data/build_person_id.py --data data/processed/spain_master_dataset.csv "
            "--method exact --output-map-csv data/processed/person_id_map.csv"
        )

    base = df.copy()
    map_df = _read_table_with_auto_format(person_id_map_path)
    if person_id_col not in map_df.columns:
        raise ValueError(
            f"Column '{person_id_col}' not found in person-ID map: {person_id_map_path}"
        )

    row_keys = ["election_ym", "prv_code", "p_code", "list_pos"]
    using_row_keys = set(row_keys).issubset(base.columns) and set(row_keys).issubset(map_df.columns)
    using_candidate = "candidate" in base.columns and "candidate" in map_df.columns

    if using_row_keys:
        key_cols = row_keys
        map_use = (
            map_df[key_cols + [person_id_col]]
            .dropna(subset=[person_id_col])
            .drop_duplicates(subset=key_cols, keep="first")
            .rename(columns={person_id_col: "_map_person_id"})
        )
        merge_mode = "row_keys"
    elif using_candidate:
        key_cols = ["candidate"]
        map_use = (
            map_df[key_cols + [person_id_col]]
            .dropna(subset=[person_id_col])
            .drop_duplicates(subset=key_cols, keep="first")
            .rename(columns={person_id_col: "_map_person_id"})
        )
        merge_mode = "candidate"
    else:
        raise ValueError(
            "Person-ID map merge failed: need either row keys "
            "(election_ym, prv_code, p_code, list_pos) or candidate."
        )

    merged = base.merge(map_use, on=key_cols, how="left")
    unmatched = int(merged["_map_person_id"].isna().sum())
    if unmatched > 0:
        raise ValueError(
            f"Person-ID map merge produced {unmatched} unmatched rows. "
            "Rebuild map from the same dataset using src/data/build_person_id.py."
        )

    merged["person_id"] = merged["_map_person_id"].astype(str)
    merged = merged.drop(columns=["_map_person_id"])

    summary = pd.DataFrame(
        [
            {
                "person_id_map_path": str(person_id_map_path),
                "person_id_col": person_id_col,
                "merge_mode": merge_mode,
                "n_rows_input": int(len(base)),
                "n_rows_map": int(len(map_df)),
                "n_rows_merged": int(len(merged)),
                "n_unmatched": unmatched,
                "n_unique_person_id": int(merged["person_id"].nunique()),
            }
        ]
    )
    return merged, summary


def _cluster_names_linktransformer(
    unique_names: pd.DataFrame,
    distance_threshold: float,
    max_block_size: int,
) -> tuple[pd.DataFrame, dict[str, float | int | str]]:
    try:
        import linktransformer as lt
    except Exception as exc:
        raise RuntimeError(f"LinkTransformer is not available: {exc}") from exc

    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform
    from sklearn.metrics.pairwise import cosine_similarity

    model = lt.load_model("sentence-transformers/multi-qa-MiniLM-L6-cos-v1")

    names = unique_names.reset_index(drop=True).copy()
    n = len(names)
    parent = np.arange(n, dtype=int)
    rank = np.zeros(n, dtype=int)

    def _find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(a: int, b: int) -> None:
        ra, rb = _find(a), _find(b)
        if ra == rb:
            return
        if rank[ra] < rank[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        if rank[ra] == rank[rb]:
            rank[ra] += 1

    # Always unify exact normalized matches.
    for _, idx in names.groupby("candidate_match_norm", dropna=False).groups.items():
        idx_list = list(idx)
        for j in idx_list[1:]:
            _union(idx_list[0], int(j))

    blocks = names.groupby("match_block", dropna=False).groups
    blocks_total = int(len(blocks))
    blocks_skipped = 0
    blocks_processed = 0
    links_added = 0

    for _, idx in blocks.items():
        idx_list = [int(v) for v in list(idx)]
        if len(idx_list) <= 1:
            continue
        if len(idx_list) > max_block_size:
            blocks_skipped += 1
            continue

        block_names = names.loc[idx_list, "candidate_match_norm"].fillna("").tolist()
        embeddings = model.encode(block_names)
        similarity_matrix = cosine_similarity(embeddings)
        distance_matrix = np.maximum(1 - similarity_matrix, 0)

        if len(idx_list) == 2:
            if float(distance_matrix[0, 1]) <= distance_threshold:
                _union(idx_list[0], idx_list[1])
                links_added += 1
            blocks_processed += 1
            continue

        condensed = squareform(distance_matrix, force="tovector", checks=False)
        linkage_matrix = linkage(condensed, method="average")
        cluster_ids = fcluster(linkage_matrix, t=distance_threshold, criterion="distance")
        cluster_frame = pd.DataFrame({"idx": idx_list, "cluster_id": cluster_ids})
        for _, cluster_idx in cluster_frame.groupby("cluster_id")["idx"]:
            cluster_list = cluster_idx.tolist()
            for j in cluster_list[1:]:
                _union(cluster_list[0], int(j))
                links_added += 1
        blocks_processed += 1

    roots = np.array([_find(i) for i in range(n)], dtype=int)
    root_labels = pd.Series(roots).astype("category").cat.codes + 1
    names["person_id"] = root_labels.map(lambda x: f"pid_lt_{int(x):06d}")

    stats = {
        "blocks_total": blocks_total,
        "blocks_processed": blocks_processed,
        "blocks_skipped_over_max": blocks_skipped,
        "pair_links_added": int(links_added),
    }
    return names[["candidate", "candidate_match_norm", "person_id"]], stats


def _token_guard_pass(name_a: str, name_b: str, similarity: float, sim_threshold: float) -> bool:
    if similarity >= 0.985:
        return True
    tokens_a = name_a.split()
    tokens_b = name_b.split()
    if not tokens_a or not tokens_b:
        return False
    set_a, set_b = set(tokens_a), set(tokens_b)
    jaccard = len(set_a & set_b) / max(len(set_a | set_b), 1)
    same_last = tokens_a[-1] == tokens_b[-1]
    return similarity >= sim_threshold and (jaccard >= 0.60 or same_last)


def _cluster_names_heuristic(
    unique_names: pd.DataFrame,
    similarity_threshold: float,
    max_block_size: int,
) -> tuple[pd.DataFrame, dict[str, float | int | str]]:
    names = unique_names.reset_index(drop=True).copy()
    n = len(names)
    parent = np.arange(n, dtype=int)
    rank = np.zeros(n, dtype=int)

    def _find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(a: int, b: int) -> None:
        ra, rb = _find(a), _find(b)
        if ra == rb:
            return
        if rank[ra] < rank[rb]:
            ra, rb = rb, ra
        parent[rb] = ra
        if rank[ra] == rank[rb]:
            rank[ra] += 1

    # Always unify exact normalized matches.
    for _, idx in names.groupby("candidate_match_norm", dropna=False).groups.items():
        idx_list = list(idx)
        for j in idx_list[1:]:
            _union(idx_list[0], int(j))

    blocks = names.groupby("match_block", dropna=False).groups
    blocks_total = int(len(blocks))
    blocks_skipped = 0
    blocks_processed = 0
    pairs_tested = 0
    links_added = 0

    for _, idx in blocks.items():
        idx_list = [int(v) for v in list(idx)]
        m = len(idx_list)
        if m <= 1:
            continue
        if m > max_block_size:
            blocks_skipped += 1
            continue

        block_names = names.loc[idx_list, "candidate_match_norm"].fillna("").tolist()
        for i in range(m):
            name_i = block_names[i]
            if not name_i:
                continue
            for j in range(i + 1, m):
                name_j = block_names[j]
                if not name_j:
                    continue
                if abs(len(name_i) - len(name_j)) > 8:
                    continue
                pairs_tested += 1
                sim = SequenceMatcher(None, name_i, name_j).ratio()
                if sim < similarity_threshold:
                    continue
                if _token_guard_pass(name_i, name_j, sim, similarity_threshold):
                    _union(idx_list[i], idx_list[j])
                    links_added += 1
        blocks_processed += 1

    roots = np.array([_find(i) for i in range(n)], dtype=int)
    root_labels = pd.Series(roots).astype("category").cat.codes + 1
    names["person_id"] = root_labels.map(lambda x: f"pid_h_{int(x):06d}")

    stats = {
        "blocks_total": blocks_total,
        "blocks_processed": blocks_processed,
        "blocks_skipped_over_max": blocks_skipped,
        "pairs_tested": int(pairs_tested),
        "pair_links_added": int(links_added),
    }
    return names[["candidate", "candidate_match_norm", "person_id"]], stats


def assign_stable_person_id(
    df: pd.DataFrame,
    method: str,
    panel_id_csv: str,
    panel_id_col: str,
    lt_distance_threshold: float,
    fuzzy_sim_threshold: float,
    max_block_size: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = df.copy()
    _assert_columns(out, ["candidate"])
    out["candidate_match_norm"] = out["candidate"].map(_normalize_person_name)
    out["match_block"] = out["candidate_match_norm"].map(_name_block_key)

    unique_names = out[["candidate", "candidate_match_norm", "match_block"]].drop_duplicates()
    used_method = ""
    method_detail = ""
    stats: dict[str, float | int | str] = {}

    # 1) Existing in dataset.
    existing_col = _resolve_person_id_col(out.columns, explicit_col="")
    if method in {"auto", "existing"} and existing_col:
        out["person_id"] = out[existing_col].astype(str).str.strip()
        out["person_id"] = out["person_id"].where(out["person_id"].ne(""), pd.NA)
        out["person_id"] = out["person_id"].where(
            ~out["person_id"].str.lower().isin(["nan", "none", "<na>"]),
            pd.NA,
        )
        used_method = "existing_column"
        method_detail = existing_col

    # 2) External panel-id file.
    if used_method == "" and panel_id_csv and method in {"auto", "existing"}:
        panel_path = Path(panel_id_csv)
        if not panel_path.exists():
            raise ValueError(f"--panel-id-csv does not exist: {panel_path}")
        panel_df = _read_table_with_auto_format(panel_path)
        resolved_panel_col = _resolve_person_id_col(panel_df.columns, explicit_col=panel_id_col)
        if not resolved_panel_col:
            raise ValueError("Could not resolve person/panel ID column in --panel-id-csv.")

        merge_keys = ["election_ym", "prv_code", "p_code", "list_pos"]
        if set(merge_keys).issubset(panel_df.columns) and set(merge_keys).issubset(out.columns):
            lookup = (
                panel_df[merge_keys + [resolved_panel_col]]
                .dropna(subset=[resolved_panel_col])
                .drop_duplicates(subset=merge_keys, keep="first")
                .rename(columns={resolved_panel_col: "_external_person_id"})
            )
            out = out.merge(lookup, on=merge_keys, how="left")
            out["person_id"] = out["_external_person_id"].astype("string")
            out = out.drop(columns=["_external_person_id"])
            used_method = "external_panel_id"
            method_detail = f"{panel_path}:{resolved_panel_col}:row_keys"
        elif "candidate" in panel_df.columns and "candidate" in out.columns:
            lookup = (
                panel_df[["candidate", resolved_panel_col]]
                .dropna(subset=[resolved_panel_col])
                .drop_duplicates(subset=["candidate"], keep="first")
                .rename(columns={resolved_panel_col: "_external_person_id"})
            )
            out = out.merge(lookup, on="candidate", how="left")
            out["person_id"] = out["_external_person_id"].astype("string")
            out = out.drop(columns=["_external_person_id"])
            used_method = "external_panel_id"
            method_detail = f"{panel_path}:{resolved_panel_col}:candidate"
        else:
            raise ValueError(
                "--panel-id-csv cannot be merged. Required either row keys "
                "(election_ym,prv_code,p_code,list_pos) or candidate."
            )

    # 3) LinkTransformer fuzzy clustering.
    if used_method == "" and method in {"auto", "linktransformer"}:
        try:
            name_map, stats = _cluster_names_linktransformer(
                unique_names=unique_names,
                distance_threshold=lt_distance_threshold,
                max_block_size=max_block_size,
            )
            out = out.merge(name_map, on=["candidate", "candidate_match_norm"], how="left")
            used_method = "linktransformer"
            method_detail = (
                f"distance_threshold={lt_distance_threshold:.4f},"
                f"max_block_size={max_block_size}"
            )
        except Exception as exc:
            if method == "linktransformer":
                raise
            stats["linktransformer_error"] = str(exc)

    # 4) Conservative local fallback fuzzy clustering.
    if used_method == "":
        name_map, heuristic_stats = _cluster_names_heuristic(
            unique_names=unique_names,
            similarity_threshold=fuzzy_sim_threshold,
            max_block_size=max_block_size,
        )
        stats.update(heuristic_stats)
        out = out.merge(name_map, on=["candidate", "candidate_match_norm"], how="left")
        used_method = "heuristic_fuzzy"
        method_detail = (
            f"similarity_threshold={fuzzy_sim_threshold:.4f},"
            f"max_block_size={max_block_size}"
        )

    # If existing/panel IDs are only partially available, fill uncovered names with heuristic clusters.
    missing_pid = out["person_id"].isna() | (out["person_id"].astype(str).str.strip() == "")
    if missing_pid.any() and used_method in {"existing_column", "external_panel_id"}:
        missing_unique = (
            out.loc[missing_pid, ["candidate", "candidate_match_norm", "match_block"]]
            .drop_duplicates()
            .copy()
        )
        missing_map, heuristic_stats = _cluster_names_heuristic(
            unique_names=missing_unique,
            similarity_threshold=fuzzy_sim_threshold,
            max_block_size=max_block_size,
        )
        stats.update(
            {f"heuristic_fill_{k}": v for k, v in heuristic_stats.items()}
        )
        missing_lookup = missing_map.rename(columns={"person_id": "_heuristic_person_id"})
        out = out.merge(
            missing_lookup[["candidate", "candidate_match_norm", "_heuristic_person_id"]],
            on=["candidate", "candidate_match_norm"],
            how="left",
        )
        out.loc[missing_pid, "person_id"] = out.loc[missing_pid, "_heuristic_person_id"]
        out = out.drop(columns=["_heuristic_person_id"])
        used_method = f"{used_method}+heuristic_fill"
        method_detail = (
            method_detail
            + f";heuristic_fill_similarity={fuzzy_sim_threshold:.4f},"
            f"max_block_size={max_block_size}"
        )

    # Fill any residual gaps with deterministic candidate-name IDs.
    missing_pid = out["person_id"].isna() | (out["person_id"].astype(str).str.strip() == "")
    if missing_pid.any():
        fallback = (
            out.loc[missing_pid, ["candidate"]]
            .drop_duplicates()
            .assign(_fallback_id=lambda d: "pid_fb_" + (d.index.astype(str)))
        )
        out = out.merge(fallback, on="candidate", how="left")
        out.loc[missing_pid, "person_id"] = out.loc[missing_pid, "_fallback_id"]
        out = out.drop(columns=["_fallback_id"])

    cluster_sizes = out.groupby("person_id")["candidate"].nunique().rename("n_unique_candidate_names")
    multi_name_person_ids = int((cluster_sizes > 1).sum())
    row_cluster_sizes = out.groupby("person_id").size()
    rows_in_multi_name = int(
        row_cluster_sizes[row_cluster_sizes.index.isin(cluster_sizes[cluster_sizes > 1].index)].sum()
    )
    validation = {
        "method_requested": method,
        "method_used": used_method,
        "method_detail": method_detail,
        "n_rows": int(len(out)),
        "n_unique_candidate_strings": int(out["candidate"].nunique()),
        "n_unique_person_id": int(out["person_id"].nunique()),
        "n_person_ids_with_multiple_candidate_names": multi_name_person_ids,
        "rows_in_multi_name_person_ids": rows_in_multi_name,
        "share_rows_in_multi_name_person_ids": (
            float(rows_in_multi_name / len(out)) if len(out) else np.nan
        ),
        "largest_row_cluster_size": int(row_cluster_sizes.max()) if len(row_cluster_sizes) else 0,
        "lt_distance_threshold": lt_distance_threshold,
        "heuristic_similarity_threshold": fuzzy_sim_threshold,
        "max_block_size": max_block_size,
    }
    validation.update(stats)

    out["person_id"] = out["person_id"].astype(str)
    out["person_id_source"] = used_method
    return out, pd.DataFrame([validation])


def _build_next_outcomes_by_id(
    df: pd.DataFrame,
    id_col: str,
    prefix: str,
) -> pd.DataFrame:
    required = [id_col, "prv_code", "election_ym", "next_election_ym", "elected_dta"]
    _assert_columns(df, required)

    out = df.copy()
    same_run_col = f"runs_next_{prefix}_same_prv"
    same_win_col = f"wins_next_{prefix}_same_prv"
    any_run_col = f"runs_next_{prefix}_any_prv"
    any_win_col = f"wins_next_{prefix}_any_prv"

    panel_same = (
        out.groupby([id_col, "prv_code", "election_ym"], as_index=False)
        .agg(elected=("elected_dta", "max"))
        .assign(runs=1)
    )
    next_same = panel_same.rename(
        columns={
            "election_ym": "next_election_ym",
            "runs": same_run_col,
            "elected": same_win_col,
        }
    )
    out = out.merge(next_same, on=[id_col, "prv_code", "next_election_ym"], how="left")

    panel_any = (
        out.groupby([id_col, "election_ym"], as_index=False)
        .agg(elected=("elected_dta", "max"))
        .assign(runs=1)
    )
    next_any = panel_any.rename(
        columns={
            "election_ym": "next_election_ym",
            "runs": any_run_col,
            "elected": any_win_col,
        }
    )
    out = out.merge(next_any, on=[id_col, "next_election_ym"], how="left")

    has_next = out["next_election_ym"].notna()
    for col in [same_run_col, same_win_col, any_run_col, any_win_col]:
        out.loc[has_next, col] = out.loc[has_next, col].fillna(0.0)
    return out


def build_next_election_outcomes(df: pd.DataFrame) -> pd.DataFrame:
    required = ["candidate", "person_id", "prv_code", "election_ym", "elected_dta"]
    _assert_columns(df, required)

    out = df.copy()
    out["election_ym"] = pd.to_numeric(out["election_ym"], errors="coerce").astype("Int64")

    elections = sorted(out["election_ym"].dropna().unique().tolist())
    next_map = {elections[i]: elections[i + 1] for i in range(len(elections) - 1)}
    next_map[elections[-1]] = pd.NA
    out["next_election_ym"] = out["election_ym"].map(next_map).astype("Int64")

    out = _build_next_outcomes_by_id(out, id_col="candidate", prefix="string")
    out = _build_next_outcomes_by_id(out, id_col="person_id", prefix="person")

    # Main outcomes now use stable person_id in same province.
    out["runs_next_same_prv"] = out["runs_next_person_same_prv"]
    out["wins_next_same_prv"] = out["wins_next_person_same_prv"]
    out["runs_next_any_prv"] = out["runs_next_person_any_prv"]
    out["wins_next_any_prv"] = out["wins_next_person_any_prv"]

    out["runs_next"] = out["runs_next_same_prv"]
    out["wins_next"] = out["wins_next_same_prv"]
    return out


def add_balance_covariates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["female"] = np.where(
        out["sex"] == "F", 1.0, np.where(out["sex"] == "M", 0.0, np.nan)
    )
    out["female_missing"] = out["female"].isna().astype(float)
    out["list_pos"] = pd.to_numeric(out["list_pos"], errors="coerce")
    out["p_seats"] = pd.to_numeric(out["p_seats"], errors="coerce")
    p_votes = pd.to_numeric(out["p_votes"], errors="coerce")
    out["log_p_votes"] = np.log1p(np.clip(p_votes, a_min=0, a_max=None))

    blank_votes = pd.to_numeric(out["blank_votes_dta"], errors="coerce")
    valid_votes = pd.to_numeric(out["valid_votes"], errors="coerce")
    out["blank_vote_share"] = np.where(valid_votes > 0, blank_votes / valid_votes, np.nan)
    return out


def add_lagged_pretreatment_covariates(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    # Party-in-province level variables at election t.
    party_level = (
        out.groupby(["election_ym", "prv_code", "p_code"], as_index=False)
        .agg(
            p_votes_t=("p_votes", "first"),
            p_seats_t=("p_seats", "first"),
            votesforparties_t=("votesforparties", "first"),
        )
    )
    party_level["party_vote_share_t"] = np.where(
        pd.to_numeric(party_level["votesforparties_t"], errors="coerce") > 0,
        pd.to_numeric(party_level["p_votes_t"], errors="coerce")
        / pd.to_numeric(party_level["votesforparties_t"], errors="coerce"),
        np.nan,
    )

    party_level = party_level.sort_values(["prv_code", "p_code", "election_ym"])
    party_level["lag_p_votes"] = party_level.groupby(["prv_code", "p_code"])["p_votes_t"].shift(1)
    party_level["lag_p_seats"] = party_level.groupby(["prv_code", "p_code"])["p_seats_t"].shift(1)
    party_level["lag_party_vote_share"] = party_level.groupby(["prv_code", "p_code"])[
        "party_vote_share_t"
    ].shift(1)
    party_level["lag_log_p_votes"] = np.log1p(
        np.clip(pd.to_numeric(party_level["lag_p_votes"], errors="coerce"), a_min=0, a_max=None)
    )
    party_lags = party_level[
        [
            "election_ym",
            "prv_code",
            "p_code",
            "lag_p_votes",
            "lag_p_seats",
            "lag_party_vote_share",
            "lag_log_p_votes",
        ]
    ]

    # Province-level variables at election t.
    province_level = (
        out.groupby(["election_ym", "prv_code"], as_index=False)
        .agg(
            valid_votes_t=("valid_votes", "first"),
            invalid_votes_t=("invalid_votes", "first"),
            blank_votes_t=("blank_votes_dta", "first"),
            eligible_voters_t=("eligible_voters", "first"),
        )
    )
    province_level["province_turnout_t"] = np.where(
        pd.to_numeric(province_level["eligible_voters_t"], errors="coerce") > 0,
        (
            pd.to_numeric(province_level["valid_votes_t"], errors="coerce")
            + pd.to_numeric(province_level["invalid_votes_t"], errors="coerce")
        )
        / pd.to_numeric(province_level["eligible_voters_t"], errors="coerce"),
        np.nan,
    )
    province_level["province_blank_share_t"] = np.where(
        pd.to_numeric(province_level["valid_votes_t"], errors="coerce") > 0,
        pd.to_numeric(province_level["blank_votes_t"], errors="coerce")
        / pd.to_numeric(province_level["valid_votes_t"], errors="coerce"),
        np.nan,
    )

    province_level = province_level.sort_values(["prv_code", "election_ym"])
    province_level["lag_province_turnout"] = province_level.groupby("prv_code")[
        "province_turnout_t"
    ].shift(1)
    province_level["lag_province_blank_share"] = province_level.groupby("prv_code")[
        "province_blank_share_t"
    ].shift(1)
    province_lags = province_level[
        ["election_ym", "prv_code", "lag_province_turnout", "lag_province_blank_share"]
    ]

    out = out.merge(party_lags, on=["election_ym", "prv_code", "p_code"], how="left")
    out = out.merge(province_lags, on=["election_ym", "prv_code"], how="left")
    return out


def _prepare_sample(
    df: pd.DataFrame, running_col: str, outcome_col: str, require_next_election: bool
) -> pd.DataFrame:
    sample = df.copy()
    sample[running_col] = pd.to_numeric(sample[running_col], errors="coerce")
    sample[outcome_col] = pd.to_numeric(sample[outcome_col], errors="coerce")
    sample = sample[sample[running_col].notna() & sample[outcome_col].notna()]
    if require_next_election:
        sample = sample[sample["next_election_ym"].notna()]
    return sample


def _fit_side_linear(
    y: pd.Series,
    x: pd.Series,
    bandwidth: float,
    se_type: str,
    cluster_groups: pd.Series | None = None,
):
    weights = 1.0 - (np.abs(x) / bandwidth)
    design = pd.DataFrame({"const": 1.0, "x": x.astype(float)})
    model = sm.WLS(y.astype(float), design, weights=weights.astype(float))

    if se_type == "hc1":
        return model.fit(cov_type="HC1")

    if se_type.startswith("cluster"):
        if cluster_groups is None:
            raise ValueError("cluster_groups must be provided for clustered SE.")
        groups = pd.Series(cluster_groups).astype(str)
        if groups.nunique() < 2:
            return model.fit(cov_type="HC1")
        return model.fit(cov_type="cluster", cov_kwds={"groups": groups})

    raise ValueError(f"Unsupported se_type: {se_type}")


def _build_cluster_groups(window: pd.DataFrame, se_type: str) -> pd.Series | None:
    if se_type == "hc1":
        return None
    if se_type == "cluster_prv_election":
        _assert_columns(window, ["prv_code", "election_ym"])
        return (
            pd.to_numeric(window["prv_code"], errors="coerce").astype("Int64").astype(str)
            + "|"
            + pd.to_numeric(window["election_ym"], errors="coerce").astype("Int64").astype(str)
        )
    if se_type == "cluster_prv_election_party":
        _assert_columns(window, ["prv_code", "election_ym", "p_code"])
        return (
            pd.to_numeric(window["prv_code"], errors="coerce").astype("Int64").astype(str)
            + "|"
            + pd.to_numeric(window["election_ym"], errors="coerce").astype("Int64").astype(str)
            + "|"
            + pd.to_numeric(window["p_code"], errors="coerce").astype("Int64").astype(str)
        )
    raise ValueError(f"Unsupported cluster se_type: {se_type}")


def _extract_const_var(fit) -> float:
    cov = fit.cov_params()
    if hasattr(cov, "loc"):
        return float(cov.loc["const", "const"])
    return float(cov[0, 0])


def estimate_local_linear_rd(
    sample: pd.DataFrame,
    outcome_col: str,
    running_col: str,
    bandwidth: float,
    min_side_n: int,
    analysis_type: str,
    se_type: str = "hc1",
    donut: float = 0.0,
) -> RddEstimate:
    window = sample[sample[running_col].between(-bandwidth, bandwidth)].copy()
    if donut > 0:
        window = window[np.abs(window[running_col]) >= donut].copy()
    left = window[window[running_col] < 0]
    right = window[window[running_col] >= 0]

    if len(left) < min_side_n or len(right) < min_side_n:
        raise ValueError(
            f"Insufficient observations in window for {analysis_type}:{outcome_col}: "
            f"left={len(left)}, right={len(right)}, min={min_side_n}, bw={bandwidth}"
        )

    # Pooled local-linear regression:
    #   Y = alpha + beta*X + tau*T + gamma*(T*X) + epsilon
    # T = 1(X >= 0) allows different intercepts (tau) and slopes (gamma) across cutoff.
    # This correctly handles within-cluster covariance across the cutoff for
    # clustered SEs, unlike the separate-regressions approach.
    x_vals = pd.to_numeric(window[running_col], errors="coerce").astype(float).values
    y_vals = pd.to_numeric(window[outcome_col], errors="coerce").astype(float).values
    t_vals = (x_vals >= 0).astype(float)
    w_vals = 1.0 - (np.abs(x_vals) / bandwidth)

    design = pd.DataFrame(
        {"const": 1.0, "x": x_vals, "T": t_vals, "Tx": t_vals * x_vals},
        index=window.index,
    )
    model = sm.WLS(y_vals, design, weights=w_vals)

    cluster_groups = None
    n_clusters_total = 0
    df_inference = np.inf  # large-sample normal by default

    if se_type == "hc1":
        fit = model.fit(cov_type="HC1")
    else:
        cluster_groups = _build_cluster_groups(window, se_type=se_type)
        n_clusters_total = int(cluster_groups.nunique())
        if n_clusters_total < 2:
            fit = model.fit(cov_type="HC1")
        else:
            fit = model.fit(cov_type="cluster", cov_kwds={"groups": cluster_groups})
            # Degrees of freedom: G - 1 (conservative for cluster-robust inference).
            df_inference = float(n_clusters_total - 1)

    tau = float(fit.params["T"])
    se = float(np.sqrt(fit.cov_params().loc["T", "T"]))
    mean_left = float(left[outcome_col].astype(float).mean())
    mean_right = float(right[outcome_col].astype(float).mean())

    # Inference: use t-distribution for clustered SEs with finite clusters.
    if se > 0:
        if np.isfinite(df_inference) and df_inference < 1000:
            effective_df = max(df_inference, 1.0)
            t_stat = tau / se
            p_value = float(2 * (1 - t_dist.cdf(abs(t_stat), effective_df)))
            t_crit = float(t_dist.ppf(0.975, effective_df))
            ci95_low = float(tau - t_crit * se)
            ci95_high = float(tau + t_crit * se)
        else:
            z = tau / se
            p_value = float(2 * (1 - norm.cdf(abs(z))))
            ci95_low = float(tau - 1.96 * se)
            ci95_high = float(tau + 1.96 * se)
    else:
        p_value = np.nan
        ci95_low = np.nan
        ci95_high = np.nan

    # Cluster counts per side (for reporting).
    left_groups = _build_cluster_groups(left.copy(), se_type=se_type) if se_type != "hc1" else None
    right_groups = _build_cluster_groups(right.copy(), se_type=se_type) if se_type != "hc1" else None

    return RddEstimate(
        analysis_type=analysis_type,
        outcome=outcome_col,
        bandwidth=bandwidth,
        se_type=se_type,
        cluster_spec=se_type if se_type != "hc1" else "none",
        n_clusters_left=int(pd.Series(left_groups).nunique()) if left_groups is not None else 0,
        n_clusters_right=int(pd.Series(right_groups).nunique()) if right_groups is not None else 0,
        n_window=int(len(window)),
        n_left=int(len(left)),
        n_right=int(len(right)),
        mean_left=mean_left,
        mean_right=mean_right,
        tau=float(tau),
        se=se,
        ci95_low=ci95_low,
        ci95_high=ci95_high,
        p_value=p_value,
    )


def plot_rdd_binned(
    sample: pd.DataFrame,
    outcome_col: str,
    running_col: str,
    bandwidth: float,
    bins_per_side: int,
    output_path: Path,
) -> None:
    window = sample[sample[running_col].between(-bandwidth, bandwidth)].copy()
    left = window[window[running_col] < 0].copy()
    right = window[window[running_col] >= 0].copy()

    left_fit = _fit_side_linear(
        left[outcome_col],
        left[running_col],
        bandwidth,
        se_type="hc1",
    )
    right_fit = _fit_side_linear(
        right[outcome_col],
        right[running_col],
        bandwidth,
        se_type="hc1",
    )

    left_edges = np.linspace(-bandwidth, 0.0, bins_per_side + 1)
    right_edges = np.linspace(0.0, bandwidth, bins_per_side + 1)

    left["_bin"] = pd.cut(
        left[running_col], bins=left_edges, include_lowest=True, labels=False
    )
    right["_bin"] = pd.cut(
        right[running_col], bins=right_edges, include_lowest=True, labels=False
    )

    left_bins = left.groupby("_bin", dropna=True).agg(
        x=(running_col, "mean"), y=(outcome_col, "mean")
    )
    right_bins = right.groupby("_bin", dropna=True).agg(
        x=(running_col, "mean"), y=(outcome_col, "mean")
    )

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(left_bins["x"], left_bins["y"], color="#1f77b4", alpha=0.85, label="Left bins")
    ax.scatter(right_bins["x"], right_bins["y"], color="#d62728", alpha=0.85, label="Right bins")

    x_left = np.linspace(-bandwidth, 0.0, 200, endpoint=False)
    x_right = np.linspace(0.0, bandwidth, 200)
    y_left = left_fit.params["const"] + left_fit.params["x"] * x_left
    y_right = right_fit.params["const"] + right_fit.params["x"] * x_right
    ax.plot(x_left, y_left, color="#1f77b4", linewidth=2.0)
    ax.plot(x_right, y_right, color="#d62728", linewidth=2.0)

    ax.axvline(0.0, color="black", linestyle="--", linewidth=1.0)
    ax.set_xlabel("Running Variable")
    ax.set_ylabel(outcome_col)
    ax.set_title(f"RDD Binned Plot: {outcome_col} (bw={bandwidth:.3f})")
    ax.legend(loc="best")
    ax.grid(alpha=0.2)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def plot_bandwidth_sensitivity(
    estimates_df: pd.DataFrame, output_path: Path, title: str, se_type_filter: str = "hc1"
) -> None:
    if "se_type" in estimates_df.columns:
        plot_df = estimates_df[estimates_df["se_type"] == se_type_filter].copy()
        if plot_df.empty:
            plot_df = estimates_df.copy()
    else:
        plot_df = estimates_df.copy()

    outcomes = sorted(plot_df["outcome"].unique().tolist())
    n_outcomes = len(outcomes)
    fig, axes = plt.subplots(1, n_outcomes, figsize=(7 * n_outcomes, 5), squeeze=False)

    for idx, outcome in enumerate(outcomes):
        ax = axes[0, idx]
        sub = plot_df[plot_df["outcome"] == outcome].sort_values("bandwidth")
        x = sub["bandwidth"].to_numpy()
        y = sub["tau"].to_numpy()
        yerr = 1.96 * sub["se"].to_numpy()
        ax.errorbar(x, y, yerr=yerr, fmt="o-", capsize=4, color="#1f77b4")
        ax.axhline(0.0, color="black", linestyle="--", linewidth=1.0)
        ax.set_xlabel("Bandwidth")
        ax.set_ylabel("Estimated Jump (tau)")
        ax.set_title(outcome)
        ax.grid(alpha=0.2)

    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def _fit_log_density_side(bin_side: pd.DataFrame, bandwidth: float):
    work = bin_side.copy()
    work = work[(work["count"] > 0) & work["bin_center"].notna() & work["bin_width"].notna()].copy()
    if len(work) < 3:
        return None
    work["log_count_density"] = np.log(work["count"] / work["bin_width"])
    work["tri_weight"] = work["count"] * np.clip(1 - (np.abs(work["bin_center"]) / bandwidth), 0, None)
    work = work[work["tri_weight"] > 0].copy()
    if len(work) < 3:
        return None

    design = pd.DataFrame({"const": 1.0, "x": work["bin_center"].astype(float)})
    model = sm.WLS(
        work["log_count_density"].astype(float),
        design,
        weights=work["tri_weight"].astype(float),
    )
    return model.fit(cov_type="HC1")


def run_running_variable_density_diagnostics(
    df: pd.DataFrame,
    running_col: str,
    bandwidth_grid: list[float],
    bins_per_side: int,
    min_bins_for_test: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = df.copy()
    work[running_col] = pd.to_numeric(work[running_col], errors="coerce")
    work = work[work[running_col].notna()].copy()

    bin_rows: list[pd.DataFrame] = []
    summary_rows: list[dict[str, float | int | str]] = []

    n_bins_per_side = max(int(bins_per_side), 2)
    n_bins_total = 2 * n_bins_per_side

    for bw in bandwidth_grid:
        window = work[work[running_col].between(-bw, bw)].copy()
        n_window = int(len(window))
        n_left = int((window[running_col] < 0).sum())
        n_right = int((window[running_col] >= 0).sum())

        edges = np.linspace(-bw, bw, n_bins_total + 1)
        bin_width = float((2 * bw) / n_bins_total)

        if n_window > 0:
            bin_id = pd.cut(
                window[running_col],
                bins=edges,
                include_lowest=True,
                labels=False,
            )
            count_map = bin_id.value_counts().to_dict()
        else:
            count_map = {}

        bins_df = pd.DataFrame({"bin_idx": np.arange(n_bins_total, dtype=int)})
        bins_df["bandwidth"] = bw
        bins_df["bin_left"] = edges[:-1]
        bins_df["bin_right"] = edges[1:]
        bins_df["bin_center"] = (bins_df["bin_left"] + bins_df["bin_right"]) / 2
        bins_df["bin_width"] = bin_width
        bins_df["side"] = np.where(bins_df["bin_center"] < 0, "left", "right")
        bins_df["count"] = bins_df["bin_idx"].map(count_map).fillna(0).astype(int)
        bins_df["share"] = np.where(n_window > 0, bins_df["count"] / n_window, np.nan)
        bins_df["density"] = np.where(
            n_window > 0,
            bins_df["count"] / (n_window * bins_df["bin_width"]),
            np.nan,
        )
        bins_df["plot_bin"] = np.where(
            bins_df["side"] == "left",
            -(n_bins_per_side - bins_df["bin_idx"]),
            bins_df["bin_idx"] - n_bins_per_side + 1,
        )

        left_mask = bins_df["side"] == "left"
        right_mask = bins_df["side"] == "right"
        bins_df.loc[left_mask, "bin_in_side"] = np.arange(left_mask.sum(), dtype=int)
        bins_df.loc[right_mask, "bin_in_side"] = np.arange(right_mask.sum(), dtype=int)
        bins_df["bin_in_side"] = pd.to_numeric(bins_df["bin_in_side"], errors="coerce").astype("Int64")
        bins_df["plot_bin"] = pd.to_numeric(bins_df["plot_bin"], errors="coerce").astype("Int64")

        left_bins = bins_df[left_mask].sort_values("bin_center")
        right_bins = bins_df[right_mask].sort_values("bin_center")
        left_near_count = int(left_bins["count"].iloc[-1]) if not left_bins.empty else 0
        right_near_count = int(right_bins["count"].iloc[0]) if not right_bins.empty else 0
        count_ratio_near0 = (
            float(right_near_count / left_near_count) if left_near_count > 0 else np.nan
        )
        count_ratio_near0_add05 = float((right_near_count + 0.5) / (left_near_count + 0.5))
        log_count_ratio_near0_add05 = float(np.log(count_ratio_near0_add05))

        left_nonzero = left_bins[left_bins["count"] > 0].copy()
        right_nonzero = right_bins[right_bins["count"] > 0].copy()
        formal_test_feasible = (
            len(left_nonzero) >= min_bins_for_test and len(right_nonzero) >= min_bins_for_test
        )

        log_density_jump = np.nan
        log_density_jump_se = np.nan
        log_density_jump_ci95_low = np.nan
        log_density_jump_ci95_high = np.nan
        log_density_jump_p_value = np.nan
        implied_density_ratio = np.nan

        if formal_test_feasible:
            left_fit = _fit_log_density_side(left_nonzero, bandwidth=bw)
            right_fit = _fit_log_density_side(right_nonzero, bandwidth=bw)
            if left_fit is not None and right_fit is not None:
                left_intercept = float(left_fit.params["const"])
                right_intercept = float(right_fit.params["const"])
                log_density_jump = right_intercept - left_intercept
                var_left = float(left_fit.cov_params().loc["const", "const"])
                var_right = float(right_fit.cov_params().loc["const", "const"])
                log_density_jump_se = float(np.sqrt(var_left + var_right))
                if log_density_jump_se > 0:
                    z = log_density_jump / log_density_jump_se
                    log_density_jump_p_value = float(2 * (1 - norm.cdf(abs(z))))
                    log_density_jump_ci95_low = float(log_density_jump - 1.96 * log_density_jump_se)
                    log_density_jump_ci95_high = float(log_density_jump + 1.96 * log_density_jump_se)
                implied_density_ratio = float(np.exp(log_density_jump))
            else:
                formal_test_feasible = False

        bins_df["count_ratio_near0"] = count_ratio_near0
        bins_df["count_ratio_near0_add05"] = count_ratio_near0_add05
        bins_df["log_count_ratio_near0_add05"] = log_count_ratio_near0_add05
        bins_df["formal_test_feasible"] = int(formal_test_feasible)
        bins_df["log_density_jump"] = log_density_jump
        bins_df["log_density_jump_se"] = log_density_jump_se
        bins_df["log_density_jump_p_value"] = log_density_jump_p_value
        bins_df["implied_density_ratio_at_cutoff"] = implied_density_ratio
        bin_rows.append(bins_df)

        summary_rows.append(
            {
                "bandwidth": bw,
                "n_window": n_window,
                "n_left": n_left,
                "n_right": n_right,
                "bins_per_side": n_bins_per_side,
                "n_bins_total": n_bins_total,
                "bin_width": bin_width,
                "left_bins_nonzero": int(len(left_nonzero)),
                "right_bins_nonzero": int(len(right_nonzero)),
                "left_near0_count": left_near_count,
                "right_near0_count": right_near_count,
                "count_ratio_right_over_left_near0": count_ratio_near0,
                "count_ratio_right_over_left_near0_add05": count_ratio_near0_add05,
                "log_count_ratio_near0_add05": log_count_ratio_near0_add05,
                "formal_test_feasible": int(formal_test_feasible),
                "formal_test_name": "mccrary_style_local_linear_log_bin_density",
                "log_density_jump": log_density_jump,
                "log_density_jump_se": log_density_jump_se,
                "log_density_jump_ci95_low": log_density_jump_ci95_low,
                "log_density_jump_ci95_high": log_density_jump_ci95_high,
                "log_density_jump_p_value": log_density_jump_p_value,
                "implied_density_ratio_at_cutoff": implied_density_ratio,
            }
        )

    all_bins_df = pd.concat(bin_rows, ignore_index=True)
    all_bins_df = all_bins_df.sort_values(["bandwidth", "bin_center"]).reset_index(drop=True)
    summary_df = pd.DataFrame(summary_rows).sort_values("bandwidth").reset_index(drop=True)
    return all_bins_df, summary_df


def plot_running_variable_density_diagnostics(
    density_bins_df: pd.DataFrame,
    density_summary_df: pd.DataFrame,
    fig_dir: Path,
) -> list[Path]:
    fig_dir.mkdir(parents=True, exist_ok=True)
    output_paths: list[Path] = []
    bandwidths = sorted(density_bins_df["bandwidth"].dropna().unique().tolist())

    for bw in bandwidths:
        sub = density_bins_df[density_bins_df["bandwidth"] == bw].copy().sort_values("bin_center")
        if sub.empty:
            continue
        summary_sub = density_summary_df[density_summary_df["bandwidth"] == bw]
        summary_row = summary_sub.iloc[0] if not summary_sub.empty else None

        bin_width = float(sub["bin_width"].iloc[0])
        left = sub[sub["side"] == "left"]
        right = sub[sub["side"] == "right"]

        fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
        ax_hist, ax_density = axes

        bar_colors = np.where(sub["side"] == "left", "#1f77b4", "#d62728")
        ax_hist.bar(
            sub["bin_center"],
            sub["count"],
            width=0.95 * bin_width,
            color=bar_colors,
            alpha=0.85,
            edgecolor="white",
            linewidth=0.4,
        )
        ax_hist.axvline(0.0, color="black", linestyle="--", linewidth=1.0)
        ax_hist.set_title(f"Histogram of Running Variable (h={bw:.3f})")
        ax_hist.set_xlabel("Running variable")
        ax_hist.set_ylabel("Bin count")
        ax_hist.grid(alpha=0.2)

        ax_density.plot(
            left["bin_center"],
            left["density"],
            "o-",
            color="#1f77b4",
            label="Left bins",
            alpha=0.9,
        )
        ax_density.plot(
            right["bin_center"],
            right["density"],
            "o-",
            color="#d62728",
            label="Right bins",
            alpha=0.9,
        )
        ax_density.axvline(0.0, color="black", linestyle="--", linewidth=1.0)
        ax_density.set_title(f"Binned Density of Running Variable (h={bw:.3f})")
        ax_density.set_xlabel("Running variable")
        ax_density.set_ylabel("Estimated density")
        ax_density.grid(alpha=0.2)
        ax_density.legend(loc="best")

        if summary_row is not None:
            ratio = summary_row["count_ratio_right_over_left_near0"]
            jump = summary_row["log_density_jump"]
            pval = summary_row["log_density_jump_p_value"]
            ratio_text = f"{ratio:.3f}" if pd.notna(ratio) else "NA"
            jump_text = f"{jump:.3f}" if pd.notna(jump) else "NA"
            p_text = f"{pval:.3f}" if pd.notna(pval) else "NA"
            annotation = (
                f"Near-0 count ratio R/L: {ratio_text}\n"
                f"Log density jump: {jump_text}\n"
                f"p-value: {p_text}"
            )
            ax_density.text(
                0.02,
                0.98,
                annotation,
                transform=ax_density.transAxes,
                va="top",
                ha="left",
                fontsize=9,
                bbox={"facecolor": "white", "alpha": 0.9, "edgecolor": "none"},
            )

        fig.tight_layout()
        output_path = fig_dir / f"rdd_running_density_bw{_safe_bw_label(float(bw))}.png"
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        output_paths.append(output_path)

    return output_paths


def _count_sides_in_bandwidth(sample: pd.DataFrame, running_col: str, bandwidth: float) -> tuple[int, int]:
    window = sample[sample[running_col].between(-bandwidth, bandwidth)]
    n_left = int((window[running_col] < 0).sum())
    n_right = int((window[running_col] >= 0).sum())
    return n_left, n_right


def _min_bandwidth_for_side_counts(sample: pd.DataFrame, running_col: str, min_side_n: int) -> float:
    x = pd.to_numeric(sample[running_col], errors="coerce")
    left = np.sort(np.abs(x[x < 0].to_numpy()))
    right = np.sort(np.abs(x[x >= 0].to_numpy()))
    if len(left) < min_side_n or len(right) < min_side_n:
        raise ValueError(
            f"Insufficient support for bandwidth selection: left={len(left)}, right={len(right)}, "
            f"required={min_side_n}"
        )
    return float(max(left[min_side_n - 1], right[min_side_n - 1]))


def _fit_side_quadratic_for_bw(
    sample: pd.DataFrame,
    outcome_col: str,
    running_col: str,
    bandwidth: float,
    side: str,
):
    window = sample[sample[running_col].between(-bandwidth, bandwidth)].copy()
    if side == "left":
        window = window[window[running_col] < 0].copy()
    else:
        window = window[window[running_col] >= 0].copy()

    if len(window) < 10:
        return None

    x = pd.to_numeric(window[running_col], errors="coerce").astype(float)
    y = pd.to_numeric(window[outcome_col], errors="coerce").astype(float)
    w = np.clip(1 - (np.abs(x) / bandwidth), 0, None)

    design = pd.DataFrame({"const": 1.0, "x": x, "x2": np.square(x)})
    try:
        fit = sm.WLS(y, design, weights=w).fit(cov_type="HC1")
    except Exception:
        return None
    return fit


def _fit_side_variance(sample: pd.DataFrame, outcome_col: str, running_col: str, bandwidth: float) -> tuple[float, float]:
    window = sample[sample[running_col].between(-bandwidth, bandwidth)].copy()
    y = pd.to_numeric(window[outcome_col], errors="coerce")
    x = pd.to_numeric(window[running_col], errors="coerce")
    left = y[x < 0]
    right = y[x >= 0]
    var_left = float(left.var(ddof=1)) if len(left) > 1 else np.nan
    var_right = float(right.var(ddof=1)) if len(right) > 1 else np.nan
    return var_left, var_right


def _pick_quantile_bandwidth(
    sample: pd.DataFrame,
    running_col: str,
    quantiles: list[float],
    min_side_n: int,
    multiplier: float = 1.0,
) -> float:
    abs_x = np.abs(pd.to_numeric(sample[running_col], errors="coerce").dropna().to_numpy())
    if len(abs_x) == 0:
        return np.nan
    for q in quantiles:
        h = float(np.quantile(abs_x, q)) * multiplier
        n_left, n_right = _count_sides_in_bandwidth(sample, running_col=running_col, bandwidth=h)
        if n_left >= min_side_n and n_right >= min_side_n:
            return h
    return float(np.quantile(abs_x, quantiles[-1])) * multiplier


def _select_bandwidth_rdrobust(
    sample: pd.DataFrame,
    outcome_col: str,
    running_col: str,
) -> dict[str, float | str] | None:
    try:
        from rdrobust import rdbwselect
    except Exception:
        return None

    x = pd.to_numeric(sample[running_col], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(sample[outcome_col], errors="coerce").to_numpy(dtype=float)

    try:
        result = rdbwselect(y=y, x=x, c=0.0, p=1, q=2, kernel="tri")
    except Exception:
        return None

    bws = getattr(result, "bws", None)
    if bws is None:
        return None

    h_left = np.nan
    h_right = np.nan
    selector_label = ""

    if isinstance(bws, pd.DataFrame):
        preferred_rows = ["mserd", "msecomb1", "msecomb2", "cerrd"]
        row = next((r for r in preferred_rows if r in bws.index), bws.index[0])
        selector_label = str(row)
        values = pd.to_numeric(bws.loc[row], errors="coerce")
        if len(values) >= 2:
            h_left = float(values.iloc[0])
            h_right = float(values.iloc[1])
        elif len(values) == 1:
            h_left = float(values.iloc[0])
            h_right = h_left
    else:
        arr = np.asarray(bws, dtype=float).ravel()
        if arr.size >= 2:
            h_left, h_right = float(arr[0]), float(arr[1])
        elif arr.size == 1:
            h_left = float(arr[0])
            h_right = h_left

    h_raw = float(np.nanmean([h_left, h_right]))
    if not np.isfinite(h_raw) or h_raw <= 0:
        return None

    return {
        "method_used": "rdrobust_cct",
        "selector_detail": selector_label if selector_label else "rdrobust_default",
        "bandwidth_raw": h_raw,
        "bandwidth_left_raw": h_left,
        "bandwidth_right_raw": h_right,
    }


def _select_bandwidth_ik_style(
    sample: pd.DataFrame,
    outcome_col: str,
    running_col: str,
    min_side_n: int,
    reference_bw: float,
) -> dict[str, float | str]:
    abs_x = np.abs(pd.to_numeric(sample[running_col], errors="coerce").dropna().to_numpy())
    if len(abs_x) == 0:
        return {
            "method_used": "ik_style_plugin",
            "selector_detail": "failed_no_running_variable",
            "bandwidth_raw": np.nan,
            "bandwidth_left_raw": np.nan,
            "bandwidth_right_raw": np.nan,
            "pilot_h_curvature": np.nan,
            "pilot_h_variance": np.nan,
            "pilot_h_density": np.nan,
            "m2_left": np.nan,
            "m2_right": np.nan,
            "m2_diff_abs": np.nan,
            "sigma2_left": np.nan,
            "sigma2_right": np.nan,
            "sigma2_sum": np.nan,
            "fhat_cutoff": np.nan,
            "fallback_reason": "no_running_variable",
        }

    h_curv = _pick_quantile_bandwidth(
        sample=sample,
        running_col=running_col,
        quantiles=[0.25, 0.35, 0.45, 0.55, 0.65],
        min_side_n=max(2 * min_side_n, 40),
        multiplier=1.0,
    )
    h_var = _pick_quantile_bandwidth(
        sample=sample,
        running_col=running_col,
        quantiles=[0.15, 0.20, 0.25, 0.30, 0.35],
        min_side_n=max(2 * min_side_n, 40),
        multiplier=1.0,
    )
    h_density = _pick_quantile_bandwidth(
        sample=sample,
        running_col=running_col,
        quantiles=[0.20, 0.30, 0.40, 0.50, 0.60],
        min_side_n=max(2 * min_side_n, 40),
        multiplier=1.0,
    )

    fit_left = _fit_side_quadratic_for_bw(
        sample=sample,
        outcome_col=outcome_col,
        running_col=running_col,
        bandwidth=h_curv,
        side="left",
    )
    fit_right = _fit_side_quadratic_for_bw(
        sample=sample,
        outcome_col=outcome_col,
        running_col=running_col,
        bandwidth=h_curv,
        side="right",
    )

    fallback_reason = ""
    m2_left = np.nan
    m2_right = np.nan
    m2_diff_abs = np.nan
    if fit_left is not None and fit_right is not None:
        m2_left = float(2 * fit_left.params.get("x2", np.nan))
        m2_right = float(2 * fit_right.params.get("x2", np.nan))
        m2_diff_abs = float(np.abs(m2_right - m2_left))
    else:
        fallback_reason = "quadratic_curvature_fit_failed"

    sigma2_left, sigma2_right = _fit_side_variance(
        sample=sample,
        outcome_col=outcome_col,
        running_col=running_col,
        bandwidth=h_var,
    )
    sigma2_sum = np.nansum([sigma2_left, sigma2_right])

    n = int(len(sample))
    count_density = int(sample[sample[running_col].between(-h_density, h_density)].shape[0])
    fhat_cutoff = float(count_density / (2 * h_density * n)) if h_density > 0 and n > 0 else np.nan

    # IK-style plug-in structure for local-linear RD MSE balancing:
    # h ~ [ V / (n * B^2) ]^{1/5}
    # with triangular-kernel constants approximated in reduced form.
    r_k = 2.0 / 3.0
    boundary_bias_const = 0.5

    if not np.isfinite(m2_diff_abs) or m2_diff_abs <= 1e-10:
        fallback_reason = fallback_reason or "near_zero_curvature_difference"
    if not np.isfinite(sigma2_sum) or sigma2_sum <= 0:
        fallback_reason = fallback_reason or "nonpositive_variance"
    if not np.isfinite(fhat_cutoff) or fhat_cutoff <= 0:
        fallback_reason = fallback_reason or "nonpositive_cutoff_density"

    if fallback_reason:
        h_raw = np.nan
    else:
        numerator = r_k * sigma2_sum
        denominator = 4.0 * (boundary_bias_const**2) * (m2_diff_abs**2) * fhat_cutoff * n
        h_raw = float((numerator / denominator) ** (1.0 / 5.0)) if denominator > 0 else np.nan

    if not np.isfinite(h_raw) or h_raw <= 0:
        h_raw = float(reference_bw)
        fallback_reason = fallback_reason or "invalid_plugin_bandwidth_used_reference"

    return {
        "method_used": "ik_style_plugin",
        "selector_detail": "ik_style_local_linear_plugin",
        "bandwidth_raw": h_raw,
        "bandwidth_left_raw": np.nan,
        "bandwidth_right_raw": np.nan,
        "pilot_h_curvature": h_curv,
        "pilot_h_variance": h_var,
        "pilot_h_density": h_density,
        "m2_left": m2_left,
        "m2_right": m2_right,
        "m2_diff_abs": m2_diff_abs,
        "sigma2_left": sigma2_left,
        "sigma2_right": sigma2_right,
        "sigma2_sum": sigma2_sum,
        "fhat_cutoff": fhat_cutoff,
        "fallback_reason": fallback_reason,
    }


def select_data_driven_bandwidth(
    sample: pd.DataFrame,
    outcome_col: str,
    running_col: str,
    min_side_n: int,
    reference_bw: float,
) -> dict[str, float | int | str]:
    work = sample.copy()
    work[running_col] = pd.to_numeric(work[running_col], errors="coerce")
    work[outcome_col] = pd.to_numeric(work[outcome_col], errors="coerce")
    work = work[work[running_col].notna() & work[outcome_col].notna()].copy()

    if len(work) == 0:
        raise ValueError(f"No data available for bandwidth selection: {outcome_col}")

    h_min = _min_bandwidth_for_side_counts(
        sample=work, running_col=running_col, min_side_n=min_side_n
    )
    abs_x = np.abs(work[running_col].to_numpy())
    h_upper_q90 = float(np.quantile(abs_x, 0.90))
    h_upper = max(h_upper_q90, h_min)

    cct = _select_bandwidth_rdrobust(work, outcome_col=outcome_col, running_col=running_col)
    if cct is not None:
        selection = dict(cct)
        selection["fallback_reason"] = ""
    else:
        selection = _select_bandwidth_ik_style(
            sample=work,
            outcome_col=outcome_col,
            running_col=running_col,
            min_side_n=min_side_n,
            reference_bw=reference_bw,
        )

    h_raw = float(selection.get("bandwidth_raw", np.nan))
    if not np.isfinite(h_raw) or h_raw <= 0:
        h_raw = float(reference_bw)
        selection["fallback_reason"] = (
            str(selection.get("fallback_reason", "")) + ";invalid_raw_bandwidth"
        ).strip(";")

    h_selected = h_raw
    adjusted_to_min = False
    adjusted_to_max = False
    if h_selected < h_min:
        h_selected = h_min
        adjusted_to_min = True
    if h_selected > h_upper:
        h_selected = h_upper
        adjusted_to_max = True
        if h_selected < h_min:
            h_selected = h_min
            adjusted_to_min = True

    n_left_sel, n_right_sel = _count_sides_in_bandwidth(
        sample=work, running_col=running_col, bandwidth=h_selected
    )

    row = {
        "outcome": outcome_col,
        "selector_method": selection.get("method_used", "unknown"),
        "selector_detail": selection.get("selector_detail", ""),
        "bandwidth_raw": h_raw,
        "bandwidth_selected": float(h_selected),
        "bandwidth_min_required": float(h_min),
        "bandwidth_upper_cap_q90": float(h_upper_q90),
        "adjusted_to_min_side_requirement": int(adjusted_to_min),
        "adjusted_to_upper_cap": int(adjusted_to_max),
        "n_sample": int(len(work)),
        "n_left_selected_bw": int(n_left_sel),
        "n_right_selected_bw": int(n_right_sel),
        "pilot_h_curvature": selection.get("pilot_h_curvature", np.nan),
        "pilot_h_variance": selection.get("pilot_h_variance", np.nan),
        "pilot_h_density": selection.get("pilot_h_density", np.nan),
        "m2_left": selection.get("m2_left", np.nan),
        "m2_right": selection.get("m2_right", np.nan),
        "m2_diff_abs": selection.get("m2_diff_abs", np.nan),
        "sigma2_left": selection.get("sigma2_left", np.nan),
        "sigma2_right": selection.get("sigma2_right", np.nan),
        "sigma2_sum": selection.get("sigma2_sum", np.nan),
        "fhat_cutoff": selection.get("fhat_cutoff", np.nan),
        "bandwidth_left_raw": selection.get("bandwidth_left_raw", np.nan),
        "bandwidth_right_raw": selection.get("bandwidth_right_raw", np.nan),
        "fallback_reason": selection.get("fallback_reason", ""),
    }
    return row


def _safe_bw_label(bandwidth: float) -> str:
    return f"{bandwidth:.3f}".replace(".", "p")


def _build_window_with_plot_bins(
    sample: pd.DataFrame,
    running_col: str,
    bandwidth: float,
    bins_per_side: int,
) -> pd.DataFrame:
    window = sample[sample[running_col].between(-bandwidth, bandwidth)].copy()
    window["treated"] = (window[running_col] >= 0.0).astype(int)
    window["weights"] = 1.0 - (np.abs(window[running_col]) / bandwidth)
    window["plot_side"] = np.where(window[running_col] < 0, "left", "right")

    left_edges = np.linspace(-bandwidth, 0.0, bins_per_side + 1)
    right_edges = np.linspace(0.0, bandwidth, bins_per_side + 1)

    left_mask = window[running_col] < 0
    right_mask = ~left_mask

    window.loc[left_mask, "bin_in_side"] = pd.cut(
        window.loc[left_mask, running_col],
        bins=left_edges,
        include_lowest=True,
        labels=False,
    )
    window.loc[right_mask, "bin_in_side"] = pd.cut(
        window.loc[right_mask, running_col],
        bins=right_edges,
        include_lowest=True,
        labels=False,
    )
    window["bin_in_side"] = pd.to_numeric(window["bin_in_side"], errors="coerce").astype("Int64")

    # Signed bin index for single-column plotting/export:
    # left bins: -1, -2, ... ; right bins: 1, 2, ...
    window["plot_bin"] = np.where(
        window["plot_side"] == "left",
        -(window["bin_in_side"] + 1),
        window["bin_in_side"] + 1,
    )
    window["plot_bin"] = pd.to_numeric(window["plot_bin"], errors="coerce").astype("Int64")
    return window


def _export_estimation_windows(
    prepared: pd.DataFrame,
    running_col: str,
    bandwidth_grid: list[float],
    bins_per_side: int,
    main_outcomes: list[str],
    balance_covariates: list[str],
    windows_dir: Path,
) -> None:
    windows_dir.mkdir(parents=True, exist_ok=True)

    id_cols = [
        "candidate",
        "person_id",
        "election_ym",
        "prv_code",
        "p_code",
        "list_pos",
        running_col,
        "elected_dta",
        "next_election_ym",
    ]
    id_cols = [c for c in id_cols if c in prepared.columns]
    export_meta_cols = ["treated", "weights", "plot_side", "bin_in_side", "plot_bin"]

    def _build_export_frame(
        window: pd.DataFrame,
        outcome_col: str,
        analysis_type: str,
    ) -> pd.DataFrame:
        cols = id_cols + export_meta_cols
        cols = list(dict.fromkeys(cols))  # preserve order while forcing uniqueness
        out = window[cols].copy()
        out["outcome_value"] = pd.to_numeric(window[outcome_col], errors="coerce")
        out.insert(0, "outcome", outcome_col)
        out.insert(0, "analysis_type", analysis_type)
        return out

    for bw in bandwidth_grid:
        all_rows: list[pd.DataFrame] = []

        for outcome_col in main_outcomes:
            sample = _prepare_sample(
                prepared,
                running_col=running_col,
                outcome_col=outcome_col,
                require_next_election=True,
            )
            window = _build_window_with_plot_bins(
                sample=sample,
                running_col=running_col,
                bandwidth=bw,
                bins_per_side=bins_per_side,
            )
            all_rows.append(_build_export_frame(window, outcome_col, analysis_type="main"))

        for covariate in balance_covariates:
            sample = _prepare_sample(
                prepared,
                running_col=running_col,
                outcome_col=covariate,
                require_next_election=True,
            )
            window = _build_window_with_plot_bins(
                sample=sample,
                running_col=running_col,
                bandwidth=bw,
                bins_per_side=bins_per_side,
            )
            all_rows.append(_build_export_frame(window, covariate, analysis_type="balance"))

        bw_df = pd.concat(all_rows, ignore_index=True)
        bw_path = windows_dir / f"rdd_window_bw{_safe_bw_label(bw)}.csv"
        bw_df.to_csv(bw_path, index=False)


def run_treatment_validation(
    df: pd.DataFrame,
    running_col: str,
    bandwidth_grid: list[float],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = df.copy()
    work[running_col] = pd.to_numeric(work[running_col], errors="coerce")
    work["elected_dta"] = pd.to_numeric(work["elected_dta"], errors="coerce")
    work = work[work[running_col].notna() & work["elected_dta"].notna()].copy()
    work["treated"] = (work[running_col] >= 0.0).astype(int)
    work["elected_bin"] = (work["elected_dta"] > 0.5).astype(int)
    work["is_mismatch"] = work["treated"] != work["elected_bin"]

    summary_rows: list[dict[str, float | int]] = []
    mismatch_rows: list[pd.DataFrame] = []

    mismatch_cols = [
        "candidate",
        "election_ym",
        "prv_code",
        "p_code",
        "list_pos",
        running_col,
        "elected_dta",
    ]

    for bw in bandwidth_grid:
        window = work[work[running_col].between(-bw, bw)].copy()
        n_window = int(len(window))

        tp = int(((window["treated"] == 1) & (window["elected_bin"] == 1)).sum())
        tn = int(((window["treated"] == 0) & (window["elected_bin"] == 0)).sum())
        fp = int(((window["treated"] == 1) & (window["elected_bin"] == 0)).sum())
        fn = int(((window["treated"] == 0) & (window["elected_bin"] == 1)).sum())

        mismatches = fp + fn
        mismatch_rate = float(mismatches / n_window) if n_window else np.nan

        summary_rows.append(
            {
                "bandwidth": bw,
                "n_window": n_window,
                "tp_treated1_elected1": tp,
                "tn_treated0_elected0": tn,
                "fp_treated1_elected0": fp,
                "fn_treated0_elected1": fn,
                "mismatches": mismatches,
                "mismatch_rate": mismatch_rate,
            }
        )

        bw_mismatches = window[window["is_mismatch"]][mismatch_cols].copy()
        bw_mismatches.insert(0, "bandwidth", bw)
        mismatch_rows.append(bw_mismatches)

    summary_df = pd.DataFrame(summary_rows).sort_values("bandwidth")
    mismatches_df = (
        pd.concat(mismatch_rows, ignore_index=True)
        if mismatch_rows
        else pd.DataFrame(columns=["bandwidth", *mismatch_cols])
    )
    return summary_df, mismatches_df


def run_female_placebo_diagnostics(
    prepared: pd.DataFrame,
    running_col: str,
    bandwidth_grid: list[float],
    min_side_n: int,
) -> pd.DataFrame:
    base = prepared.copy()
    base[running_col] = pd.to_numeric(base[running_col], errors="coerce")
    base = base[base["next_election_ym"].notna() & base[running_col].notna()].copy()
    base["treated"] = (base[running_col] >= 0.0).astype(int)
    base["female_missing"] = pd.to_numeric(base["female_missing"], errors="coerce").fillna(1.0)

    missing_rd_sample = _prepare_sample(
        prepared,
        running_col=running_col,
        outcome_col="female_missing",
        require_next_election=True,
    )

    rows: list[dict[str, float | int]] = []
    for bw in bandwidth_grid:
        window = base[base[running_col].between(-bw, bw)].copy()
        treated = window[window["treated"] == 1]
        control = window[window["treated"] == 0]

        n_window = int(len(window))
        n_treated = int(len(treated))
        n_control = int(len(control))
        miss_treated = int(treated["female_missing"].sum())
        miss_control = int(control["female_missing"].sum())

        rd_est = estimate_local_linear_rd(
            missing_rd_sample,
            outcome_col="female_missing",
            running_col=running_col,
            bandwidth=bw,
            min_side_n=min_side_n,
            analysis_type="female_missing",
        )

        rows.append(
            {
                "bandwidth": bw,
                "n_window": n_window,
                "n_treated": n_treated,
                "n_control": n_control,
                "female_missing_count_treated": miss_treated,
                "female_missing_count_control": miss_control,
                "female_missing_rate_treated": float(miss_treated / n_treated) if n_treated else np.nan,
                "female_missing_rate_control": float(miss_control / n_control) if n_control else np.nan,
                "female_missing_rate_overall": float(window["female_missing"].mean()) if n_window else np.nan,
                "rd_tau_female_missing": rd_est.tau,
                "rd_se_female_missing": rd_est.se,
                "rd_ci95_low_female_missing": rd_est.ci95_low,
                "rd_ci95_high_female_missing": rd_est.ci95_high,
                "rd_p_value_female_missing": rd_est.p_value,
            }
        )

    return pd.DataFrame(rows).sort_values("bandwidth")


def extract_closest_female_placebo_observations(
    prepared: pd.DataFrame,
    running_col: str,
    n_each_side: int = 20,
) -> tuple[pd.DataFrame, float, float]:
    female_sample = _prepare_sample(
        prepared,
        running_col=running_col,
        outcome_col="female",
        require_next_election=True,
    ).copy()
    female_sample["abs_running_variable"] = np.abs(pd.to_numeric(female_sample[running_col], errors="coerce"))

    left = (
        female_sample[female_sample[running_col] < 0]
        .sort_values("abs_running_variable")
        .head(n_each_side)
        .copy()
    )
    right = (
        female_sample[female_sample[running_col] >= 0]
        .sort_values("abs_running_variable")
        .head(n_each_side)
        .copy()
    )

    left["side"] = "left"
    right["side"] = "right"
    left["rank_in_side"] = np.arange(1, len(left) + 1)
    right["rank_in_side"] = np.arange(1, len(right) + 1)

    cols = [
        "side",
        "rank_in_side",
        "candidate",
        "election_ym",
        "prv_code",
        "p_code",
        "list_pos",
        running_col,
        "abs_running_variable",
        "female",
        "elected_dta",
    ]
    out = pd.concat([left, right], ignore_index=True)[cols]

    min_left = float(left["abs_running_variable"].min()) if not left.empty else np.nan
    min_right = float(right["abs_running_variable"].min()) if not right.empty else np.nan
    return out, min_left, min_right


def compare_person_vs_string_estimates(
    prepared: pd.DataFrame,
    running_col: str,
    bandwidth_grid: list[float],
    min_side_n: int,
    se_types: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    outcome_specs = [
        ("runs", "string_same_prv", "runs_next_string_same_prv"),
        ("runs", "person_same_prv", "runs_next_same_prv"),
        ("runs", "string_any_prv", "runs_next_string_any_prv"),
        ("runs", "person_any_prv", "runs_next_any_prv"),
        ("wins", "string_same_prv", "wins_next_string_same_prv"),
        ("wins", "person_same_prv", "wins_next_same_prv"),
        ("wins", "string_any_prv", "wins_next_string_any_prv"),
        ("wins", "person_any_prv", "wins_next_any_prv"),
    ]

    rows: list[dict[str, float | int | str]] = []
    for family, definition, outcome_col in outcome_specs:
        for se_type in se_types:
            sample = _prepare_sample(
                prepared,
                running_col=running_col,
                outcome_col=outcome_col,
                require_next_election=True,
            )
            for bw in bandwidth_grid:
                est = estimate_local_linear_rd(
                    sample=sample,
                    outcome_col=outcome_col,
                    running_col=running_col,
                    bandwidth=bw,
                    min_side_n=min_side_n,
                    analysis_type="comparison",
                    se_type=se_type,
                )
                row = est.as_dict()
                row["outcome_family"] = family
                row["definition"] = definition
                rows.append(row)

    long_df = pd.DataFrame(rows).sort_values(
        ["se_type", "outcome_family", "definition", "bandwidth"]
    )
    wide = (
        long_df.pivot_table(
            index=["se_type", "outcome_family", "bandwidth"],
            columns="definition",
            values="tau",
            aggfunc="first",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    for col in ["person_same_prv", "string_same_prv", "person_any_prv", "string_any_prv"]:
        if col not in wide.columns:
            wide[col] = np.nan
    wide["tau_diff_person_minus_string_same_prv"] = (
        wide["person_same_prv"] - wide["string_same_prv"]
    )
    wide["tau_diff_person_minus_string_any_prv"] = wide["person_any_prv"] - wide["string_any_prv"]
    return long_df, wide.sort_values(["se_type", "outcome_family", "bandwidth"])


def estimate_fuzzy_rd_wald(
    sample: pd.DataFrame,
    outcome_col: str,
    running_col: str,
    bandwidth: float,
    min_side_n: int,
    se_type: str,
) -> dict[str, float | int | str]:
    # Reduced form: jump in E[Y|x] at cutoff.
    rf = estimate_local_linear_rd(
        sample=sample,
        outcome_col=outcome_col,
        running_col=running_col,
        bandwidth=bandwidth,
        min_side_n=min_side_n,
        analysis_type="fuzzy_reduced_form",
        se_type=se_type,
    )

    # First stage: jump in P(D=1|x), where D = elected_dta.
    first_stage = estimate_local_linear_rd(
        sample=sample,
        outcome_col="elected_dta",
        running_col=running_col,
        bandwidth=bandwidth,
        min_side_n=min_side_n,
        analysis_type="fuzzy_first_stage",
        se_type=se_type,
    )

    fs_tau = float(first_stage.tau)
    fs_se = float(first_stage.se)
    rf_tau = float(rf.tau)
    rf_se = float(rf.se)

    fuzzy_tau = np.nan
    fuzzy_se = np.nan
    fuzzy_ci95_low = np.nan
    fuzzy_ci95_high = np.nan
    fuzzy_p_value = np.nan

    # Weak instrument test: use first-stage F-statistic (= t^2) rather than
    # raw coefficient magnitude.  Stock & Yogo (2005) rule of thumb: F > 10.
    fs_f_stat = (fs_tau / fs_se) ** 2 if fs_se > 0 else np.nan
    weak_first_stage_flag = int(
        not np.isfinite(fs_f_stat) or fs_f_stat < 10.0
    )

    if np.isfinite(fs_tau) and abs(fs_tau) > 1e-10:
        fuzzy_tau = float(rf_tau / fs_tau)
        # Delta-method SE (conservative: omits negative covariance term,
        # so SE is overstated).  Acceptable when first stage is strong (~0.98).
        var_fuzzy = (rf_se**2) / (fs_tau**2) + ((rf_tau**2) * (fs_se**2)) / (fs_tau**4)
        if np.isfinite(var_fuzzy) and var_fuzzy >= 0:
            fuzzy_se = float(np.sqrt(var_fuzzy))
            if fuzzy_se > 0:
                z = fuzzy_tau / fuzzy_se
                fuzzy_p_value = float(2 * (1 - norm.cdf(abs(z))))
                fuzzy_ci95_low = float(fuzzy_tau - 1.96 * fuzzy_se)
                fuzzy_ci95_high = float(fuzzy_tau + 1.96 * fuzzy_se)

    return {
        "analysis_type": "fuzzy_wald",
        "outcome": outcome_col,
        "bandwidth": bandwidth,
        "se_type": se_type,
        "cluster_spec": se_type if se_type != "hc1" else "none",
        "n_window": rf.n_window,
        "n_left": rf.n_left,
        "n_right": rf.n_right,
        "n_clusters_left": rf.n_clusters_left,
        "n_clusters_right": rf.n_clusters_right,
        "reduced_form_tau": rf_tau,
        "reduced_form_se": rf_se,
        "reduced_form_p_value": rf.p_value,
        "first_stage_tau": fs_tau,
        "first_stage_se": fs_se,
        "first_stage_p_value": first_stage.p_value,
        "fuzzy_tau": fuzzy_tau,
        "fuzzy_se": fuzzy_se,
        "fuzzy_ci95_low": fuzzy_ci95_low,
        "fuzzy_ci95_high": fuzzy_ci95_high,
        "fuzzy_p_value": fuzzy_p_value,
        "first_stage_f_stat": float(fs_f_stat) if np.isfinite(fs_f_stat) else np.nan,
        "weak_first_stage_flag": weak_first_stage_flag,
    }


def run_placebo_cutoff_tests(
    sample: pd.DataFrame,
    outcome_col: str,
    running_col: str,
    bandwidth: float,
    min_side_n: int,
    se_types: list[str],
) -> list[dict[str, float | int | str]]:
    """Run RDD at fake cutoffs (median of each side) to check for spurious jumps."""
    x = pd.to_numeric(sample[running_col], errors="coerce")
    left_x = x[x < 0]
    right_x = x[x >= 0]

    placebo_cutoffs = {}
    if len(left_x) > 2 * min_side_n:
        placebo_cutoffs["left_median"] = float(left_x.median())
    if len(right_x) > 2 * min_side_n:
        placebo_cutoffs["right_median"] = float(right_x.median())

    rows: list[dict[str, float | int | str]] = []
    for label, cutoff in placebo_cutoffs.items():
        shifted = sample.copy()
        shifted["_shifted_rv"] = pd.to_numeric(shifted[running_col], errors="coerce") - cutoff

        # Restrict to the appropriate side to avoid contamination from the real cutoff.
        if label.startswith("left"):
            shifted = shifted[shifted[running_col] < 0].copy()
        else:
            shifted = shifted[shifted[running_col] >= 0].copy()

        for se_type in se_types:
            try:
                est = estimate_local_linear_rd(
                    sample=shifted,
                    outcome_col=outcome_col,
                    running_col="_shifted_rv",
                    bandwidth=bandwidth,
                    min_side_n=min_side_n,
                    analysis_type=f"placebo_cutoff_{label}",
                    se_type=se_type,
                )
                row = est.as_dict()
                row["placebo_cutoff"] = cutoff
                row["placebo_label"] = label
                rows.append(row)
            except ValueError:
                pass  # insufficient observations at this placebo cutoff

    return rows


def run_donut_hole_robustness(
    sample: pd.DataFrame,
    outcome_col: str,
    running_col: str,
    bandwidth: float,
    min_side_n: int,
    se_types: list[str],
    donut_sizes: list[float] | None = None,
) -> list[dict[str, float | int | str]]:
    """Run RDD excluding observations very close to the cutoff."""
    if donut_sizes is None:
        # Default: exclude innermost 0.1%, 0.25%, 0.5% of bandwidth range.
        donut_sizes = [0.001, 0.0025, 0.005]

    rows: list[dict[str, float | int | str]] = []
    for donut in donut_sizes:
        for se_type in se_types:
            try:
                est = estimate_local_linear_rd(
                    sample=sample,
                    outcome_col=outcome_col,
                    running_col=running_col,
                    bandwidth=bandwidth,
                    min_side_n=min_side_n,
                    analysis_type="donut_hole",
                    se_type=se_type,
                    donut=donut,
                )
                row = est.as_dict()
                row["donut_radius"] = donut
                rows.append(row)
            except ValueError:
                pass  # insufficient observations after donut exclusion

    return rows


def run_polynomial_order_robustness(
    sample: pd.DataFrame,
    outcome_col: str,
    running_col: str,
    bandwidth: float,
    min_side_n: int,
    se_type: str = "hc1",
) -> dict[str, float | int | str] | None:
    """Run local-quadratic RDD as robustness check against local-linear."""
    window = sample[sample[running_col].between(-bandwidth, bandwidth)].copy()
    left = window[window[running_col] < 0]
    right = window[window[running_col] >= 0]

    if len(left) < min_side_n or len(right) < min_side_n:
        return None

    x = pd.to_numeric(window[running_col], errors="coerce").astype(float).values
    y = pd.to_numeric(window[outcome_col], errors="coerce").astype(float).values
    t = (x >= 0).astype(float)
    w = 1.0 - (np.abs(x) / bandwidth)

    # Local-quadratic: Y = a + b*X + c*X^2 + tau*T + d*T*X + e*T*X^2 + eps
    design = pd.DataFrame(
        {
            "const": 1.0,
            "x": x,
            "x2": x**2,
            "T": t,
            "Tx": t * x,
            "Tx2": t * x**2,
        },
        index=window.index,
    )
    model = sm.WLS(y, design, weights=w)

    if se_type == "hc1":
        fit = model.fit(cov_type="HC1")
    else:
        cluster_groups = _build_cluster_groups(window, se_type=se_type)
        if cluster_groups.nunique() < 2:
            fit = model.fit(cov_type="HC1")
        else:
            fit = model.fit(cov_type="cluster", cov_kwds={"groups": cluster_groups})

    tau = float(fit.params["T"])
    se = float(np.sqrt(fit.cov_params().loc["T", "T"]))

    p_value = np.nan
    ci95_low = np.nan
    ci95_high = np.nan
    if se > 0:
        z = tau / se
        p_value = float(2 * (1 - norm.cdf(abs(z))))
        ci95_low = float(tau - 1.96 * se)
        ci95_high = float(tau + 1.96 * se)

    return {
        "analysis_type": "local_quadratic",
        "outcome": outcome_col,
        "bandwidth": bandwidth,
        "se_type": se_type,
        "n_window": int(len(window)),
        "n_left": int(len(left)),
        "n_right": int(len(right)),
        "mean_left": float(left[outcome_col].astype(float).mean()),
        "mean_right": float(right[outcome_col].astype(float).mean()),
        "tau": tau,
        "se": se,
        "ci95_low": ci95_low,
        "ci95_high": ci95_high,
        "p_value": p_value,
    }


def estimate_rdrobust(
    sample: pd.DataFrame,
    outcome_col: str,
    running_col: str,
) -> dict[str, float | str] | None:
    """Run rdrobust for bias-corrected RDD inference (Cattaneo et al. 2014/2020).

    Returns conventional and bias-corrected estimates with robust CIs,
    or None if rdrobust is not installed.
    """
    try:
        from rdrobust import rdrobust
    except ImportError:
        return None

    x = pd.to_numeric(sample[running_col], errors="coerce").to_numpy(dtype=float)
    y = pd.to_numeric(sample[outcome_col], errors="coerce").to_numpy(dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]

    try:
        result = rdrobust(y=y, x=x, c=0.0, p=1, q=2, kernel="tri")
    except Exception:
        return None

    # Extract estimates from rdrobust output.
    coef = getattr(result, "coef", None)
    se = getattr(result, "se", None)
    ci = getattr(result, "ci", None)
    pv = getattr(result, "pv", None)
    bws = getattr(result, "bws", None)

    row: dict[str, float | str] = {"outcome": outcome_col}

    # rdrobust returns DataFrames with rows: Conventional, Bias-Corrected, Robust.
    for label, idx in [("conventional", 0), ("bias_corrected", 1), ("robust", 2)]:
        try:
            if hasattr(coef, "iloc"):
                row[f"tau_{label}"] = float(coef.iloc[idx].iloc[0])
            else:
                row[f"tau_{label}"] = float(np.asarray(coef).ravel()[idx])
        except (IndexError, TypeError):
            row[f"tau_{label}"] = np.nan

        try:
            if hasattr(se, "iloc"):
                row[f"se_{label}"] = float(se.iloc[idx].iloc[0])
            else:
                row[f"se_{label}"] = float(np.asarray(se).ravel()[idx])
        except (IndexError, TypeError):
            row[f"se_{label}"] = np.nan

        try:
            if hasattr(pv, "iloc"):
                row[f"pvalue_{label}"] = float(pv.iloc[idx].iloc[0])
            else:
                row[f"pvalue_{label}"] = float(np.asarray(pv).ravel()[idx])
        except (IndexError, TypeError):
            row[f"pvalue_{label}"] = np.nan

        try:
            if hasattr(ci, "iloc"):
                row[f"ci_low_{label}"] = float(ci.iloc[idx].iloc[0])
                row[f"ci_high_{label}"] = float(ci.iloc[idx].iloc[1])
            else:
                ci_arr = np.asarray(ci)
                row[f"ci_low_{label}"] = float(ci_arr[idx, 0])
                row[f"ci_high_{label}"] = float(ci_arr[idx, 1])
        except (IndexError, TypeError):
            row[f"ci_low_{label}"] = np.nan
            row[f"ci_high_{label}"] = np.nan

    # Bandwidth info.
    try:
        if hasattr(bws, "iloc"):
            row["bw_left"] = float(bws.iloc[0].iloc[0])
            row["bw_right"] = float(bws.iloc[0].iloc[1])
        else:
            bw_arr = np.asarray(bws).ravel()
            row["bw_left"] = float(bw_arr[0])
            row["bw_right"] = float(bw_arr[1]) if len(bw_arr) > 1 else float(bw_arr[0])
    except (IndexError, TypeError):
        row["bw_left"] = np.nan
        row["bw_right"] = np.nan

    row["n_total"] = int(len(x))
    return row


def generate_descriptive_statistics(
    prepared: pd.DataFrame,
    running_col: str,
    bandwidth: float,
) -> pd.DataFrame:
    """Generate descriptive statistics table for the analysis sample."""
    window = prepared[prepared[running_col].between(-bandwidth, bandwidth)].copy()
    window["treated"] = (window[running_col] >= 0).astype(int)

    stats_vars = [
        running_col,
        "elected_dta",
        "runs_next",
        "wins_next",
        "female",
        "list_pos",
        "log_p_votes",
        "p_seats",
        "blank_vote_share",
    ]
    stats_vars = [v for v in stats_vars if v in window.columns]

    rows: list[dict[str, float | int | str]] = []
    for var in stats_vars:
        vals = pd.to_numeric(window[var], errors="coerce")
        vals_left = pd.to_numeric(window.loc[window["treated"] == 0, var], errors="coerce")
        vals_right = pd.to_numeric(window.loc[window["treated"] == 1, var], errors="coerce")

        rows.append(
            {
                "variable": var,
                "n_total": int(vals.notna().sum()),
                "mean_total": float(vals.mean()) if vals.notna().any() else np.nan,
                "sd_total": float(vals.std()) if vals.notna().sum() > 1 else np.nan,
                "min_total": float(vals.min()) if vals.notna().any() else np.nan,
                "max_total": float(vals.max()) if vals.notna().any() else np.nan,
                "n_left": int(vals_left.notna().sum()),
                "mean_left": float(vals_left.mean()) if vals_left.notna().any() else np.nan,
                "sd_left": float(vals_left.std()) if vals_left.notna().sum() > 1 else np.nan,
                "n_right": int(vals_right.notna().sum()),
                "mean_right": float(vals_right.mean()) if vals_right.notna().any() else np.nan,
                "sd_right": float(vals_right.std()) if vals_right.notna().sum() > 1 else np.nan,
            }
        )

    return pd.DataFrame(rows)


def main() -> None:
    args = parse_args()

    data_path = Path(args.data)
    output_path = Path(args.output_csv)
    balance_output_path = Path(args.balance_output_csv)
    balance_pretreatment_output_path = Path(args.balance_pretreatment_output_csv)
    sample_output_path = Path(args.sample_output_csv)
    windows_dir = Path(args.windows_dir)
    validation_output_path = Path(args.validation_output_csv)
    validation_mismatches_path = Path(args.validation_mismatches_csv)
    female_diag_path = Path(args.female_diagnostics_csv)
    female_closest_path = Path(args.female_closest_csv)
    person_id_map_path = Path(args.person_id_map_csv)
    person_id_output_path = Path(args.person_id_output_csv)
    person_id_validation_path = Path(args.person_id_validation_output_csv)
    comparison_output_path = Path(args.comparison_output_csv)
    comparison_long_output_path = Path(args.comparison_long_output_csv)
    fuzzy_output_path = Path(args.fuzzy_output_csv)
    fuzzy_selected_bw_output_path = Path(args.fuzzy_selected_bw_output_csv)
    sharp_fuzzy_comparison_output_path = Path(args.sharp_fuzzy_comparison_output_csv)
    density_bins_output_path = Path(args.density_bins_output_csv)
    density_summary_output_path = Path(args.density_summary_output_csv)
    bw_selection_output_path = Path(args.bw_selection_output_csv)
    main_selected_bw_output_path = Path(args.main_selected_bw_output_csv)
    fig_dir = Path(args.fig_dir)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    balance_output_path.parent.mkdir(parents=True, exist_ok=True)
    balance_pretreatment_output_path.parent.mkdir(parents=True, exist_ok=True)
    sample_output_path.parent.mkdir(parents=True, exist_ok=True)
    windows_dir.mkdir(parents=True, exist_ok=True)
    validation_output_path.parent.mkdir(parents=True, exist_ok=True)
    validation_mismatches_path.parent.mkdir(parents=True, exist_ok=True)
    female_diag_path.parent.mkdir(parents=True, exist_ok=True)
    female_closest_path.parent.mkdir(parents=True, exist_ok=True)
    person_id_output_path.parent.mkdir(parents=True, exist_ok=True)
    person_id_validation_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_output_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_long_output_path.parent.mkdir(parents=True, exist_ok=True)
    fuzzy_output_path.parent.mkdir(parents=True, exist_ok=True)
    fuzzy_selected_bw_output_path.parent.mkdir(parents=True, exist_ok=True)
    sharp_fuzzy_comparison_output_path.parent.mkdir(parents=True, exist_ok=True)
    density_bins_output_path.parent.mkdir(parents=True, exist_ok=True)
    density_summary_output_path.parent.mkdir(parents=True, exist_ok=True)
    bw_selection_output_path.parent.mkdir(parents=True, exist_ok=True)
    main_selected_bw_output_path.parent.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)

    bandwidth_grid = _parse_bandwidth_grid(args.bandwidth_grid)
    requested_se_types = _parse_se_types(args.se_types)
    plot_bandwidth = args.bandwidth

    df = pd.read_csv(data_path)
    required = ["candidate", "prv_code", "election_ym", "elected_dta", args.running_col]
    _assert_columns(df, required)
    main_se_types, skipped_se_types = _resolve_available_se_types(df, requested_se_types)

    legacy_person_id_opts_used = (
        args.person_id_method != DEFAULT_PERSON_ID_METHOD
        or bool(args.panel_id_csv.strip())
        or bool(args.panel_id_col.strip())
    )

    with_person_id, person_id_validation_df = merge_person_id_map(
        df=df,
        person_id_map_path=person_id_map_path,
        person_id_col=args.person_id_map_col.strip(),
    )
    with_person_id["person_id_source"] = "person_id_map"
    prepared = build_next_election_outcomes(with_person_id)
    prepared = add_balance_covariates(prepared)
    prepared = add_lagged_pretreatment_covariates(prepared)

    person_id_export_cols = [
        "candidate",
        "person_id",
        "person_id_source",
        "election_ym",
        "prv_code",
        "p_code",
        "list_pos",
    ]
    person_id_export_cols = [c for c in person_id_export_cols if c in prepared.columns]
    prepared[person_id_export_cols].to_csv(person_id_output_path, index=False)
    person_id_validation_df.to_csv(person_id_validation_path, index=False)

    validation_summary_df, validation_mismatches_df = run_treatment_validation(
        prepared,
        running_col=args.running_col,
        bandwidth_grid=bandwidth_grid,
    )
    validation_summary_df.to_csv(validation_output_path, index=False)
    validation_mismatches_df.to_csv(validation_mismatches_path, index=False)

    female_diag_df = run_female_placebo_diagnostics(
        prepared=prepared,
        running_col=args.running_col,
        bandwidth_grid=bandwidth_grid,
        min_side_n=args.min_side_n,
    )
    female_diag_df.to_csv(female_diag_path, index=False)

    female_closest_df, min_abs_left, min_abs_right = extract_closest_female_placebo_observations(
        prepared=prepared,
        running_col=args.running_col,
        n_each_side=20,
    )
    female_closest_df.to_csv(female_closest_path, index=False)

    density_bins_df, density_summary_df = run_running_variable_density_diagnostics(
        df=prepared,
        running_col=args.running_col,
        bandwidth_grid=bandwidth_grid,
        bins_per_side=args.bins_per_side,
        min_bins_for_test=4,
    )
    density_bins_df.to_csv(density_bins_output_path, index=False)
    density_summary_df.to_csv(density_summary_output_path, index=False)
    density_plot_paths = plot_running_variable_density_diagnostics(
        density_bins_df=density_bins_df,
        density_summary_df=density_summary_df,
        fig_dir=fig_dir,
    )

    main_outcomes = ["wins_next", "runs_next"] if args.outcome == "both" else [args.outcome]
    main_estimates: list[dict[str, float | int | str]] = []
    main_samples: dict[str, pd.DataFrame] = {}
    for outcome_col in main_outcomes:
        main_sample = _prepare_sample(
            prepared, running_col=args.running_col, outcome_col=outcome_col, require_next_election=True
        )
        main_samples[outcome_col] = main_sample
        for bw in bandwidth_grid:
            for se_type in main_se_types:
                est = estimate_local_linear_rd(
                    main_sample,
                    outcome_col=outcome_col,
                    running_col=args.running_col,
                    bandwidth=bw,
                    min_side_n=args.min_side_n,
                    analysis_type="main",
                    se_type=se_type,
                )
                main_estimates.append(est.as_dict())

        plot_path = fig_dir / f"rdd_plot_{outcome_col}_bw{_safe_bw_label(plot_bandwidth)}.png"
        plot_rdd_binned(
            main_sample,
            outcome_col=outcome_col,
            running_col=args.running_col,
            bandwidth=plot_bandwidth,
            bins_per_side=args.bins_per_side,
            output_path=plot_path,
        )

    main_estimates_df = pd.DataFrame(main_estimates).sort_values(
        ["outcome", "se_type", "bandwidth"]
    )
    main_estimates_df.to_csv(output_path, index=False)

    fuzzy_rows: list[dict[str, float | int | str]] = []
    for outcome_col, main_sample in main_samples.items():
        for bw in bandwidth_grid:
            for se_type in main_se_types:
                fuzzy_rows.append(
                    estimate_fuzzy_rd_wald(
                        sample=main_sample,
                        outcome_col=outcome_col,
                        running_col=args.running_col,
                        bandwidth=bw,
                        min_side_n=args.min_side_n,
                        se_type=se_type,
                    )
                )
    fuzzy_df = pd.DataFrame(fuzzy_rows).sort_values(["outcome", "se_type", "bandwidth"])
    fuzzy_df.to_csv(fuzzy_output_path, index=False)

    sharp_comp = main_estimates_df.rename(
        columns={
            "tau": "sharp_tau",
            "se": "sharp_se",
            "p_value": "sharp_p_value",
            "ci95_low": "sharp_ci95_low",
            "ci95_high": "sharp_ci95_high",
            "analysis_type": "sharp_analysis_type",
        }
    )
    sharp_fuzzy_comparison_df = sharp_comp.merge(
        fuzzy_df[
            [
                "outcome",
                "bandwidth",
                "se_type",
                "first_stage_tau",
                "first_stage_se",
                "first_stage_p_value",
                "reduced_form_tau",
                "reduced_form_se",
                "reduced_form_p_value",
                "fuzzy_tau",
                "fuzzy_se",
                "fuzzy_ci95_low",
                "fuzzy_ci95_high",
                "fuzzy_p_value",
                "weak_first_stage_flag",
            ]
        ],
        on=["outcome", "bandwidth", "se_type"],
        how="left",
    )
    sharp_fuzzy_comparison_df["sharp_minus_fuzzy"] = (
        sharp_fuzzy_comparison_df["sharp_tau"] - sharp_fuzzy_comparison_df["fuzzy_tau"]
    )
    sharp_fuzzy_comparison_df.to_csv(sharp_fuzzy_comparison_output_path, index=False)

    bw_selection_rows: list[dict[str, float | int | str]] = []
    selected_bw_estimates: list[dict[str, float | int | str]] = []
    selected_bw_fuzzy_estimates: list[dict[str, float | int | str]] = []
    for outcome_col, main_sample in main_samples.items():
        bw_row = select_data_driven_bandwidth(
            sample=main_sample,
            outcome_col=outcome_col,
            running_col=args.running_col,
            min_side_n=args.min_side_n,
            reference_bw=float(plot_bandwidth),
        )
        bw_selection_rows.append(bw_row)

        selected_bw = float(bw_row["bandwidth_selected"])
        for se_type in main_se_types:
            est_sel = estimate_local_linear_rd(
                sample=main_sample,
                outcome_col=outcome_col,
                running_col=args.running_col,
                bandwidth=selected_bw,
                min_side_n=args.min_side_n,
                analysis_type="main_selected_bw",
                se_type=se_type,
            )
            est_sel_row = est_sel.as_dict()
            est_sel_row["selector_method"] = bw_row.get("selector_method", "")
            est_sel_row["selector_detail"] = bw_row.get("selector_detail", "")
            selected_bw_estimates.append(est_sel_row)

            fuzzy_sel_row = estimate_fuzzy_rd_wald(
                sample=main_sample,
                outcome_col=outcome_col,
                running_col=args.running_col,
                bandwidth=selected_bw,
                min_side_n=args.min_side_n,
                se_type=se_type,
            )
            fuzzy_sel_row["selector_method"] = bw_row.get("selector_method", "")
            fuzzy_sel_row["selector_detail"] = bw_row.get("selector_detail", "")
            selected_bw_fuzzy_estimates.append(fuzzy_sel_row)

    bw_selection_df = pd.DataFrame(bw_selection_rows).sort_values(["outcome"])
    selected_bw_estimates_df = pd.DataFrame(selected_bw_estimates).sort_values(
        ["outcome", "se_type"]
    )
    selected_bw_fuzzy_df = pd.DataFrame(selected_bw_fuzzy_estimates).sort_values(
        ["outcome", "se_type"]
    )
    bw_selection_df.to_csv(bw_selection_output_path, index=False)
    selected_bw_estimates_df.to_csv(main_selected_bw_output_path, index=False)
    selected_bw_fuzzy_df.to_csv(fuzzy_selected_bw_output_path, index=False)

    comparison_long_df, comparison_df = compare_person_vs_string_estimates(
        prepared=prepared,
        running_col=args.running_col,
        bandwidth_grid=bandwidth_grid,
        min_side_n=args.min_side_n,
        se_types=main_se_types,
    )
    comparison_long_df.to_csv(comparison_long_output_path, index=False)
    comparison_df.to_csv(comparison_output_path, index=False)

    sensitivity_plot_path = fig_dir / "rdd_bandwidth_sensitivity_main.png"
    plot_bandwidth_sensitivity(
        main_estimates_df,
        output_path=sensitivity_plot_path,
        title="Bandwidth Sensitivity (Main Outcomes)",
    )

    # Robustness: placebo cutoff tests, donut-hole, local-quadratic.
    robustness_dir = output_path.parent
    placebo_rows: list[dict[str, float | int | str]] = []
    donut_rows: list[dict[str, float | int | str]] = []
    quadratic_rows: list[dict[str, float | int | str]] = []

    for outcome_col, main_sample in main_samples.items():
        for bw in bandwidth_grid:
            placebo_rows.extend(
                run_placebo_cutoff_tests(
                    sample=main_sample,
                    outcome_col=outcome_col,
                    running_col=args.running_col,
                    bandwidth=bw,
                    min_side_n=args.min_side_n,
                    se_types=main_se_types,
                )
            )
            donut_rows.extend(
                run_donut_hole_robustness(
                    sample=main_sample,
                    outcome_col=outcome_col,
                    running_col=args.running_col,
                    bandwidth=bw,
                    min_side_n=args.min_side_n,
                    se_types=main_se_types,
                )
            )
            for se_type in main_se_types:
                quad_result = run_polynomial_order_robustness(
                    sample=main_sample,
                    outcome_col=outcome_col,
                    running_col=args.running_col,
                    bandwidth=bw,
                    min_side_n=args.min_side_n,
                    se_type=se_type,
                )
                if quad_result is not None:
                    quadratic_rows.append(quad_result)

    if placebo_rows:
        placebo_df = pd.DataFrame(placebo_rows).sort_values(
            ["outcome", "se_type", "bandwidth", "placebo_label"]
        )
        placebo_df.to_csv(robustness_dir / "rdd_placebo_cutoff_tests.csv", index=False)
        print(f"\nPlacebo cutoff tests: {robustness_dir / 'rdd_placebo_cutoff_tests.csv'}")

    if donut_rows:
        donut_df = pd.DataFrame(donut_rows).sort_values(
            ["outcome", "se_type", "bandwidth", "donut_radius"]
        )
        donut_df.to_csv(robustness_dir / "rdd_donut_hole_robustness.csv", index=False)
        print(f"Donut-hole robustness: {robustness_dir / 'rdd_donut_hole_robustness.csv'}")

    if quadratic_rows:
        quadratic_df = pd.DataFrame(quadratic_rows).sort_values(
            ["outcome", "se_type", "bandwidth"]
        )
        quadratic_df.to_csv(robustness_dir / "rdd_local_quadratic_robustness.csv", index=False)
        print(f"Local-quadratic robustness: {robustness_dir / 'rdd_local_quadratic_robustness.csv'}")

    # Descriptive statistics.
    desc_stats_df = generate_descriptive_statistics(
        prepared=prepared,
        running_col=args.running_col,
        bandwidth=plot_bandwidth,
    )
    desc_stats_df.to_csv(robustness_dir / "rdd_descriptive_statistics.csv", index=False)
    print(f"Descriptive statistics: {robustness_dir / 'rdd_descriptive_statistics.csv'}")

    # Bias-corrected inference via rdrobust (if installed).
    rdrobust_rows: list[dict[str, float | str]] = []
    for outcome_col, main_sample in main_samples.items():
        rdrobust_result = estimate_rdrobust(
            sample=main_sample,
            outcome_col=outcome_col,
            running_col=args.running_col,
        )
        if rdrobust_result is not None:
            rdrobust_rows.append(rdrobust_result)

    if rdrobust_rows:
        rdrobust_df = pd.DataFrame(rdrobust_rows)
        rdrobust_df.to_csv(robustness_dir / "rdd_rdrobust_estimates.csv", index=False)
        print(f"rdrobust bias-corrected estimates: {robustness_dir / 'rdd_rdrobust_estimates.csv'}")
    else:
        print("rdrobust not installed; skipping bias-corrected inference.")

    # Balance/placebo checks.
    requested_covariates = [c.strip() for c in args.balance_covariates.split(",") if c.strip()]
    _assert_columns(prepared, requested_covariates)

    balance_estimates: list[dict[str, float | int | str]] = []
    for covariate in requested_covariates:
        balance_sample = _prepare_sample(
            prepared, running_col=args.running_col, outcome_col=covariate, require_next_election=True
        )
        for bw in bandwidth_grid:
            est = estimate_local_linear_rd(
                balance_sample,
                outcome_col=covariate,
                running_col=args.running_col,
                bandwidth=bw,
                min_side_n=args.min_side_n,
                analysis_type="balance",
            )
            balance_estimates.append(est.as_dict())

    balance_estimates_df = (
        pd.DataFrame(balance_estimates).sort_values(["outcome", "bandwidth"])
    )
    balance_estimates_df.to_csv(balance_output_path, index=False)

    _export_estimation_windows(
        prepared=prepared,
        running_col=args.running_col,
        bandwidth_grid=bandwidth_grid,
        bins_per_side=args.bins_per_side,
        main_outcomes=main_outcomes,
        balance_covariates=requested_covariates,
        windows_dir=windows_dir,
    )

    balance_sensitivity_plot = fig_dir / "rdd_bandwidth_sensitivity_balance.png"
    plot_bandwidth_sensitivity(
        balance_estimates_df,
        output_path=balance_sensitivity_plot,
        title="Bandwidth Sensitivity (Balance/Placebo Covariates)",
    )

    # Dedicated pre-treatment-only balance/placebo checks.
    requested_pretreatment_covariates = [
        c.strip() for c in args.balance_pretreatment_covariates.split(",") if c.strip()
    ]
    available_pretreatment_covariates = [
        c for c in requested_pretreatment_covariates if c in prepared.columns
    ]
    _assert_columns(prepared, available_pretreatment_covariates)

    pretreatment_estimates: list[dict[str, float | int | str]] = []
    for covariate in available_pretreatment_covariates:
        pretreatment_sample = _prepare_sample(
            prepared,
            running_col=args.running_col,
            outcome_col=covariate,
            require_next_election=False,
        )
        for bw in bandwidth_grid:
            est = estimate_local_linear_rd(
                pretreatment_sample,
                outcome_col=covariate,
                running_col=args.running_col,
                bandwidth=bw,
                min_side_n=args.min_side_n,
                analysis_type="balance_pretreatment",
            )
            pretreatment_estimates.append(est.as_dict())

    pretreatment_estimates_df = (
        pd.DataFrame(pretreatment_estimates).sort_values(["outcome", "bandwidth"])
    )
    pretreatment_estimates_df.to_csv(balance_pretreatment_output_path, index=False)

    sample_cols = [
        "candidate",
        "person_id",
        "person_id_source",
        "prv_code",
        "election_ym",
        "next_election_ym",
        "p_code",
        "list_pos",
        "elected_dta",
        args.running_col,
        "runs_next",
        "wins_next",
        "runs_next_same_prv",
        "wins_next_same_prv",
        "runs_next_any_prv",
        "wins_next_any_prv",
        "runs_next_string_same_prv",
        "wins_next_string_same_prv",
        "runs_next_string_any_prv",
        "wins_next_string_any_prv",
        "female",
        "log_p_votes",
        "p_seats",
        "blank_vote_share",
    ]
    sample_cols = [col for col in sample_cols if col in prepared.columns]
    prepared[sample_cols].to_csv(sample_output_path, index=False)

    print("RDD pipeline completed.")
    print(f"Data: {data_path}")
    print(f"Main SE types requested: {requested_se_types}")
    print(f"Main SE types used: {main_se_types}")
    if skipped_se_types:
        print(f"Main SE types skipped: {skipped_se_types}")
    if legacy_person_id_opts_used:
        print(
            "Deprecated person-ID options detected "
            "(--person-id-method/--panel-id-csv/--panel-id-col). "
            "They are ignored here; run src/data/build_person_id.py first."
        )
    print(f"Person-ID map input: {person_id_map_path}")
    print(f"Main estimates: {output_path}")
    print(f"Person-ID assignment: {person_id_output_path}")
    print(f"Person-ID validation report: {person_id_validation_path}")
    print(f"Person-vs-string comparison (wide): {comparison_output_path}")
    print(f"Person-vs-string comparison (long): {comparison_long_output_path}")
    print(f"Fuzzy RD estimates: {fuzzy_output_path}")
    print(f"Fuzzy RD estimates at selected bandwidths: {fuzzy_selected_bw_output_path}")
    print(f"Sharp vs fuzzy comparison: {sharp_fuzzy_comparison_output_path}")
    print(f"Data-driven bandwidth selections: {bw_selection_output_path}")
    print(f"Main estimates at selected bandwidths: {main_selected_bw_output_path}")
    print(f"Running-variable density bins: {density_bins_output_path}")
    print(f"Running-variable density summary: {density_summary_output_path}")
    print(f"Balance/placebo estimates: {balance_output_path}")
    print(f"Pre-treatment placebo estimates: {balance_pretreatment_output_path}")
    print(f"Treatment validation: {validation_output_path}")
    print(f"Treatment mismatches: {validation_mismatches_path}")
    print(f"Female placebo diagnostics: {female_diag_path}")
    print(f"Female placebo closest rows: {female_closest_path}")
    print(f"Outcomes-enriched sample: {sample_output_path}")
    print(f"Per-bandwidth windows: {windows_dir}")
    print(f"Figures: {fig_dir}")
    print("\nMain estimates (bandwidth grid):")
    print(main_estimates_df.to_string(index=False))
    print("\nData-driven bandwidth selection (main outcomes):")
    print(bw_selection_df.to_string(index=False))
    print("\nMain estimates at selected bandwidths:")
    print(selected_bw_estimates_df.to_string(index=False))
    print("\nFuzzy RD estimates (bandwidth grid):")
    print(fuzzy_df.to_string(index=False))
    print("\nFuzzy RD estimates at selected bandwidths:")
    print(selected_bw_fuzzy_df.to_string(index=False))
    print("\nSharp vs fuzzy side-by-side:")
    print(sharp_fuzzy_comparison_df.to_string(index=False))
    print("\nPerson-ID validation report:")
    print(person_id_validation_df.to_string(index=False))
    print("\nPerson-ID vs string-based comparison (tau by bandwidth):")
    print(comparison_df.to_string(index=False))
    print("\nRunning-variable density diagnostics (bandwidth grid):")
    print(density_summary_df.to_string(index=False))
    print("\nBalance/placebo checks (bandwidth grid):")
    print(balance_estimates_df.to_string(index=False))
    print("\nPre-treatment-only placebo checks (bandwidth grid):")
    print(pretreatment_estimates_df.to_string(index=False))
    print("\nTreatment vs elected_dta validation (bandwidth grid):")
    print(validation_summary_df.to_string(index=False))
    print("\nFemale placebo diagnostics (bandwidth grid):")
    print(female_diag_df.to_string(index=False))
    print("\nFemale placebo closest-to-cutoff summary:")
    print(f"min |running_variable| (left):  {min_abs_left}")
    print(f"min |running_variable| (right): {min_abs_right}")
    print("\nRunning-variable density plots:")
    for path in density_plot_paths:
        print(path)


if __name__ == "__main__":
    main()
