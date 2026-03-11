#!/usr/bin/env python3
"""Extract eligible voters from Spain election .xlsx files without openpyxl.

The source files are expected to contain a worksheet with:
- "Código de Provincia"
- "Total censo electoral"

Output columns:
- election_ym
- prv_code
- eligible_voters
- province_name
- source_file
"""

from __future__ import annotations

import argparse
import csv
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract eligible voters from election XLSX files.")
    parser.add_argument(
        "--input-dir",
        default="data/external/eligible_voters/xlsx",
        help="Directory with .xlsx files (default: data/external/eligible_voters/xlsx).",
    )
    parser.add_argument(
        "--output-csv",
        default="data/processed/eligible_voters_extracted.csv",
        help="Output CSV path.",
    )
    return parser.parse_args()


def col_to_idx(col: str) -> int:
    val = 0
    for ch in col:
        val = val * 26 + (ord(ch) - 64)
    return val - 1


def _cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    value_node = cell.find(f"{{{NS_MAIN}}}v")
    if value_node is None:
        return ""
    raw = value_node.text or ""
    if cell_type == "s" and raw.isdigit():
        idx = int(raw)
        if 0 <= idx < len(shared_strings):
            return shared_strings[idx]
    return raw


def read_sheet_rows(xlsx_path: Path) -> list[tuple[int, dict[int, str]]]:
    with zipfile.ZipFile(xlsx_path) as zf:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst_root.findall(f"{{{NS_MAIN}}}si"):
                shared_strings.append(
                    "".join((node.text or "") for node in si.iter(f"{{{NS_MAIN}}}t"))
                )

        sheet_root = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        sheet_data = sheet_root.find(f"{{{NS_MAIN}}}sheetData")
        if sheet_data is None:
            return []

        rows: list[tuple[int, dict[int, str]]] = []
        for row in sheet_data.findall(f"{{{NS_MAIN}}}row"):
            row_num = int(row.attrib.get("r", "0"))
            row_cells: dict[int, str] = {}
            for cell in row.findall(f"{{{NS_MAIN}}}c"):
                ref = cell.attrib.get("r", "")
                match = re.match(r"([A-Z]+)", ref)
                if not match:
                    continue
                col_idx = col_to_idx(match.group(1))
                row_cells[col_idx] = _cell_text(cell, shared_strings)
            rows.append((row_num, row_cells))
        return rows


def detect_header(rows: list[tuple[int, dict[int, str]]]) -> tuple[int, int, int, int]:
    for row_num, row in rows[:30]:
        lowered = {k: str(v).strip().lower() for k, v in row.items()}
        has_province_code = any("código de provincia" in v for v in lowered.values())
        has_total_census = any("total censo electoral" in v for v in lowered.values())
        if has_province_code and has_total_census:
            prv_col = next(k for k, v in lowered.items() if "código de provincia" in v)
            eligible_col = next(k for k, v in lowered.items() if "total censo electoral" in v)
            province_name_col = next(
                k for k, v in lowered.items() if "nombre de provincia" in v
            )
            return row_num, prv_col, eligible_col, province_name_col
    raise ValueError("Could not detect header row with province and eligible-voter columns.")


def extract_from_file(xlsx_path: Path) -> list[dict[str, object]]:
    year_match = re.search(r"(\d{6})", xlsx_path.name)
    if not year_match:
        raise ValueError(f"Could not infer election_ym from filename: {xlsx_path.name}")
    election_ym = int(year_match.group(1))

    rows = read_sheet_rows(xlsx_path)
    header_row, prv_col, eligible_col, province_col = detect_header(rows)

    extracted: dict[int, dict[str, object]] = {}
    for row_num, row in rows:
        if row_num <= header_row:
            continue
        prv_raw = str(row.get(prv_col, "")).strip()
        eligible_raw = str(row.get(eligible_col, "")).strip()
        province_name = str(row.get(province_col, "")).strip()

        if not prv_raw.isdigit() or not eligible_raw.isdigit():
            continue
        prv_code = int(prv_raw)
        eligible_voters = int(eligible_raw)
        extracted[prv_code] = {
            "election_ym": election_ym,
            "prv_code": prv_code,
            "eligible_voters": eligible_voters,
            "province_name": province_name,
            "source_file": xlsx_path.name,
        }

    if len(extracted) != 52:
        missing = [code for code in range(1, 53) if code not in extracted]
        raise ValueError(
            f"{xlsx_path.name}: expected 52 provinces, got {len(extracted)}. Missing: {missing}"
        )
    return [extracted[k] for k in sorted(extracted)]


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_csv = Path(args.output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    files = sorted(input_dir.glob("*.xlsx"))
    if not files:
        raise FileNotFoundError(f"No .xlsx files found in {input_dir}")

    records: list[dict[str, object]] = []
    for file_path in files:
        records.extend(extract_from_file(file_path))

    # Enforce uniqueness by election_ym + prv_code.
    seen: set[tuple[int, int]] = set()
    for rec in records:
        key = (int(rec["election_ym"]), int(rec["prv_code"]))
        if key in seen:
            raise ValueError(f"Duplicate key found in extracted records: {key}")
        seen.add(key)

    fieldnames = ["election_ym", "prv_code", "eligible_voters", "province_name", "source_file"]
    with output_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for rec in sorted(records, key=lambda r: (int(r["election_ym"]), int(r["prv_code"]))):
            writer.writerow(rec)

    print(f"Extracted {len(records)} rows from {len(files)} files.")
    print(f"Wrote: {output_csv}")


if __name__ == "__main__":
    main()
