# Health AI Validation Toolkit — User Guide

This guide covers how to run the audit, reproduce the bundled report, and navigate the JSON output. The [project homepage](README.md) contains the study design, default results, and sample use cases.

## Installation

Use Python **3.11 or 3.12** and run the commands from the folder containing `audit.py` and `requirements.txt`.

### macOS or Linux

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run the audit

```bash
python audit.py
```

The script generates the cohort, fits both models, and writes the audit to `build/audit-report.json`.

| Option | Default | Purpose |
|---|---|---|
| `--seed` | `42` | Controls the synthetic patient sample and simulated transportation documentation |
| `--out` | `build/audit-report.json` | Sets the output path for the JSON report |

Use a unique output filename to keep two runs for comparison:

```bash
python audit.py --seed 42 --out build/audit-seed-42.json
python audit.py --seed 123 --out build/audit-seed-123.json
```

Both runs use the same simulation design. The seed changes the sampled patients, observations, and documentation patterns.

## Navigate the report

| JSON path | What it contains |
|---|---|
| `fit_count` and `reference_count` | Number of eligible 2022 patients reserved for model fitting and reference comparisons |
| `reference_missingness` | Missing fraction for each monitored input in the reference cohort |
| `score_bins` | Fixed probability bin boundaries used by the score-distribution calculation |
| `demo_thresholds` | Alert settings used in the run |
| `evaluation.later_period` | Results for later North and South patients, evaluated together |
| `evaluation.held_out_site` | Results for Coastal, excluded from fitting and reference |
| `evaluation.<window>.feature_checks` | Missing fraction, change from reference, and alert flag per input |
| `evaluation.<window>.models` | Results for the `clinical` and `with_transport` models |
| `evaluation.<window>.models.<model>.overall` | Patient and event counts, observed rate, mean score, discrimination, Brier score, and calibration |
| `evaluation.<window>.models.<model>.subgroups` | Metrics by age band and transportation documentation status |
| `evaluation.<window>.models.<model>.example_explanation` | Original feature values, intercept, log-odds contributions, and predicted probability for one synthetic patient |

The report stores rates as proportions. For example, `0.344` is **34.4%**. A difference of `0.233` is **23.3 percentage points**.

### Metric definitions

- **AUROC** summarizes ranking between patients with and without the recorded outcome.
- **Average precision** summarizes precision across recall levels. Interpret it alongside outcome prevalence.
- **Brier score** is the average squared difference between the predicted probability and the observed binary outcome.
- **Calibration gap** is `mean_score - observed_rate`. Negative values indicate average underprediction.
- **Calibration bins** contain the number of patients, mean score, and observed rate in each populated range.
- **PSI** compares the score distribution with the reference distribution. The implementation uses fixed bins and adds 0.5 to each bin count before normalizing.

An empty subgroup returns `{"n": 0}`. A subgroup with only one outcome class reports `null` for AUROC and average precision.

## Alert rules

| Alert | Trigger | Data required |
|---|---|---|
| Feature missingness | Evaluation missing fraction rises at least 15 percentage points above reference | Feature values |
| Score-distribution shift | PSI is at least 0.20 | Evaluation and reference scores |
| Aggregate calibration | Absolute calibration gap is at least 5 percentage points | Evaluation scores and observed outcomes |

The score-distribution bins and the calibration bins serve different calculations. The top-level `score_bins` field documents the bins used for PSI. Each metric block shows the probability ranges used for its calibration summary.

The thresholds are illustrative. A real monitoring policy would also specify cohort size, outcome maturity, expected variability, and what happens after an alert.

## Verify the default run

```bash
python -m unittest discover -s tests -v
python audit.py --seed 42 --out build/audit-seed-42.json
```

On macOS or Linux, compare the new output with the bundled report:

```bash
cmp docs/sample-audit-report.json build/audit-seed-42.json
```

On Windows PowerShell, compare their SHA-256 hashes:

```powershell
Get-FileHash docs/sample-audit-report.json, build/audit-seed-42.json
```

The bundled report reproduced byte for byte in the development environment. Use the pinned dependency versions when checking reproducibility. If an environment produces small numerical differences, compare the counts, alert flags, and metrics before interpreting the discrepancy.

The tests check that:

- PSI is zero when two distributions match and increases when the example distribution shifts.
- Unknown transportation status is counted separately from a documented absence of a barrier.
- Both models use the same held-out cohort and outcome counts.
- The default held-out simulation triggers the transportation missingness alert.
- The displayed explanation terms reconstruct the reported probability.

The generated `build/` directory is local output. The checked-in result for readers is [docs/sample-audit-report.json](docs/sample-audit-report.json).