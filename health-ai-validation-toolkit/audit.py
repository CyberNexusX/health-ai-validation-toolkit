"""Audit chronic-disease risk models under synthetic data and documentation shifts."""

import argparse
from pathlib import Path

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from study_fixture import HORIZON, build_cohort, generate, metrics, write_json

FEATURES = ("age_years", "latest_a1c", "a1c_change")
MODELS = {"clinical": FEATURES, "with_transport": (*FEATURES, "transport_barrier")}
SCORE_BINS = np.array([0, 0.10, 0.20, 0.30, 0.50, 1.0])
THRESHOLDS = {"missingness_increase": 0.15, "score_psi": 0.20, "absolute_calibration_gap": 0.05}


def add_transport(rows, seed):
    """Attach a simulated access-to-care field, preserving unknown values."""
    rng = np.random.default_rng(np.random.SeedSequence([seed, 1]))
    enriched = []
    for row in rows:
        coastal = row["site"] == "coastal"
        barrier_probability = 0.35 if row["age_years"] >= 65 else 0.18
        has_barrier = rng.random() < barrier_probability
        missing_probability = (0.55 if has_barrier else 0.28) if coastal else 0.12
        barrier = None if rng.random() < missing_probability else int(has_barrier)
        enriched.append({**row, "transport_barrier": barrier})
    return enriched


def matrix(rows, features):
    return np.array([[row[field] for field in features] for row in rows], dtype=float)


def fit(rows, features):
    model = make_pipeline(
        SimpleImputer(strategy="median", add_indicator=True),
        StandardScaler(),
        LogisticRegression(max_iter=1000),
    )
    return model.fit(matrix(rows, features), [row["outcome"] for row in rows])


def population_stability(reference, current):
    """Compare score distributions using fixed bins and half-count smoothing."""
    reference_counts = np.histogram(reference, bins=SCORE_BINS)[0] + 0.5
    current_counts = np.histogram(current, bins=SCORE_BINS)[0] + 0.5
    reference_rates = reference_counts / reference_counts.sum()
    current_rates = current_counts / current_counts.sum()
    return float(np.sum((current_rates - reference_rates) * np.log(current_rates / reference_rates)))


def missing_rates(rows):
    return {
        feature: sum(row[feature] is None for row in rows) / len(rows)
        for feature in MODELS["with_transport"]
    }


def summarize(rows, probabilities):
    result = metrics(rows, probabilities)
    if result["n"]:
        result["calibration_gap"] = result["mean_score"] - result["observed_rate"]
    return result


def subgroups(rows, probabilities):
    groups = {
        "age_under_65": [row["age_years"] < 65 for row in rows],
        "age_65_plus": [row["age_years"] >= 65 for row in rows],
        "transport_barrier_recorded": [row["transport_barrier"] == 1 for row in rows],
        "no_transport_barrier_recorded": [row["transport_barrier"] == 0 for row in rows],
        "transport_unknown": [row["transport_barrier"] is None for row in rows],
    }
    return {
        group: summarize([row for row, include in zip(rows, mask) if include], probabilities[mask])
        for group, mask in groups.items()
    }


def explain_example(rows, model, features):
    """Decompose one synthetic prediction on the fitted log-odds scale."""
    row = next((row for row in rows if row["transport_barrier"] is None), rows[0])
    transformed = model[:-1].transform(matrix([row], features))[0]
    imputer = model.named_steps["simpleimputer"]
    classifier = model.named_steps["logisticregression"]
    names = imputer.get_feature_names_out(list(features))
    terms = dict(zip(names, (transformed * classifier.coef_[0]).tolist()))
    return {
        "synthetic_patient_id": row["patient_id"],
        "features": {field: row[field] for field in features},
        "intercept": float(classifier.intercept_[0]),
        "log_odds_contributions": terms,
        "predicted_probability": float(model.predict_proba(matrix([row], features))[0, 1]),
    }


def audit_window(rows, models, reference_scores, reference_missing):
    current_missing = missing_rates(rows)
    feature_checks = {}
    for field, rate in current_missing.items():
        change = rate - reference_missing[field]
        feature_checks[field] = {
            "missing_rate": rate, "change_from_reference": change,
            "alert": change >= THRESHOLDS["missingness_increase"],
        }
    model_checks = {}
    for name, (model, features) in models.items():
        probabilities = model.predict_proba(matrix(rows, features))[:, 1]
        psi = population_stability(reference_scores[name], probabilities)
        performance = summarize(rows, probabilities)
        model_checks[name] = {
            "score_psi": psi,
            "score_drift_alert": psi >= THRESHOLDS["score_psi"],
            "calibration_alert": abs(performance["calibration_gap"])
            >= THRESHOLDS["absolute_calibration_gap"],
            "overall": performance,
            "subgroups": subgroups(rows, probabilities),
            "example_explanation": explain_example(rows, model, features),
        }
    return {"feature_checks": feature_checks, "models": model_checks}


def run(seed):
    bundle, metadata = generate(seed)
    rows = add_transport(build_cohort(bundle, metadata), seed)
    training = [row for row in rows if row["split"] == "train"]
    # Reserve a disjoint reference portion within each training-period clinic.
    counts_by_site = {}
    fit_rows, reference = [], []
    for row in training:
        site = row["site"]
        counts_by_site[site] = counts_by_site.get(site, 0) + 1
        target = reference if counts_by_site[site] % 5 == 0 else fit_rows
        target.append(row)
    models = {name: (fit(fit_rows, features), features) for name, features in MODELS.items()}
    reference_missing = missing_rates(reference)
    reference_scores = {
        name: model.predict_proba(matrix(reference, features))[:, 1]
        for name, (model, features) in models.items()
    }
    return {
        "synthetic_only": True, "seed": seed, "horizon_days": HORIZON,
        "fit_count": len(fit_rows), "reference_count": len(reference),
        "reference_missingness": reference_missing,
        "score_bins": SCORE_BINS.tolist(), "demo_thresholds": THRESHOLDS,
        "evaluation": {
            split: audit_window(
                [row for row in rows if row["split"] == split],
                models, reference_scores, reference_missing,
            )
            for split in ("later_period", "held_out_site")
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=Path("build/audit-report.json"))
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.out, run(args.seed))
    print(f"Audit report: {args.out}")
