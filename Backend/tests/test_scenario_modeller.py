from __future__ import annotations

import unittest
from services.scenario_modeller import simulate_macro_scenario


class TestScenarioModeller(unittest.TestCase):
    def test_hormuz_closure_simulation_india(self) -> None:
        # Run a Strait of Hormuz 40% closure simulation for 30 days for India
        result = simulate_macro_scenario(
            scenario_type="hormuz_closure",
            loss_pct=40.0,
            duration_days=30,
            spr_drawdown_active=True,
            country="India",
        )

        self.assertEqual(result["scenario_type"], "hormuz_closure")
        self.assertIn("Strait of Hormuz", result["scenario_label"])
        self.assertEqual(result["loss_pct"], 40.0)
        self.assertEqual(result["duration_days"], 30)
        self.assertTrue(result["spr_drawdown_active"])

        # Check assumptions
        self.assertEqual(result["assumptions"]["country"], "India")
        self.assertEqual(result["assumptions"]["consumption_mbd"], 5.1)
        self.assertEqual(result["assumptions"]["crude_import_dependency_pct"], 88.0)

        # Check summary metrics
        summary = result["summary"]
        self.assertGreater(summary["gross_import_shock_mbd"], 0.7)
        self.assertLess(summary["gross_import_shock_mbd"], 0.8)
        self.assertGreater(summary["average_brent_price_usd"], 75.0)
        self.assertLess(summary["average_gdp_growth_impact_pct"], 0.0)

        # Check daily timeline length
        self.assertEqual(len(result["daily_timeline"]), 30)

        # First day validation
        first_day = result["daily_timeline"][0]
        self.assertEqual(first_day["day"], 1)
        self.assertGreater(first_day["brent_price_usd"], 75.0)
        self.assertGreaterEqual(first_day["refinery_run_rate_pct"], 80.0)
        self.assertLessEqual(first_day["refinery_run_rate_pct"], 100.0)

    def test_japan_scenario_severe_gdp_impact(self) -> None:
        # Japan is 99.7% import dependent, so a disruption should hit it harder than India
        india_res = simulate_macro_scenario(
            scenario_type="hormuz_closure",
            loss_pct=80.0,
            duration_days=30,
            spr_drawdown_active=True,
            country="India",
        )
        japan_res = simulate_macro_scenario(
            scenario_type="hormuz_closure",
            loss_pct=80.0,
            duration_days=30,
            spr_drawdown_active=True,
            country="Japan",
        )

        # Average GDP hit should be larger (more negative) for Japan due to higher import dependencies and risk sensitivity
        self.assertLess(
            japan_res["summary"]["average_gdp_growth_impact_pct"],
            india_res["summary"]["average_gdp_growth_impact_pct"]
        )

    def test_double_choke_scenario(self) -> None:
        result = simulate_macro_scenario(
            scenario_type="double_choke",
            loss_pct=30.0,
            duration_days=30,
            spr_drawdown_active=True,
            country="India",
        )
        self.assertEqual(result["scenario_type"], "double_choke")
        self.assertIn("Double-Choke", result["scenario_label"])
        # Shock should be combination of Hormuz + Suez
        self.assertGreater(result["summary"]["gross_import_shock_mbd"], 0.8)

    def test_sensitivity_and_roi_calculation(self) -> None:
        result = simulate_macro_scenario(
            scenario_type="hormuz_closure",
            loss_pct=40.0,
            duration_days=30,
            spr_drawdown_active=True,
            country="India",
        )

        # Sensitivity analysis list checks
        self.assertIn("sensitivity_analysis", result)
        self.assertEqual(len(result["sensitivity_analysis"]), 3)
        self.assertIn("friendly_name", result["sensitivity_analysis"][0])
        self.assertIn("total_swing_pct", result["sensitivity_analysis"][0])

        # ROI check
        summary = result["summary"]
        self.assertIn("expected_cost_avoided_usd", summary)
        self.assertIn("resilience_roi_pct", summary)

    def test_no_spr_mitigation_results_in_higher_stress(self) -> None:
        # Scenario with SPR drawdown active
        with_spr = simulate_macro_scenario(
            scenario_type="hormuz_closure",
            loss_pct=40.0,
            duration_days=30,
            spr_drawdown_active=True,
            country="India",
        )

        # Scenario without SPR drawdown active
        no_spr = simulate_macro_scenario(
            scenario_type="hormuz_closure",
            loss_pct=40.0,
            duration_days=30,
            spr_drawdown_active=False,
            country="India",
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
