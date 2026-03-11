#!/usr/bin/env python3
"""Build stable person IDs as a separate, reproducible pipeline step.

Outputs:
- person_id_map.csv (row-level map ready for downstream merges)
- validation sample with matched/non-matched pairs for manual QA
- summary CSV with method diagnostics
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_DATA = "data/processed/spain_master_dataset.csv"
DEFAULT_METHOD = "exact"
DEFAULT_LT_DISTANCE_THRESHOLD = 0.10
DEFAULT_LT_MAX_BLOCK_SIZE = 120
DEFAULT_SEED = 42
DEFAULT_OUTPUT_MAP = "data/processed/person_id_map.csv"
DEFAULT_OUTPUT_VALIDATION_SAMPLE = "data/processed/person_id_validation_sample.csv"
DEFAULT_OUTPUT_SUMMARY = "data/processed/person_id_build_summary.csv"

ROW_KEYS = ["election_ym", "prv_code", "p_code", "list_pos"]


@dataclass
class BuildSummary:
    method_requested: str
    method_used: str
    data_rows: int
    unique_candidates: int
    unique_person_id: int
    multi_name_person_ids: int
    rows_in_multi_name_person_ids: int
    merge_mode: str
    unmatched_after_merge: int
    lt_distance_threshold: float
    lt_max_block_size: int
    validation_target_matches: int
    validation_target_nonmatches: int
    validation_actual_matches: int
    validation_actual_nonmatches: int

    def to_dict(self) -> dict[str, float | int | str]:
        return {
            "method_requested": self.method_requested,
            "method_used": self.method_used,
            "data_rows": self.data_rows,
            "unique_candidates": self.unique_candidates,
            "unique_person_id": self.unique_person_id,
            "multi_name_person_ids": self.multi_name_person_ids,
            "rows_in_multi_name_person_ids": self.rows_in_multi_name_person_ids,
            "merge_mode": self.merge_mode,
            "unmatched_after_merge": self.unmatched_after_merge,
            "lt_distance_threshold": self.lt_distance_threshold,
            "lt_max_block_size": self.lt_max_block_size,
            "validation_target_matches": self.validation_target_matches,
            "validation_target_nonmatches": self.validation_target_nonmatches,
            "validation_actual_matches": self.validation_actual_matches,
            "validation_actual_nonmatches": self.validation_actual_nonmatches,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build person IDs for candidate linkage.")
    parser.add_argument("--data", default=DEFAULT_DATA, help=f"Input dataset (default: {DEFAULT_DATA})")
    parser.add_argument(
        "--method",
        choices=["exact", "provided", "linktransformer"],
        default=DEFAULT_METHOD,
        help=f"Person-ID method (default: {DEFAULT_METHOD})",
    )
    parser.add_argument(
        "--provided-panel-id",
        default="",
        help="Optional provided panel-ID table (.csv/.xlsx). Required for --method provided.",
    )
    parser.add_argument(
        "--provided-panel-id-col",
        default="",
        help="Optional ID column in provided panel-ID table. Auto-detected if omitted.",
    )
    parser.add_argument(
        "--candidate-col",
        default="candidate",
        help="Candidate name column in input dataset (default: candidate).",
    )
    parser.add_argument(
        "--lt-distance-threshold",
        type=float,
        default=DEFAULT_LT_DISTANCE_THRESHOLD,
        help=f"Distance threshold for LinkTransformer clustering (default: {DEFAULT_LT_DISTANCE_THRESHOLD}).",
    )
    parser.add_argument(
        "--lt-max-block-size",
        type=int,
        default=DEFAULT_LT_MAX_BLOCK_SIZE,
        help=f"Maximum block size for LinkTransformer pairwise clustering (default: {DEFAULT_LT_MAX_BLOCK_SIZE}).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed for validation sampling (default: {DEFAULT_SEED}).",
    )
    parser.add_argument(
        "--output-map-csv",
        default=DEFAULT_OUTPUT_MAP,
        help=f"Output person-ID map path (default: {DEFAULT_OUTPUT_MAP})",
    )
    parser.add_argument(
        "--output-validation-sample-csv",
        default=DEFAULT_OUTPUT_VALIDATION_SAMPLE,
        help=(
            "Output manual-validation sample path "
            f"(default: {DEFAULT_OUTPUT_VALIDATION_SAMPLE})"
        ),
    )
    parser.add_argument(
        "--output-summary-csv",
        default=DEFAULT_OUTPUT_SUMMARY,
        help=f"Output summary path (default: {DEFAULT_OUTPUT_SUMMARY})",
    )
    return parser.parse_args()


def _normalize_match_name(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = " ".join(text.split())
    return text


def _normalize_exact_key(value: object) -> str:
    """Normalize candidate name for exact matching.

    Strips accents and special characters so that e.g. 'José García' and
    'jose garcia' map to the same key.  Previously this only lowered/collapsed
    whitespace, missing accent variation – the most common source of name
    mismatches in Spanish data.
    """
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    # Strip combining diacritical marks (accents, tildes, etc.).
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    # Remove non-alphanumeric characters (hyphens, periods, etc.).
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = " ".join(text.split())
    return text


def _name_block_key(name_norm: str) -> str:
    tokens = name_norm.split()
    if not tokens:
        return "__EMPTY__"
    return f"{tokens[0][:3]}|{tokens[-1][:4]}|{len(tokens)}"


def _read_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def _resolve_person_id_col(columns: list[str], explicit_col: str) -> str:
    if explicit_col:
        if explicit_col in columns:
            return explicit_col
        raise ValueError(f"Provided panel ID column not found: {explicit_col}")
    for col in ["person_id", "panel_id", "Panel_ID", "panelid", "PanelID", "cluster_id"]:
        if col in columns:
            return col
    return ""


def _build_exact_person_id(df: pd.DataFrame, candidate_col: str) -> pd.DataFrame:
    out = df.copy()
    key = out[candidate_col].map(_normalize_exact_key)
    codes = pd.Series(key).astype("category").cat.codes + 1
    out["person_id"] = codes.map(lambda x: f"pid_exact_{int(x):07d}")
    out["person_id_source"] = "exact_string"
    return out


def _merge_provided_panel_id(
    df: pd.DataFrame,
    panel_path: Path,
    panel_id_col: str,
    candidate_col: str,
) -> tuple[pd.DataFrame, str, int]:
    panel = _read_table(panel_path)
    resolved_col = _resolve_person_id_col(list(panel.columns), explicit_col=panel_id_col)
    if not resolved_col:
        raise ValueError("Could not auto-detect person/panel ID column in provided panel file.")

    out = df.copy()
    unmatched = 0
    merge_mode = ""

    if set(ROW_KEYS).issubset(panel.columns) and set(ROW_KEYS).issubset(out.columns):
        lookup = (
            panel[ROW_KEYS + [resolved_col]]
            .dropna(subset=[resolved_col])
            .drop_duplicates(subset=ROW_KEYS, keep="first")
            .rename(columns={resolved_col: "_provided_person_id"})
        )
        out = out.merge(lookup, on=ROW_KEYS, how="left")
        merge_mode = "row_keys"
    elif candidate_col in panel.columns:
        lookup = (
            panel[[candidate_col, resolved_col]]
            .dropna(subset=[resolved_col])
            .drop_duplicates(subset=[candidate_col], keep="first")
            .rename(columns={resolved_col: "_provided_person_id"})
        )
        out = out.merge(lookup, on=[candidate_col], how="left")
        merge_mode = "candidate"
    else:
        raise ValueError(
            "Provided panel-ID merge failed. Need either row keys "
            "(election_ym, prv_code, p_code, list_pos) or candidate column."
        )

    unmatched = int(out["_provided_person_id"].isna().sum())
    out["person_id"] = out["_provided_person_id"].astype("string")
    out = out.drop(columns=["_provided_person_id"])

    # Keep pipeline complete by filling uncovered rows with exact matching IDs.
    if unmatched > 0:
        exact = _build_exact_person_id(out, candidate_col=candidate_col)
        out.loc[out["person_id"].isna(), "person_id"] = exact.loc[out["person_id"].isna(), "person_id"]
        out["person_id_source"] = np.where(
            out["person_id"].astype(str).str.startswith("pid_exact_"),
            "provided_panel_id_fallback_exact",
            "provided_panel_id",
        )
    else:
        out["person_id_source"] = "provided_panel_id"

    out["person_id"] = out["person_id"].astype(str)
    return out, merge_mode, unmatched


def _cluster_names_linktransformer(
    unique_names: pd.DataFrame,
    distance_threshold: float,
    max_block_size: int,
) -> pd.DataFrame:
    try:
        import linktransformer as lt
    except Exception as exc:
        raise RuntimeError(
            "LinkTransformer method requested but package is not installed. "
            "Install dependencies first (e.g., `pip install torch==2.3.0 linktransformer==0.1.15`)."
        ) from exc

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

    # Always union exact normalized matches.
    for _, idx in names.groupby("candidate_match_norm", dropna=False).groups.items():
        idx_list = list(idx)
        for j in idx_list[1:]:
            _union(idx_list[0], int(j))

    for _, idx in names.groupby("match_block", dropna=False).groups.items():
        idx_list = [int(v) for v in list(idx)]
        if len(idx_list) <= 1:
            continue
        if len(idx_list) > max_block_size:
            continue

        block_names = names.loc[idx_list, "candidate_match_norm"].fillna("").tolist()
        embeddings = model.encode(block_names)
        sim = cosine_similarity(embeddings)
        dist = np.maximum(1 - sim, 0)

        if len(idx_list) == 2:
            if float(dist[0, 1]) <= distance_threshold:
                _union(idx_list[0], idx_list[1])
            continue

        condensed = squareform(dist, force="tovector", checks=False)
        linkage_matrix = linkage(condensed, method="average")
        cluster_ids = fcluster(linkage_matrix, t=distance_threshold, criterion="distance")
        cluster_frame = pd.DataFrame({"idx": idx_list, "cluster_id": cluster_ids})
        for _, members in cluster_frame.groupby("cluster_id")["idx"]:
            m = members.tolist()
            for j in m[1:]:
                _union(m[0], int(j))

    roots = np.array([_find(i) for i in range(n)], dtype=int)
    labels = pd.Series(roots).astype("category").cat.codes + 1
    names["person_id"] = labels.map(lambda x: f"pid_lt_{int(x):07d}")
    return names[["candidate", "candidate_match_norm", "person_id"]]


def _build_linktransformer_person_id(
    df: pd.DataFrame,
    candidate_col: str,
    distance_threshold: float,
    max_block_size: int,
) -> pd.DataFrame:
    out = df.copy()
    unique_names = (
        out[[candidate_col, "candidate_match_norm", "match_block"]]
        .rename(columns={candidate_col: "candidate"})
        .drop_duplicates()
    )
    linked = _cluster_names_linktransformer(
        unique_names=unique_names,
        distance_threshold=distance_threshold,
        max_block_size=max_block_size,
    )
    out = out.merge(linked, left_on=[candidate_col, "candidate_match_norm"], right_on=["candidate", "candidate_match_norm"], how="left")
    out = out.drop(columns=["candidate_y"]).rename(columns={"candidate_x": candidate_col})
    if out["person_id"].isna().any():
        raise RuntimeError("LinkTransformer clustering produced missing person_id assignments.")
    out["person_id_source"] = "linktransformer"
    return out


def _sample_pair_records(
    df: pd.DataFrame,
    rng: np.random.Generator,
    n_target: int,
    pair_type: str,
) -> list[tuple[int, int]]:
    indices = df.index.to_numpy()
    if len(indices) < 2:
        return []

    pairs: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    if pair_type == "match":
        groups = {pid: idx.to_numpy() for pid, idx in df.groupby("person_id").groups.items() if len(idx) >= 2}
        if not groups:
            return []
        pids = np.array(list(groups.keys()))
        attempts = 0
        while len(pairs) < n_target and attempts < n_target * 200:
            pid = rng.choice(pids)
            grp = groups[pid]
            a, b = rng.choice(grp, size=2, replace=False)
            key = tuple(sorted((int(a), int(b))))
            if key not in seen:
                seen.add(key)
                pairs.append(key)
            attempts += 1
    else:
        attempts = 0
        while len(pairs) < n_target and attempts < n_target * 500:
            a, b = rng.choice(indices, size=2, replace=False)
            if df.loc[a, "person_id"] == df.loc[b, "person_id"]:
                attempts += 1
                continue
            key = tuple(sorted((int(a), int(b))))
            if key not in seen:
                seen.add(key)
                pairs.append(key)
            attempts += 1

    return pairs


def build_validation_sample(
    df: pd.DataFrame,
    candidate_col: str,
    seed: int,
    n_match: int = 200,
    n_nonmatch: int = 200,
) -> pd.DataFrame:
    work = df.copy().reset_index(drop=True)
    work["obs_idx"] = np.arange(len(work))
    rng = np.random.default_rng(seed)

    match_pairs = _sample_pair_records(work, rng=rng, n_target=n_match, pair_type="match")
    nonmatch_pairs = _sample_pair_records(work, rng=rng, n_target=n_nonmatch, pair_type="nonmatch")

    rows: list[dict[str, float | int | str]] = []
    for pair_type, pairs in [("match", match_pairs), ("nonmatch", nonmatch_pairs)]:
        for i, (a, b) in enumerate(pairs, start=1):
            row_a = work.loc[a]
            row_b = work.loc[b]
            sim = SequenceMatcher(
                None,
                str(row_a["candidate_match_norm"]),
                str(row_b["candidate_match_norm"]),
            ).ratio()
            rows.append(
                {
                    "pair_type": pair_type,
                    "pair_rank": i,
                    "obs_idx_a": int(row_a["obs_idx"]),
                    "obs_idx_b": int(row_b["obs_idx"]),
                    "candidate_a": row_a[candidate_col],
                    "candidate_b": row_b[candidate_col],
                    "candidate_match_norm_a": row_a["candidate_match_norm"],
                    "candidate_match_norm_b": row_b["candidate_match_norm"],
                    "person_id_a": row_a["person_id"],
                    "person_id_b": row_b["person_id"],
                    "same_person_id": int(row_a["person_id"] == row_b["person_id"]),
                    "similarity_score": float(sim),
                    "election_ym_a": row_a["election_ym"],
                    "election_ym_b": row_b["election_ym"],
                    "prv_code_a": row_a["prv_code"],
                    "prv_code_b": row_b["prv_code"],
                    "p_code_a": row_a["p_code"],
                    "p_code_b": row_b["p_code"],
                    "list_pos_a": row_a["list_pos"],
                    "list_pos_b": row_b["list_pos"],
                }
            )

    out = pd.DataFrame(rows)
    out = out.sort_values(["pair_type", "pair_rank"]).reset_index(drop=True)
    return out


def main() -> None:
    args = parse_args()

    data_path = Path(args.data)
    output_map = Path(args.output_map_csv)
    output_validation = Path(args.output_validation_sample_csv)
    output_summary = Path(args.output_summary_csv)

    output_map.parent.mkdir(parents=True, exist_ok=True)
    output_validation.parent.mkdir(parents=True, exist_ok=True)
    output_summary.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(data_path)
    required = [args.candidate_col, *ROW_KEYS]
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"Input data missing required columns: {missing}")

    base = df.copy()
    base["candidate_match_norm"] = base[args.candidate_col].map(_normalize_match_name)
    base["match_block"] = base["candidate_match_norm"].map(_name_block_key)

    method_used = args.method
    merge_mode = "n/a"
    unmatched = 0

    if args.method == "exact":
        linked = _build_exact_person_id(base, candidate_col=args.candidate_col)
    elif args.method == "provided":
        if not args.provided_panel_id:
            raise ValueError("--provided-panel-id is required when --method provided.")
        panel_path = Path(args.provided_panel_id)
        if not panel_path.exists():
            raise ValueError(f"Provided panel-ID file not found: {panel_path}")
        linked, merge_mode, unmatched = _merge_provided_panel_id(
            base,
            panel_path=panel_path,
            panel_id_col=args.provided_panel_id_col.strip(),
            candidate_col=args.candidate_col,
        )
        method_used = "provided_panel_id"
    else:
        linked = _build_linktransformer_person_id(
            base,
            candidate_col=args.candidate_col,
            distance_threshold=args.lt_distance_threshold,
            max_block_size=args.lt_max_block_size,
        )
        method_used = "linktransformer"

    map_cols = ROW_KEYS + [
        args.candidate_col,
        "candidate_match_norm",
        "person_id",
        "person_id_source",
    ]
    map_cols = [c for c in map_cols if c in linked.columns]
    linked[map_cols].to_csv(output_map, index=False)

    validation_df = build_validation_sample(
        linked,
        candidate_col=args.candidate_col,
        seed=args.seed,
        n_match=200,
        n_nonmatch=200,
    )
    validation_df.to_csv(output_validation, index=False)

    cluster_sizes = linked.groupby("person_id")[args.candidate_col].nunique()
    multi_name_ids = cluster_sizes[cluster_sizes > 1].index
    summary = BuildSummary(
        method_requested=args.method,
        method_used=method_used,
        data_rows=int(len(linked)),
        unique_candidates=int(linked[args.candidate_col].nunique()),
        unique_person_id=int(linked["person_id"].nunique()),
        multi_name_person_ids=int((cluster_sizes > 1).sum()),
        rows_in_multi_name_person_ids=int(linked["person_id"].isin(multi_name_ids).sum()),
        merge_mode=merge_mode,
        unmatched_after_merge=unmatched,
        lt_distance_threshold=float(args.lt_distance_threshold),
        lt_max_block_size=int(args.lt_max_block_size),
        validation_target_matches=200,
        validation_target_nonmatches=200,
        validation_actual_matches=int((validation_df["pair_type"] == "match").sum()) if not validation_df.empty else 0,
        validation_actual_nonmatches=int((validation_df["pair_type"] == "nonmatch").sum()) if not validation_df.empty else 0,
    )
    pd.DataFrame([summary.to_dict()]).to_csv(output_summary, index=False)

    print("Person-ID build completed.")
    print(f"Method requested: {args.method}")
    print(f"Method used: {method_used}")
    print(f"Person-ID map: {output_map}")
    print(f"Validation sample: {output_validation}")
    print(f"Summary: {output_summary}")
    print(f"Rows: {len(linked):,}")
    print(f"Unique person IDs: {linked['person_id'].nunique():,}")


if __name__ == "__main__":
    main()

