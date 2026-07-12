from __future__ import annotations

import unittest
from services.scenario_modeller import simulate_macro_scenario


class TestScenarioModeller(unittest.TestCase):
    def test_hormuz_closure_simulation(self) -> None:
        # Run a Strait of Hormuz 40% closure simulation for 30 days
        result = simulate_macro_scenario(
            scenario_type="hormuz_closure",
            loss_pct=40.0,
            duration_days=30,
            spr_drawdown_active=True,
        )

        self.assertEqual(result["scenario_type"], "hormuz_closure")
        self.assertIn("Strait of Hormuz", result["scenario_label"])
        self.assertEqual(result["loss_pct"], 40.0)
        self.assertEqual(result["duration_days"], 30)
        self.assertTrue(result["spr_drawdown_active"])

        # Check assumptions
        self.assertEqual(result["assumptions"]["india_crude_consumption_mbd"], 5.1)
        self.assertEqual(result["assumptions"]["crude_import_dependency_pct"], 88.0)

        # Check summary metrics
        summary = result["summary"]
        self.assertGreater(summary["gross_import_shock_mbd"], 0.7)
        self.assertLess(summary["gross_import_shock_mbd"], 0.8)
        self.assertGreater(summary["average_brent_price_usd"], 80.0)
        self.assertLess(summary["average_gdp_growth_impact_pct"], 0.0)

        # Check daily timeline length
        self.assertEqual(len(result["daily_timeline"]), 30)

        # First day validation
        first_day = result["daily_timeline"][0]
        self.assertEqual(first_day["day"], 1)
        self.assertGreater(first_day["brent_price_usd"], 80.0)
        self.assertGreaterEqual(first_day["refinery_run_rate_pct"], 80.0)
        self.assertLessEqual(first_day["refinery_run_rate_pct"], 100.0)

    def test_no_spr_mitigation_results_in_higher_stress(self) -> None:
        # Scenario with SPR drawdown active
        with_spr = simulate_macro_scenario(
            scenario_type="hormuz_closure",
            loss_pct=40.0,
            duration_days=30,
            spr_drawdown_active=True,
        )

        # Scenario without SPR drawdown active
        no_spr = simulate_macro_scenario(
            scenario_type="hormuz_closure",
            loss_pct=40.0,
            duration_days=30,
            spr_drawdown_active=False,
        )

        # Average refinery run rate should be lower without SPR drawdown
        self.assertLess(
            no_spr["summary"]["average_refinery_run_rate_pct"],
            with_spr["summary"]["average_refinery_run_rate_pct"],
        )

        # Average power sector stress should be higher without SPR drawdown
        self.assertGreater(
            no_spr["summary"]["average_power_sector_stress_pct"],
            with_spr["summary"]["average_power_sector_stress_pct"],
        )

        # Total unmet demand should be higher without SPR drawdown
        self.assertGreater(
            no_spr["summary"]["total_unmet_demand_mmbbl"],
            with_spr["summary"]["total_unmet_demand_mmbbl"],
        )


if __name__ == "__main__":
    unittest.main()
