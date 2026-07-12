"""
Unit tests for Linear Programming crude blend optimizer and routing comparison engines.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from services.energy_resilience import (
    optimize_crude_blend,
    build_all_blend_recipes,
    build_route_comparison,
)


class TestEnergyResilienceServices(unittest.TestCase):

    def test_optimize_crude_blend_success(self):
        # Test optimize_crude_blend for Jamnagar with iranian_light blocked
        res = optimize_crude_blend(refinery_id="jamnagar", blocked_grade="iranian_light")
        self.assertIn(res["status"], ["optimal", "infeasible"])
        if res["status"] == "optimal":
            self.assertTrue(res["meets_spec"])
            self.assertEqual(res["solver"], "scipy HiGHS LP")
            # Proportions must sum to 1.0
            total_fraction = sum(r["fraction"] for r in res["recipe"])
            self.assertAlmostEqual(total_fraction, 1.0, places=3)
            # Each fraction must respect bounds (typically max 80% if relaxed, or 60%)
            for item in res["recipe"]:
                self.assertLessEqual(item["fraction"], 0.81)
                self.assertGreaterEqual(item["fraction"], 0.0)

    def test_optimize_crude_blend_no_alternatives(self):
        # Mock CRUDE_PROFILES to have only 1 non-blocked crude
        mock_crudes = [
            {"id": "c1", "name": "Crude 1", "daily_available_mbd": 0.5, "blocked": True},
            {"id": "c2", "name": "Crude 2", "daily_available_mbd": 0.5, "blocked": False},
        ]
        with patch("services.energy_resilience.CRUDE_PROFILES", mock_crudes):
            res = optimize_crude_blend(refinery_id="jamnagar", blocked_grade="c1")
            self.assertEqual(res["status"], "no_alternatives")
            self.assertIn("cannot build a blend", res["message"])

    def test_build_all_blend_recipes(self):
        res = build_all_blend_recipes(blocked_grade="iranian_light")
        self.assertEqual(res["refineries_analysed"], 4)  # Jamnagar, Paradip, Vadinar, and other
        self.assertIn("feasible_count", res)
        self.assertIn("infeasible_count", res)
        self.assertIn("blend_recipes", res)

    @patch("routing.sea.crude_tanker_route")
    def test_build_route_comparison_low_risk(self, mock_route):
        # Setup mock route results for Suez and Cape VLCC/Suezmax routes
        mock_route.side_effect = lambda lat1, lon1, lat2, lon2, tanker_class, force_cape, chokepoint: {
            "distance_km": 4000.0 if not force_cape else 12000.0,
            "transit_days": 10.0 if not force_cape else 30.0,
            "risk_score": 0.15 if not force_cape else 0.05,
            "tanker_class": tanker_class,
            "force_cape": force_cape,
        }

        # Compare at low corridor risk
        res = build_route_comparison(corridor_risk_score=0.20)
        self.assertEqual(res["recommendation"], "suez")
        self.assertIn("Suez Canal is viable", res["recommendation_text"])
        self.assertGreater(res["cost_delta_usd"], 0)  # Cape should be more expensive
        self.assertGreater(res["time_delta_days"], 0)

    @patch("routing.sea.crude_tanker_route")
    def test_build_route_comparison_critical_risk(self, mock_route):
        mock_route.side_effect = lambda lat1, lon1, lat2, lon2, tanker_class, force_cape, chokepoint: {
            "distance_km": 4000.0 if not force_cape else 12000.0,
            "transit_days": 10.0 if not force_cape else 30.0,
            "risk_score": 0.85 if not force_cape else 0.05,
            "tanker_class": tanker_class,
            "force_cape": force_cape,
        }

        # Compare at critical corridor risk
        res = build_route_comparison(corridor_risk_score=0.80)
        self.assertEqual(res["recommendation"], "cape_strongly_recommended")
        self.assertIn("Red Sea threat is CRITICAL", res["recommendation_text"])
        self.assertLessEqual(res["breakeven_risk"], 1.0)
        self.assertGreaterEqual(res["breakeven_risk"], 0.0)
