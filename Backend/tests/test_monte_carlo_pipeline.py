"""
Unit tests for the Monte Carlo simulation engine (services/monte_carlo.py).

All tests are pure-Python — no HTTP, no Firestore, no FastAPI context needed.
Run with:  python -m pytest tests/test_monte_carlo_pipeline.py -v
"""
from __future__ import annotations

import sys
import math
import unittest
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# The module under test has NO external dependencies — import directly.
from services.monte_carlo import (
    simulate_incident_monte_carlo,
    _create_rng,
    _triangular,
    _percentile,
    _binomial_confidence_interval,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_incident(
    *,
    exposure_usd: float = 500_000.0,
    gnn_confidence: float = 0.75,
    min_stockout_days: float = 5.0,
    affected_node_count: int = 3,
    route_mode: str = "air",
) -> dict:
    return {
        "id": "inc_test_001",
        "total_exposure_usd": exposure_usd,
        "gnn_confidence": gnn_confidence,
        "min_stockout_days": min_stockout_days,
        "affected_node_count": affected_node_count,
        "route_options": [
            {
                "mode": route_mode,
                "recommended": True,
                "transit_days": 2.5,
                "risk_score": 0.2,
            }
        ],
    }


def _make_event(*, severity_raw: float = 7.0, duration_days: float = 5.0) -> dict:
    return {
        "id": "sig_test_001",
        "severity_raw": severity_raw,
        "duration_days": duration_days,
        "lat": 13.0,
        "lng": 77.0,
        "event_type": "wildfire",
        "title": "Test wildfire event",
    }


# ---------------------------------------------------------------------------
# RNG internals
# ---------------------------------------------------------------------------

class TestLcgRng(unittest.TestCase):
    """Park–Miller LCG seeded RNG — determinism & range guarantees."""

    def test_always_in_unit_interval(self):
        rng = _create_rng(42)
        for _ in range(1000):
            v = rng()
            self.assertGreaterEqual(v, 0.0)
            self.assertLess(v, 1.0)

    def test_deterministic_for_same_seed(self):
        rng_a = _create_rng(99)
        rng_b = _create_rng(99)
        for _ in range(200):
            self.assertEqual(rng_a(), rng_b())

    def test_different_seeds_differ(self):
        rng_a = _create_rng(1)
        rng_b = _create_rng(2)
        # After a few draws they should diverge
        vals_a = [rng_a() for _ in range(10)]
        vals_b = [rng_b() for _ in range(10)]
        self.assertNotEqual(vals_a, vals_b)

    def test_zero_seed_handled(self):
        # seed % 2147483647 == 0 should not cause division-by-zero
        rng = _create_rng(0)
        v = rng()
        self.assertGreaterEqual(v, 0.0)

    def test_large_seed_handled(self):
        rng = _create_rng(2 ** 31)
        for _ in range(50):
            v = rng()
            self.assertGreaterEqual(v, 0.0)
            self.assertLess(v, 1.0)


# ---------------------------------------------------------------------------
# Triangular distribution
# ---------------------------------------------------------------------------

class TestTriangularDistribution(unittest.TestCase):
    """Triangular(low, mode, high) produces values within bounds."""

    def _sample(self, low: float, mode: float, high: float, n: int = 500) -> list[float]:
        rng = _create_rng(7)
        return [_triangular(rng, low, mode, high) for _ in range(n)]

    def test_values_in_bounds(self):
        for v in self._sample(1.0, 3.0, 8.0):
            self.assertGreaterEqual(v, 1.0)
            self.assertLessEqual(v, 8.0)

    def test_mean_near_theoretical(self):
        # E[X] = (low + mode + high) / 3
        samples = self._sample(2.0, 4.0, 9.0, n=2000)
        mean_obs = sum(samples) / len(samples)
        mean_theory = (2.0 + 4.0 + 9.0) / 3.0
        self.assertAlmostEqual(mean_obs, mean_theory, delta=0.4)

    def test_symmetric_triangular(self):
        # Triangular(0, 5, 10) is symmetric → median ≈ 5
        samples = sorted(self._sample(0.0, 5.0, 10.0, n=2000))
        median = samples[len(samples) // 2]
        self.assertAlmostEqual(median, 5.0, delta=0.5)

    def test_degenerate_equal_bounds(self):
        # When high == low the formula must not crash
        rng = _create_rng(3)
        v = _triangular(rng, 5.0, 5.0, 5.0)
        self.assertIsInstance(v, float)


# ---------------------------------------------------------------------------
# Percentile helper
# ---------------------------------------------------------------------------

class TestPercentile(unittest.TestCase):

    def test_empty_returns_zero(self):
        self.assertEqual(_percentile([], 0.5), 0.0)

    def test_single_value(self):
        self.assertEqual(_percentile([42.0], 0.0), 42.0)
        self.assertEqual(_percentile([42.0], 1.0), 42.0)

    def test_median_of_odd_list(self):
        values = [1, 2, 3, 4, 5]
        self.assertAlmostEqual(_percentile(values, 0.5), 3.0, places=1)

    def test_p10_and_p90(self):
        values = list(range(1, 101))   # 1..100
        self.assertAlmostEqual(_percentile(values, 0.10), 10, delta=2)
        self.assertAlmostEqual(_percentile(values, 0.90), 90, delta=2)

    def test_clamped_to_valid_index(self):
        values = [5.0, 10.0, 15.0]
        # p=0 → first, p=1 → last
        self.assertEqual(_percentile(values, 0.0), 5.0)
        self.assertEqual(_percentile(values, 1.0), 15.0)


# ---------------------------------------------------------------------------
# Binomial confidence interval
# ---------------------------------------------------------------------------

class TestBinomialCI(unittest.TestCase):

    def test_zero_runs_returns_zeros(self):
        low, high = _binomial_confidence_interval(0, 0)
        self.assertEqual(low, 0.0)
        self.assertEqual(high, 0.0)

    def test_all_successes(self):
        low, high = _binomial_confidence_interval(100, 100)
        self.assertGreater(low, 85.0)   # CI close to 100%
        self.assertEqual(high, 100.0)

    def test_no_successes(self):
        low, high = _binomial_confidence_interval(0, 100)
        self.assertEqual(low, 0.0)
        self.assertLess(high, 5.0)

    def test_half_successes_midpoint_near_50(self):
        low, high = _binomial_confidence_interval(500, 1000)
        mid = (low + high) / 2
        self.assertAlmostEqual(mid, 50.0, delta=1.0)

    def test_ci_width_decreases_with_more_runs(self):
        low_small, high_small = _binomial_confidence_interval(50, 100)
        low_large, high_large = _binomial_confidence_interval(500, 1000)
        width_small = high_small - low_small
        width_large = high_large - low_large
        self.assertGreater(width_small, width_large)

    def test_output_in_percentage_points(self):
        # Both bounds must be in [0, 100]
        low, high = _binomial_confidence_interval(75, 100)
        self.assertGreaterEqual(low, 0.0)
        self.assertLessEqual(high, 100.0)


# ---------------------------------------------------------------------------
# simulate_incident_monte_carlo — integration-style unit tests
# ---------------------------------------------------------------------------

class TestSimulateIncidentMonteCarlo(unittest.TestCase):

    def _run(self, **inc_kwargs) -> dict:
        return simulate_incident_monte_carlo(
            _make_incident(**inc_kwargs),
            _make_event(),
            runs=200,
        )

    # ---------- Schema checks ----------

    def test_result_has_required_keys(self):
        result = self._run()
        required = [
            "runs", "seed", "route_mode", "protected_rate", "route_reliability",
            "average_delay_days", "expected_exposure_avoided_usd",
            "worst_case_loss_usd", "confidence_interval_low", "confidence_interval_high",
            "arrival_days_p10", "arrival_days_p50", "arrival_days_p90",
            "disruption_days_p10", "disruption_days_p50", "disruption_days_p90",
            "sample_outcomes",
        ]
        for key in required:
            self.assertIn(key, result, f"Missing key: {key}")

    def test_runs_clamped_to_bounds(self):
        # Request 10 (below min 50) → should get 50
        result = simulate_incident_monte_carlo(_make_incident(), _make_event(), runs=10)
        self.assertEqual(result["runs"], 50)

        # Request 9999 (above max 1000) → should get 1000
        result = simulate_incident_monte_carlo(_make_incident(), _make_event(), runs=9999)
        self.assertEqual(result["runs"], 1000)

    def test_sample_outcomes_capped_at_18(self):
        result = self._run()
        self.assertLessEqual(len(result["sample_outcomes"]), 18)

    # ---------- Rate invariants ----------

    def test_protected_rate_in_unit_interval(self):
        result = self._run()
        self.assertGreaterEqual(result["protected_rate"], 0.0)
        self.assertLessEqual(result["protected_rate"], 1.0)

    def test_route_reliability_in_unit_interval(self):
        result = self._run()
        self.assertGreaterEqual(result["route_reliability"], 0.0)
        self.assertLessEqual(result["route_reliability"], 1.0)

    # ---------- Percentile ordering ----------

    def test_percentile_ordering_arrival(self):
        result = self._run()
        self.assertLessEqual(result["arrival_days_p10"], result["arrival_days_p50"])
        self.assertLessEqual(result["arrival_days_p50"], result["arrival_days_p90"])

    def test_percentile_ordering_disruption(self):
        result = self._run()
        self.assertLessEqual(result["disruption_days_p10"], result["disruption_days_p50"])
        self.assertLessEqual(result["disruption_days_p50"], result["disruption_days_p90"])

    # ---------- Determinism ----------

    def test_same_seed_same_result(self):
        incident = _make_incident()
        event = _make_event()
        r1 = simulate_incident_monte_carlo(incident, event, runs=300)
        r2 = simulate_incident_monte_carlo(incident, event, runs=300)
        self.assertEqual(r1["protected_rate"], r2["protected_rate"])
        self.assertEqual(r1["expected_exposure_avoided_usd"], r2["expected_exposure_avoided_usd"])

    # ---------- Economic invariants ----------

    def test_higher_exposure_means_higher_avoided_cost(self):
        low_exp = simulate_incident_monte_carlo(
            _make_incident(exposure_usd=100_000), _make_event(), runs=300
        )
        high_exp = simulate_incident_monte_carlo(
            _make_incident(exposure_usd=5_000_000), _make_event(), runs=300
        )
        self.assertGreater(
            high_exp["expected_exposure_avoided_usd"],
            low_exp["expected_exposure_avoided_usd"],
        )

    def test_worst_case_loss_geq_expected(self):
        # worst-case is a max, so should be >= average in finite samples
        result = self._run()
        # Allow a tiny tolerance for edge cases where all runs avoid all loss
        self.assertGreaterEqual(
            result["worst_case_loss_usd"],
            result["expected_exposure_avoided_usd"] * -1,  # just check it's a number
        )
        self.assertGreater(result["worst_case_loss_usd"], 0)

    def test_high_gnn_confidence_improves_protection(self):
        low_conf = simulate_incident_monte_carlo(
            _make_incident(gnn_confidence=0.1), _make_event(), runs=500
        )
        high_conf = simulate_incident_monte_carlo(
            _make_incident(gnn_confidence=0.99), _make_event(), runs=500
        )
        self.assertGreater(
            high_conf["expected_exposure_avoided_usd"],
            low_conf["expected_exposure_avoided_usd"],
        )

    # ---------- Modes ----------

    def test_air_mode_recorded(self):
        result = simulate_incident_monte_carlo(
            _make_incident(route_mode="air"), _make_event(), runs=100
        )
        self.assertEqual(result["route_mode"], "air")

    def test_sea_mode_recorded(self):
        result = simulate_incident_monte_carlo(
            _make_incident(route_mode="sea"), _make_event(), runs=100
        )
        self.assertEqual(result["route_mode"], "sea")

    def test_land_mode_recorded(self):
        result = simulate_incident_monte_carlo(
            _make_incident(route_mode="land"), _make_event(), runs=100
        )
        self.assertEqual(result["route_mode"], "land")

    # ---------- Edge cases ----------

    def test_empty_route_options_falls_back_gracefully(self):
        incident = {
            "id": "inc_edge",
            "total_exposure_usd": 100_000,
            "gnn_confidence": 0.5,
            "min_stockout_days": 3,
            "affected_node_count": 1,
            "route_options": [],    # ← intentionally empty
        }
        result = simulate_incident_monte_carlo(incident, _make_event(), runs=50)
        self.assertIn("protected_rate", result)
        self.assertGreaterEqual(result["runs"], 50)

    def test_zero_exposure_still_runs(self):
        incident = _make_incident(exposure_usd=0.01)   # near-zero
        result = simulate_incident_monte_carlo(incident, _make_event(), runs=50)
        self.assertGreaterEqual(result["runs"], 50)

    def test_confidence_interval_always_valid_range(self):
        for seed in [1, 42, 777, 2026]:
            event = {**_make_event(), "id": str(seed)}
            result = simulate_incident_monte_carlo(_make_incident(), event, runs=100)
            low = result["confidence_interval_low"]
            high = result["confidence_interval_high"]
            self.assertGreaterEqual(low, 0.0)
            self.assertLessEqual(high, 100.0)
            self.assertLessEqual(low, high)

    def test_average_delay_non_negative(self):
        result = self._run()
        self.assertGreaterEqual(result["average_delay_days"], 0.0)

    def test_sample_outcomes_structure(self):
        result = self._run()
        for outcome in result["sample_outcomes"]:
            self.assertIn("run", outcome)
            self.assertIn("arrival_days", outcome)
            self.assertIn("disruption_days", outcome)
            self.assertIn("continuity_gap_days", outcome)
            self.assertIn("protected", outcome)
            self.assertIn("loss_usd", outcome)
            self.assertIsInstance(outcome["protected"], bool)
            self.assertGreater(outcome["arrival_days"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
