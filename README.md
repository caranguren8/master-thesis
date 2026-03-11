# Master Thesis Project

## Data Build (first step)

Extract eligible voters from the election `.xlsx` files:

```bash
python3 src/data/extract_eligible_voters_xlsx.py --input-dir data/external/eligible_voters/xlsx --output-csv data/processed/eligible_voters_extracted.csv
```

Build the analysis-ready merged dataset from the two supervisor-provided files:

```bash
python3 src/data/build_master_dataset.py
```

If you already have eligible voters by district-election, pass it in and the script
will compute `running_variable = votemargin / eligible_voters` automatically:

```bash
python3 src/data/build_master_dataset.py --eligible-voters-csv data/processed/eligible_voters_extracted.csv
```

Outputs:
- `data/processed/spain_master_dataset.csv`
- `data/processed/qa_summary.json`
- `data/processed/eligible_voters_extracted.csv` (from `.xlsx`)

Notes:
- Raw election source files are expected in `data/raw/elections/`.
- Reference PDFs/emails are stored in `docs/source_materials/`.
- The CSV source file is read with robust UTF-8 decoding (`encoding_errors="replace"`).
- The merge key is `election_ym` + `prv_code` + `p_code` + `list_pos`.
- `eligible_voters` input columns must be: `election_ym`, `prv_code`, `eligible_voters`.

## Baseline RDD

Estimate a baseline local-linear RDD around the cutoff (`running_variable = 0`)
with triangular kernel, bandwidth sensitivity grid, RDD plots, and placebo checks:

```bash
python3 src/data/build_person_id.py \
  --data data/processed/spain_master_dataset.csv \
  --method exact \
  --output-map-csv data/processed/person_id_map.csv \
  --output-validation-sample-csv data/processed/person_id_validation_sample.csv \
  --output-summary-csv data/processed/person_id_build_summary.csv
```

Then run the main RD pipeline:

```bash
python3 src/models/rdd_baseline_local_linear.py \
  --data data/processed/spain_master_dataset.csv \
  --person-id-map-csv data/processed/person_id_map.csv \
  --bandwidth 0.05 \
  --bandwidth-grid 0.025,0.05,0.075,0.10 \
  --outcome both
```

Outputs:
- `data/processed/person_id_map.csv`
- `data/processed/person_id_validation_sample.csv`
- `data/processed/person_id_build_summary.csv`
- `data/processed/rdd_baseline_estimates.csv`
- `data/processed/rdd_fuzzy_estimates.csv`
- `data/processed/rdd_fuzzy_estimates_selected_bw.csv`
- `data/processed/rdd_sharp_vs_fuzzy_comparison.csv`
- `data/processed/rdd_balance_placebo_checks.csv`
- `data/processed/rdd_balance_placebo_pretreatment.csv`
- `data/processed/rdd_treatment_validation.csv`
- `data/processed/rdd_treatment_mismatches.csv`
- `data/processed/rdd_female_placebo_diagnostics.csv`
- `data/processed/rdd_female_placebo_closest20.csv`
- `data/processed/rdd_person_id_assignment.csv`
- `data/processed/rdd_person_id_validation_report.csv`
- `data/processed/rdd_person_id_vs_string_estimates_long.csv`
- `data/processed/rdd_person_id_vs_string_comparison.csv`
- `data/processed/rdd_bandwidth_selection.csv`
- `data/processed/rdd_baseline_estimates_selected_bw.csv`
- `data/processed/rdd_running_variable_density_bins.csv`
- `data/processed/rdd_running_variable_density_summary.csv`
- `data/processed/rdd_outcomes_enriched.csv`
- `data/processed/windows/rdd_window_bw0p025.csv`
- `data/processed/windows/rdd_window_bw0p050.csv`
- `data/processed/windows/rdd_window_bw0p075.csv`
- `data/processed/windows/rdd_window_bw0p100.csv`
- `data/processed/figures/rdd_plot_wins_next_bw0p050.png`
- `data/processed/figures/rdd_plot_runs_next_bw0p050.png`
- `data/processed/figures/rdd_bandwidth_sensitivity_main.png`
- `data/processed/figures/rdd_bandwidth_sensitivity_balance.png`
- `data/processed/figures/rdd_running_density_bw0p025.png`
- `data/processed/figures/rdd_running_density_bw0p050.png`
- `data/processed/figures/rdd_running_density_bw0p075.png`
- `data/processed/figures/rdd_running_density_bw0p100.png`

