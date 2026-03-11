#!/usr/bin/env python3
"""Build an analysis-ready master dataset for the Spain incumbency project.

The script merges:
1) General candidate/election data (.dta)
2) Vote margin data (.csv)

Output:
- data/processed/spain_master_dataset.csv
- data/processed/qa_summary.json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_DTA = "data/raw/elections/Spain_master_2004-2023-2.dta"
DEFAULT_CSV = "data/raw/elections/Spain_final_2004_2023_R.csv"
DEFAULT_OUTPUT_CSV = "data/processed/spain_master_dataset.csv"
DEFAULT_QA_JSON = "data/processed/qa_summary.json"

MERGE_KEYS = ["election_ym", "prv_code", "p_code", "list_pos"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge Spain election base data with vote margins."
    )
    parser.add_argument("--dta", default=DEFAULT_DTA, help="Path to master .dta file")
    parser.add_argument("--csv", default=DEFAULT_CSV, help="Path to vote margin .csv file")
    parser.add_argument(
        "--eligible-voters-csv",
        default=None,
        help=(
            "Optional CSV with eligible voters at district-election level. "
            "Expected columns: election_ym (or year), prv_code, eligible_voters."
        ),
    )
    parser.add_argument(
        "--output-csv",
        default=DEFAULT_OUTPUT_CSV,
        help="Output path for merged analysis-ready CSV",
    )
    parser.add_argument(
        "--qa-json",
        default=DEFAULT_QA_JSON,
        help="Output path for QA summary JSON",
    )
    return parser.parse_args()


def _normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = " ".join(text.split())
    return text


def load_vote_margin_csv(path: Path) -> pd.DataFrame:
    # The file is mostly UTF-8 but contains a few problematic bytes.
    # "replace" keeps loading robust while preserving almost all content.
    df = pd.read_csv(path, sep=";", encoding="utf-8", encoding_errors="replace")

    required_cols = {
        "year",
        "prv_code",
        "p_code",
        "list_pos",
        "candidate_orig",
        "votemargin",
    }
    missing = sorted(required_cols - set(df.columns))
    if missing:
        raise ValueError(f"Vote-margin CSV missing required columns: {missing}")

    # year in this file is election year+month (e.g. 201904).
    df = df.rename(columns={"year": "election_ym", "candidate_orig": "candidate_orig_csv"})
    df["election_ym"] = df["election_ym"].astype("Int64")
    df["candidate_norm_csv"] = df["candidate_orig_csv"].map(_normalize_text)
    return df


def load_master_dta(path: Path) -> pd.DataFrame:
    df = pd.read_stata(path)

    required_cols = {
        "year",
        "month",
        "prv_code",
        "p_code",
        "list_pos",
        "candidate_orig",
    }
    missing = sorted(required_cols - set(df.columns))
    if missing:
        raise ValueError(f"Master DTA missing required columns: {missing}")

    df = df.rename(columns={"candidate_orig": "candidate_orig_dta"})
    df["election_ym"] = (df["year"].astype("Int64") * 100 + df["month"].astype("Int64")).astype(
        "Int64"
    )
    df["candidate_norm_dta"] = df["candidate_orig_dta"].map(_normalize_text)
    return df


@dataclass
class QaSummary:
    source_rows_csv: int
    source_rows_dta: int
    merged_rows: int
    left_only_rows: int
    right_only_rows: int
    key_duplicates_csv: int
    key_duplicates_dta: int
    missing_votemargin: int
    election_ym_min: int
    election_ym_max: int
    provinces: int
    unique_parties: int
    elected_share: float
    eligible_voters_non_missing: int
    running_variable_non_missing: int

    def to_dict(self) -> dict:
        return {
            "source_rows_csv": self.source_rows_csv,
            "source_rows_dta": self.source_rows_dta,
            "merged_rows": self.merged_rows,
            "left_only_rows": self.left_only_rows,
            "right_only_rows": self.right_only_rows,
            "key_duplicates_csv": self.key_duplicates_csv,
            "key_duplicates_dta": self.key_duplicates_dta,
            "missing_votemargin": self.missing_votemargin,
            "election_ym_min": self.election_ym_min,
            "election_ym_max": self.election_ym_max,
            "provinces": self.provinces,
            "unique_parties": self.unique_parties,
            "elected_share": self.elected_share,
            "eligible_voters_non_missing": self.eligible_voters_non_missing,
            "running_variable_non_missing": self.running_variable_non_missing,
        }


def assert_unique_keys(df: pd.DataFrame, keys: Iterable[str], label: str) -> int:
    duplicates = int(df.duplicated(list(keys)).sum())
    if duplicates:
        raise ValueError(f"{label} has {duplicates} duplicate rows for keys {list(keys)}")
    return duplicates


def load_eligible_voters(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    cols = {c.lower(): c for c in raw.columns}

    if "election_ym" in cols:
        election_col = cols["election_ym"]
        election_ym = raw[election_col].astype("Int64")
    elif "year" in cols:
        # Accept yearly IDs as a fallback, but month-specific election IDs are preferred.
        election_col = cols["year"]
        year_series = raw[election_col].astype("Int64")
        if (year_series > 9999).all():
            election_ym = year_series
        else:
            raise ValueError(
                "Eligible-voters file has 'year' only. Please provide election_ym "
                "(e.g., 201904 and 201911 for split-election years)."
            )
    else:
        raise ValueError("Eligible-voters CSV must contain 'election_ym' (preferred) or 'year'.")

    if "prv_code" not in cols:
        raise ValueError("Eligible-voters CSV must contain 'prv_code'.")
    if "eligible_voters" not in cols:
        raise ValueError("Eligible-voters CSV must contain 'eligible_voters'.")

    out = pd.DataFrame(
        {
            "election_ym": election_ym,
            "prv_code": raw[cols["prv_code"]].astype("Int64"),
            "eligible_voters": pd.to_numeric(raw[cols["eligible_voters"]], errors="coerce").astype(
                "Int64"
            ),
        }
    )
    if out.duplicated(["election_ym", "prv_code"]).any():
        dup_count = int(out.duplicated(["election_ym", "prv_code"]).sum())
        raise ValueError(
            f"Eligible-voters file has {dup_count} duplicate rows for keys "
            "['election_ym', 'prv_code']."
        )
    return out


def build_dataset(
    csv_df: pd.DataFrame, dta_df: pd.DataFrame, eligible_df: pd.DataFrame | None = None
) -> tuple[pd.DataFrame, QaSummary]:
    key_duplicates_csv = assert_unique_keys(csv_df, MERGE_KEYS, "CSV data")
    key_duplicates_dta = assert_unique_keys(dta_df, MERGE_KEYS, "DTA data")

    merged = csv_df.merge(
        dta_df,
        on=MERGE_KEYS,
        how="outer",
        indicator=True,
        suffixes=("_csv", "_dta"),
        validate="one_to_one",
    )

    left_only = int((merged["_merge"] == "left_only").sum())
    right_only = int((merged["_merge"] == "right_only").sum())
    if left_only or right_only:
        raise ValueError(
            f"Merge mismatch detected: left_only={left_only}, right_only={right_only}."
        )

    merged["election_year"] = (merged["election_ym"] // 100).astype("Int64")
    merged["election_month"] = (merged["election_ym"] % 100).astype("Int64")

    # Use DTA text if available; otherwise fall back to CSV text.
    merged["candidate_orig_final"] = np.where(
        merged["candidate_orig_dta"].notna(),
        merged["candidate_orig_dta"],
        merged["candidate_orig_csv"],
    )

    # Placeholder for assignment variable normalization.
    # Fill this later once eligible voters per district-election are added.
    merged["eligible_voters"] = pd.Series(pd.NA, index=merged.index, dtype="Int64")
    if eligible_df is not None:
        merged = merged.merge(
            eligible_df,
            on=["election_ym", "prv_code"],
            how="left",
            suffixes=("", "_eligible"),
            validate="many_to_one",
        )
        # Prefer eligible-voter values from the auxiliary file.
        merged["eligible_voters"] = merged["eligible_voters_eligible"]
        merged = merged.drop(columns=["eligible_voters_eligible"])

    merged["running_variable"] = (
        pd.to_numeric(merged["votemargin"], errors="coerce")
        / pd.to_numeric(merged["eligible_voters"], errors="coerce")
    ).astype("Float64")

    elected_col = "elected_dta" if "elected_dta" in merged.columns else "elected_csv"

    qa = QaSummary(
        source_rows_csv=int(len(csv_df)),
        source_rows_dta=int(len(dta_df)),
        merged_rows=int(len(merged)),
        left_only_rows=left_only,
        right_only_rows=right_only,
        key_duplicates_csv=key_duplicates_csv,
        key_duplicates_dta=key_duplicates_dta,
        missing_votemargin=int(merged["votemargin"].isna().sum()),
        election_ym_min=int(merged["election_ym"].min()),
        election_ym_max=int(merged["election_ym"].max()),
        provinces=int(merged["prv_code"].nunique()),
        unique_parties=int(merged["p_code"].nunique()),
        elected_share=float(pd.to_numeric(merged[elected_col], errors="coerce").mean()),
        eligible_voters_non_missing=int(merged["eligible_voters"].notna().sum()),
        running_variable_non_missing=int(merged["running_variable"].notna().sum()),
    )
    return merged, qa


def main() -> None:
    args = parse_args()

    dta_path = Path(args.dta)
    csv_path = Path(args.csv)
    output_csv = Path(args.output_csv)
    qa_json = Path(args.qa_json)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    qa_json.parent.mkdir(parents=True, exist_ok=True)

    csv_df = load_vote_margin_csv(csv_path)
    dta_df = load_master_dta(dta_path)
    eligible_df = (
        load_eligible_voters(Path(args.eligible_voters_csv))
        if args.eligible_voters_csv
        else None
    )
    merged, qa = build_dataset(csv_df, dta_df, eligible_df=eligible_df)

    merged = merged.sort_values(MERGE_KEYS).reset_index(drop=True)
    merged.to_csv(output_csv, index=False)
    qa_json.write_text(json.dumps(qa.to_dict(), indent=2), encoding="utf-8")

    print("Master dataset created.")
    print(f"Rows: {qa.merged_rows:,}")
    print(f"Output CSV: {output_csv}")
    print(f"QA JSON: {qa_json}")


if __name__ == "__main__":
    main()
