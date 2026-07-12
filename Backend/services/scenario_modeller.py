from __future__ import annotations

import math
import urllib.request
import json
from datetime import datetime, timezone
from typing import Any
from agents.spr_optimization_agent import optimize_spr_drawdown, SPRInputs


def _fetch_straits_live_oil_history() -> list[dict[str, Any]]:
    """
    Fetch live daily/hourly Brent crude price history from straits.live
    """
    url = "https://straits.live/api/v1/oil"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Praecantator-Monitor/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return data.get("points") or []
    except Exception:
        return []


def simulate_macro_scenario(
    scenario_type: str,  # "hormuz_closure", "red_sea_suspension", "opec_cut", "double_choke", "custom"
    loss_pct: float,
    duration_days: int,
    spr_drawdown_active: bool = True,
    baseline_brent: float = 76.0,
    country: str = "India",
) -> dict[str, Any]:
    """
    Simulates the macroeconomic and operational impacts of a crude oil supply shock.
    Supports India, Japan, and South Korea, and matches simulated results
    against actual live crisis prices from straits.live/api/v1/oil.
    """
    # 1. Parameterize Country profiles (Import-Dependent Economies)
    profiles = {
        "India": {
            "gdp_nominal_usd_billion": 3550.0,
            "consumption_mbd": 5.1,
            "import_dependency_pct": 88.0,
            "import_volume_mbd": 4.49,
            "hormuz_import_share_pct": 42.5,
            "red_sea_import_share_pct": 25.0,
            "refinery_baseline_capacity_mbd": 4.7,
            "spr_total_capacity_mmbbl": 39.0,
            "spr_cover_days": 9.5,
            "refinery_operational_floor_pct": 86.0,
            "currency_symbol": "₹",
            "price_elasticity": 0.45,  # fuel spike per $1 Brent spike
            "gdp_price_impact": 0.15,  # drop per $10 Brent spike
            "gdp_refinery_impact": 0.12, # drop per 10% run rate drop
        },
        "Japan": {
            "gdp_nominal_usd_billion": 4210.0,
            "consumption_mbd": 3.4,
            "import_dependency_pct": 99.7,
            "import_volume_mbd": 3.39,
            "hormuz_import_share_pct": 90.0,
            "red_sea_import_share_pct": 5.0,
            "refinery_baseline_capacity_mbd": 3.2,
            "spr_total_capacity_mmbbl": 305.0,
            "spr_cover_days": 90.0,
            "refinery_operational_floor_pct": 80.0,
            "currency_symbol": "¥",
            "price_elasticity": 1.55,
            "gdp_price_impact": 0.22,
            "gdp_refinery_impact": 0.18,
        },
        "South Korea": {
            "gdp_nominal_usd_billion": 1710.0,
            "consumption_mbd": 2.6,
            "import_dependency_pct": 100.0,
            "import_volume_mbd": 2.6,
            "hormuz_import_share_pct": 72.0,
            "red_sea_import_share_pct": 10.0,
            "refinery_baseline_capacity_mbd": 2.5,
            "spr_total_capacity_mmbbl": 234.0,
            "spr_cover_days": 90.0,
            "refinery_operational_floor_pct": 82.0,
            "currency_symbol": "₩",
            "price_elasticity": 12.5,
            "gdp_price_impact": 0.25,
            "gdp_refinery_impact": 0.15,
        }
    }

    country_profile = profiles.get(country, profiles["India"])

    assumptions = {
        "country": country,
        "gdp_nominal_usd_billion": country_profile["gdp_nominal_usd_billion"],
        "consumption_mbd": country_profile["consumption_mbd"],
        "crude_import_dependency_pct": country_profile["import_dependency_pct"],
        "import_volume_mbd": country_profile["import_volume_mbd"],
        "hormuz_import_share_pct": country_profile["hormuz_import_share_pct"],
        "red_sea_import_share_pct": country_profile["red_sea_import_share_pct"],
        "refinery_baseline_capacity_mbd": country_profile["refinery_baseline_capacity_mbd"],
        "spr_total_capacity_mmbbl": country_profile["spr_total_capacity_mmbbl"],
        "spr_cover_days": country_profile["spr_cover_days"],
        "refinery_operational_floor_pct": country_profile["refinery_operational_floor_pct"],
        "crude_price_elasticity_coefficient": country_profile["price_elasticity"],
        "gdp_growth_impact_per_10usd_price_spike_pct": country_profile["gdp_price_impact"],
        "gdp_growth_impact_per_10pct_refinery_drop_pct": country_profile["gdp_refinery_impact"],
    }

    # Fetch live/actual crisis prices from straits.live for backtesting
    oil_points = _fetch_straits_live_oil_history()
    actual_prices_by_day: dict[int, float] = {}
    
    # Pre-calculated static fallback for stable demo in offline/failure mode
    static_fallback = [71.60, 71.51, 72.13, 72.13, 71.58, 75.66, 80.12, 75.79, 76.00, 76.01, 76.01]

    if oil_points:
        by_date: dict[str, list[float]] = {}
        for pt in oil_points:
            iso_date = pt.get("iso", "").split("T")[0]
            if iso_date and "brent" in pt:
                by_date.setdefault(iso_date, []).append(float(pt["brent"]))
        
        sorted_dates = sorted(by_date.keys())
        for idx, d in enumerate(sorted_dates):
            avg_price = sum(by_date[d]) / len(by_date[d])
            actual_prices_by_day[idx + 1] = round(avg_price, 2)
    else:
        for idx, val in enumerate(static_fallback):
            actual_prices_by_day[idx + 1] = val

    # 2. Compute Shock parameters & Brent Risk Premium
    import_volume_mbd = assumptions["import_volume_mbd"]
    if scenario_type == "hormuz_closure":
        affected_volume = import_volume_mbd * (assumptions["hormuz_import_share_pct"] / 100.0)
        gross_shock_mbd = affected_volume * (loss_pct / 100.0)
        scenario_label = f"Strait of Hormuz {loss_pct}% closure"
        base_brent_spike = 15.0 + (loss_pct / 100.0) * 25.0
    elif scenario_type == "red_sea_suspension":
        affected_volume = import_volume_mbd * (assumptions["red_sea_import_share_pct"] / 100.0)
        gross_shock_mbd = affected_volume * (loss_pct / 100.0)
        scenario_label = f"Red Sea Shipping {loss_pct}% disruption"
        base_brent_spike = 5.0 + (loss_pct / 100.0) * 12.0
    elif scenario_type == "opec_cut":
        affected_volume = import_volume_mbd * 0.60
        gross_shock_mbd = affected_volume * (loss_pct / 100.0)
        scenario_label = f"OPEC+ Emergency Supply Cut of {loss_pct}%"
        base_brent_spike = 8.0 + (loss_pct / 100.0) * 15.0
    elif scenario_type == "double_choke":
        # Correlated multi-shock: simultaneous Suez + Hormuz disruptions
        hormuz_aff = import_volume_mbd * (assumptions["hormuz_import_share_pct"] / 100.0)
        suez_aff = import_volume_mbd * (assumptions["red_sea_import_share_pct"] / 100.0)
        gross_shock_mbd = (hormuz_aff + suez_aff) * (loss_pct / 100.0)
        scenario_label = f"Double-Choke Suez & Hormuz {loss_pct}% Disruption"
        base_brent_spike = 22.0 + (loss_pct / 100.0) * 35.0
    else:  # custom
        gross_shock_mbd = import_volume_mbd * (loss_pct / 100.0)
        scenario_label = f"Custom Disruption ({loss_pct}% import loss)"
        base_brent_spike = (loss_pct / 100.0) * 20.0

    gross_shock_mbd = max(0.0, min(gross_shock_mbd, import_volume_mbd))

    # 3. Strategic Reserve Drawdown simulation
    spr_inputs = {
        "national_consumption_mbd": assumptions["consumption_mbd"],
        "spr_cover_days": assumptions["spr_cover_days"],
        "initial_fill_pct": 1.0,
        "supply_gap_mbd": gross_shock_mbd,
        "refinery_throughput_mbd": assumptions["refinery_baseline_capacity_mbd"],
        "demand_shed_limit_pct": 0.08,
        "planning_horizon_days": duration_days,
        "replenishment_eta_days": duration_days + 15,
    }

    spr_res = optimize_spr_drawdown(spr_inputs)
    spr_schedule = spr_res.get("schedule", [])

    daily_timeline = []
    total_unmet_demand_mmbbl = 0.0
    brent_prices = []
    refinery_run_rates = []
    power_stress_scores = []
    gdp_hits = []

    for idx, day_data in enumerate(spr_schedule):
        day = day_data["day"]
        spr_draw = day_data["spr_draw_mbd"] if spr_drawdown_active else 0.0
        net_gap = max(0.0, gross_shock_mbd - spr_draw)
        
        # Refinery run rate
        refinery_run_rate = (assumptions["refinery_baseline_capacity_mbd"] - net_gap) / assumptions["refinery_baseline_capacity_mbd"]
        refinery_run_rate_pct = round(max(0.0, refinery_run_rate * 100.0), 2)
        refinery_run_rates.append(refinery_run_rate_pct)
        
        # Unmet demand
        unmet_demand = max(0.0, net_gap - (assumptions["consumption_mbd"] * 0.08))
        total_unmet_demand_mmbbl += unmet_demand
        
        # Brent price projection day-by-day
        day_factor = math.sin((day / duration_days) * math.pi) if duration_days > 0 else 0.0
        current_spike = base_brent_spike * (0.8 + 0.3 * day_factor)
        
        # Dampen price spike with SPR release
        if spr_drawdown_active and gross_shock_mbd > 0:
            mitigation_ratio = spr_draw / gross_shock_mbd
            current_spike *= (1.0 - 0.22 * mitigation_ratio)
            
        brent_price = round(baseline_brent + current_spike, 2)
        brent_prices.append(brent_price)
        
        # Local currency fuel increase per litre
        fuel_price_increase = round(current_spike * assumptions["crude_price_elasticity_coefficient"], 2)
        
        # Power stress
        refinery_drop_pct = 100.0 - refinery_run_rate_pct
        power_stress = (refinery_drop_pct * 1.55) + (unmet_demand / assumptions["consumption_mbd"] * 250.0)
        power_stress = round(min(100.0, max(0.0, power_stress)), 2)
        power_stress_scores.append(power_stress)
        
        # GDP drag
        gdp_hit = - ((current_spike / 10.0) * assumptions["gdp_growth_impact_per_10usd_price_spike_pct"]) - ((refinery_drop_pct / 10.0) * assumptions["gdp_growth_impact_per_10pct_refinery_drop_pct"])
        gdp_hit = round(gdp_hit, 3)
        gdp_hits.append(gdp_hit)
        
        # SPR Inventory
        spr_inventory = max(0.0, spr_res["initial_inventory_mmbbl"] - sum(d["spr_draw_mbd"] for d in spr_schedule[:day])) if spr_drawdown_active else spr_res["initial_inventory_mmbbl"]
        
        # Actual Brent price alignment (caps to last known if day > len)
        actual_price = actual_prices_by_day.get(day, list(actual_prices_by_day.values())[-1])

        daily_timeline.append({
            "day": day,
            "gross_import_shock_mbd": round(gross_shock_mbd, 3),
            "spr_draw_mbd": round(spr_draw, 3),
            "net_supply_gap_mbd": round(net_gap, 3),
            "refinery_run_rate_pct": refinery_run_rate_pct,
            "brent_price_usd": brent_price,
            "actual_brent_price_usd": actual_price,
            "fuel_price_increase_local": fuel_price_increase,
            "power_sector_stress_pct": power_stress,
            "gdp_growth_impact_pct": gdp_hit,
            "spr_inventory_mmbbl": round(spr_inventory, 3),
            "unmet_demand_mbd": round(unmet_demand, 3),
        })

    # Summary
    avg_brent = sum(brent_prices) / len(brent_prices) if brent_prices else baseline_brent
    avg_run_rate = sum(refinery_run_rates) / len(refinery_run_rates) if refinery_run_rates else 100.0
    avg_power_stress = sum(power_stress_scores) / len(power_stress_scores) if power_stress_scores else 0.0
    final_gdp_hit = sum(gdp_hits) / len(gdp_hits) if gdp_hits else 0.0
    peak_fuel_increase = max((d["fuel_price_increase_local"] for d in daily_timeline), default=0.0)

    # Refinery & Power stress levels
    refinery_stress_level = "stable"
    if avg_run_rate < assumptions["refinery_operational_floor_pct"]:
        refinery_stress_level = "critical"
    elif avg_run_rate < 95.0:
        refinery_stress_level = "alert"
        
    power_stress_level = "stable"
    if avg_power_stress > 50.0:
        power_stress_level = "critical"
    elif avg_power_stress > 20.0:
        power_stress_level = "alert"

    # 4. Resilience ROI & Expected Cost Avoided Calculator
    # Base case: run simulation with spr_drawdown_active=False
    base_gdp_hits = []
    for day_data in spr_schedule:
        # no spr draw in base case
        net_gap = gross_shock_mbd
        refinery_run_rate = (assumptions["refinery_baseline_capacity_mbd"] - net_gap) / assumptions["refinery_baseline_capacity_mbd"]
        ref_drop = 100.0 - round(max(0.0, refinery_run_rate * 100.0), 2)
        day_factor = math.sin((day_data["day"] / duration_days) * math.pi) if duration_days > 0 else 0.0
        curr_spike = base_brent_spike * (0.8 + 0.3 * day_factor)
        g_hit = - ((curr_spike / 10.0) * assumptions["gdp_growth_impact_per_10usd_price_spike_pct"]) - ((ref_drop / 10.0) * assumptions["gdp_growth_impact_per_10pct_refinery_drop_pct"])
        base_gdp_hits.append(g_hit)
    
    base_gdp_hit = sum(base_gdp_hits) / len(base_gdp_hits) if base_gdp_hits else 0.0
    gdp_nominal_usd = assumptions["gdp_nominal_usd_billion"] * 1e9
    
    # GDP Loss is hit pct * nominal GDP.
    # Convert growth drop (e.g. -0.5% GDP hit -> 0.005)
    loss_with_spr = abs(final_gdp_hit / 100.0) * gdp_nominal_usd
    loss_without_spr = abs(base_gdp_hit / 100.0) * gdp_nominal_usd
    expected_cost_avoided_usd = max(0.0, loss_without_spr - loss_with_spr)
    
    platform_annual_cost = 120000.0  # $120k operation/deployment cost
    resilience_roi = ((expected_cost_avoided_usd - platform_annual_cost) / platform_annual_cost) * 100.0 if expected_cost_avoided_usd > 0 else 0.0

    # 5. Sensitivity & Tornado Analysis
    # Perturb each key coefficient by +/- 20%
    sensitivity_params = {
        "crude_price_elasticity_coefficient": assumptions["crude_price_elasticity_coefficient"],
        "gdp_growth_impact_per_10usd_price_spike_pct": assumptions["gdp_growth_impact_per_10usd_price_spike_pct"],
        "gdp_growth_impact_per_10pct_refinery_drop_pct": assumptions["gdp_growth_impact_per_10pct_refinery_drop_pct"],
    }
    
    sensitivity_results = []
    for param_name, base_val in sensitivity_params.items():
        # High perturbation (+20%)
        high_val = base_val * 1.2
        high_gdp_hits = []
        for day_data in spr_schedule:
            spr_draw = day_data["spr_draw_mbd"] if spr_drawdown_active else 0.0
            net_gap = max(0.0, gross_shock_mbd - spr_draw)
            ref_drop = 100.0 - round(max(0.0, ((assumptions["refinery_baseline_capacity_mbd"] - net_gap) / assumptions["refinery_baseline_capacity_mbd"]) * 100.0), 2)
            day_factor = math.sin((day_data["day"] / duration_days) * math.pi) if duration_days > 0 else 0.0
            curr_spike = base_brent_spike * (0.8 + 0.3 * day_factor)
            if spr_drawdown_active and gross_shock_mbd > 0:
                curr_spike *= (1.0 - 0.22 * (spr_draw / gross_shock_mbd))
            
            p_coef = high_val if param_name == "gdp_growth_impact_per_10usd_price_spike_pct" else assumptions["gdp_growth_impact_per_10usd_price_spike_pct"]
            r_coef = high_val if param_name == "gdp_growth_impact_per_10pct_refinery_drop_pct" else assumptions["gdp_growth_impact_per_10pct_refinery_drop_pct"]
            
            g_hit = - ((curr_spike / 10.0) * p_coef) - ((ref_drop / 10.0) * r_coef)
            high_gdp_hits.append(g_hit)
        high_gdp_hit = sum(high_gdp_hits) / len(high_gdp_hits) if high_gdp_hits else 0.0

        # Low perturbation (-20%)
        low_val = base_val * 0.8
        low_gdp_hits = []
        for day_data in spr_schedule:
            spr_draw = day_data["spr_draw_mbd"] if spr_drawdown_active else 0.0
            net_gap = max(0.0, gross_shock_mbd - spr_draw)
            ref_drop = 100.0 - round(max(0.0, ((assumptions["refinery_baseline_capacity_mbd"] - net_gap) / assumptions["refinery_baseline_capacity_mbd"]) * 100.0), 2)
            day_factor = math.sin((day_data["day"] / duration_days) * math.pi) if duration_days > 0 else 0.0
            curr_spike = base_brent_spike * (0.8 + 0.3 * day_factor)
            if spr_drawdown_active and gross_shock_mbd > 0:
                curr_spike *= (1.0 - 0.22 * (spr_draw / gross_shock_mbd))
            
            p_coef = low_val if param_name == "gdp_growth_impact_per_10usd_price_spike_pct" else assumptions["gdp_growth_impact_per_10usd_price_spike_pct"]
            r_coef = low_val if param_name == "gdp_growth_impact_per_10pct_refinery_drop_pct" else assumptions["gdp_growth_impact_per_10pct_refinery_drop_pct"]
            
            g_hit = - ((curr_spike / 10.0) * p_coef) - ((ref_drop / 10.0) * r_coef)
            low_gdp_hits.append(g_hit)
        low_gdp_hit = sum(low_gdp_hits) / len(low_gdp_hits) if low_gdp_hits else 0.0

        sensitivity_results.append({
            "parameter": param_name,
            "friendly_name": param_name.replace("_", " ").title(),
            "low_val_20pct": round(low_val, 3),
            "high_val_20pct": round(high_val, 3),
            "gdp_drag_at_low": round(low_gdp_hit, 3),
            "gdp_drag_at_high": round(high_gdp_hit, 3),
            "total_swing_pct": round(abs(high_gdp_hit - low_gdp_hit), 3),
        })

    # Sort parameters by sensitivity swing
    sensitivity_results.sort(key=lambda x: x["total_swing_pct"], reverse=True)

    return {
        "scenario_type": scenario_type,
        "scenario_label": scenario_label,
        "loss_pct": loss_pct,
        "duration_days": duration_days,
        "spr_drawdown_active": spr_drawdown_active,
        "assumptions": assumptions,
        "currency_symbol": country_profile["currency_symbol"],
        "summary": {
            "gross_import_shock_mbd": round(gross_shock_mbd, 3),
            "average_refinery_run_rate_pct": round(avg_run_rate, 2),
            "refinery_stress_level": refinery_stress_level,
            "average_brent_price_usd": round(avg_brent, 2),
            "peak_fuel_price_increase_local": round(peak_fuel_increase, 2),
            "average_power_sector_stress_pct": round(avg_power_stress, 2),
            "power_stress_level": power_stress_level,
            "average_gdp_growth_impact_pct": round(final_gdp_hit, 3),
            "total_unmet_demand_mmbbl": round(total_unmet_demand_mmbbl, 3),
            "mitigation_percentage": round((gross_shock_mbd - (total_unmet_demand_mmbbl / duration_days)) / gross_shock_mbd * 100.0, 1) if gross_shock_mbd > 0 else 100.0,
            
            # ROI Outputs
            "expected_cost_avoided_usd": round(expected_cost_avoided_usd, 2),
            "resilience_roi_pct": round(resilience_roi, 1),
            "gdp_loss_with_spr_usd": round(loss_with_spr, 2),
            "gdp_loss_without_spr_usd": round(loss_without_spr, 2),
        },
        "sensitivity_analysis": sensitivity_results,
        "daily_timeline": daily_timeline,
    }