Per-bandwidth window files contain one row per observation per estimation (`analysis_type`, `outcome`)
and include `treated`, triangular-kernel `weights`, and plot bin assignment (`plot_side`, `bin_in_side`, `plot_bin`).

Person-ID build methods:
- `--method exact`: deterministic exact string linkage.
- `--method provided`: merge an external panel-ID table (`--provided-panel-id` and optional `--provided-panel-id-col`).
- `--method linktransformer`: embedding-based clustering. If `linktransformer` is not installed, the script fails with a clear error (no silent fallback).
- Manual validation output is always generated with up to 200 matched pairs + 200 non-matches, including similarity scores.

Fuzzy RD outputs:
- Fuzzy RD uses `elected_dta` as treatment \(D\), `running_variable` as forcing variable, and a local Wald estimator at the cutoff.
- `rdd_fuzzy_estimates.csv` includes first-stage discontinuity (`first_stage_tau`: jump in \(P(D=1)\) at 0) and fuzzy LATE estimates for `runs_next` and `wins_next`.
- `rdd_fuzzy_estimates_selected_bw.csv` includes fuzzy estimates exactly at each outcome’s data-driven selected bandwidth (same bandwidth used in `rdd_baseline_estimates_selected_bw.csv`).
- `rdd_sharp_vs_fuzzy_comparison.csv` reports sharp and fuzzy estimates side-by-side by outcome, bandwidth, and SE type.

Notes on bandwidth selection:
- The script writes a data-driven selector report in `rdd_bandwidth_selection.csv`.
- If Python `rdrobust` is available, it uses a CCT-style selector from `rdbwselect`.
- Otherwise it uses an IK-style local-linear plug-in fallback and reports all pilot quantities used.

Notes on standard errors:
- Main estimates now include `se_type` and report both `hc1` and clustered SE variants by default.
- Supported clustering definitions: `cluster_prv_election` and `cluster_prv_election_party`.
- You can control this with `--se-types`.

## Thesis Tables Export

Build publication-ready tables (CSV + LaTeX + Markdown) from the latest estimates:

```bash
python3 src/models/make_thesis_tables.py \
  --preferred-se cluster_prv_election \
  --bandwidth-grid 0.025,0.05,0.075,0.10 \
  --se-table-bandwidth 0.05 \
  --outcome-definition-bandwidth 0.05 \
  --outdir data/processed/thesis_tables
```

Outputs:
- `data/processed/thesis_tables/thesis_main_sharp_fuzzy_selected_bw.csv`
- `data/processed/thesis_tables/thesis_main_sharp_fuzzy_selected_bw.tex`
- `data/processed/thesis_tables/thesis_main_sharp_fuzzy_selected_bw.md`
- `data/processed/thesis_tables/thesis_robustness_bandwidth_grid.csv`
- `data/processed/thesis_tables/thesis_robustness_bandwidth_grid.tex`
- `data/processed/thesis_tables/thesis_robustness_bandwidth_grid.md`
- `data/processed/thesis_tables/thesis_robustness_se_types.csv`
- `data/processed/thesis_tables/thesis_robustness_se_types.tex`
- `data/processed/thesis_tables/thesis_robustness_se_types.md`
- `data/processed/thesis_tables/thesis_robustness_outcome_definition.csv`
- `data/processed/thesis_tables/thesis_robustness_outcome_definition.tex`
- `data/processed/thesis_tables/thesis_robustness_outcome_definition.md`
