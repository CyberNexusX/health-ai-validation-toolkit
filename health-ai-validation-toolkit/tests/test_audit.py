import unittest

import numpy as np

from audit import population_stability, run, subgroups


class AuditTests(unittest.TestCase):
    def test_score_shift(self):
        reference = np.full(100, 0.08)
        self.assertAlmostEqual(population_stability(reference, reference), 0)
        self.assertGreater(population_stability(reference, np.full(100, 0.70)), 1)

    def test_unknown_is_separate_from_no_barrier(self):
        rows = [
            {"age_years": 50, "transport_barrier": None, "outcome": 0},
            {"age_years": 70, "transport_barrier": 0, "outcome": 1},
        ]
        report = subgroups(rows, np.array([0.2, 0.3]))
        self.assertEqual(report["transport_unknown"]["n"], 1)
        self.assertEqual(report["no_transport_barrier_recorded"]["events"], 1)
        self.assertEqual(report["transport_barrier_recorded"], {"n": 0})

    def test_held_out_shift_and_paired_comparison(self):
        report = run(42)
        held_out = report["evaluation"]["held_out_site"]
        self.assertTrue(held_out["feature_checks"]["transport_barrier"]["alert"])
        models = held_out["models"]
        for field in ("n", "events"):
            self.assertEqual(models["clinical"]["overall"][field],
                             models["with_transport"]["overall"][field])
        for model in models.values():
            explanation = model["example_explanation"]
            log_odds = explanation["intercept"] + sum(explanation["log_odds_contributions"].values())
            self.assertAlmostEqual(explanation["predicted_probability"], 1 / (1 + np.exp(-log_odds)))
        self.assertEqual(sum(group["n"] for group in (
            models["clinical"]["subgroups"]["transport_unknown"],
            models["clinical"]["subgroups"]["transport_barrier_recorded"],
            models["clinical"]["subgroups"]["no_transport_barrier_recorded"],
        )), models["clinical"]["overall"]["n"])


if __name__ == "__main__":
    unittest.main()
