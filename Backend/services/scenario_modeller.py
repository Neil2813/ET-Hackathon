from __future__ import annotations

import math
from typing import Any
from agents.spr_optimization_agent import optimize_spr_drawdown, SPRInputs


def simulate_macro_scenario(
    scenario_type: str,  # "hormuz_closure", "red_sea_suspension", "opec_cut", "custom"
    loss_pct: float,
    duration_days: int,
    spr_drawdown_active: bool = True,
    baseline_brent: float = 80.0,
) -> dict[str, Any]:
    """
    Simulates the macroeconomic and operational impacts of a crude oil supply shock.
    
    Assumptions & Equations:
    ------------------------
    1. India's daily crude consumption is 5.1 MBD.
    2. Crude import dependency is 88%, resulting in an import volume of 4.49 MBD.
    3. Strait of Hormuz accounts for 42.5% of imports (1.91 MBD).
    4. Red Sea shipping accounts for 25.0% of imports (1.12 MBD).
    5. Baseline refinery capacity is 4.7 MBD.
    6. India's Strategic Petroleum Reserve (SPR) cover is 9.5 days of imports (~39 MMBbl).
    7. Refinery operational floor is 86%. If run rate falls below this, it causes severe industrial disruptions.
    8. Crude price elasticity: Geopolitical risk and physical supply gaps increase Brent.
       Hormuz closures add a dynamic risk premium: Brent rises by $15 + $25 * (loss_pct / 100).
    9. Domestic retail fuel price (INR/litre) changes by ₹0.45 for every $1/bbl spike in Brent.
    10. Power sector stress increases with fuel prices and net crude supply gaps (since diesel/gas are backup generation sources).
    11. GDP growth impact: India's annual GDP growth drops by 0.15% per $10/bbl Brent spike and 0.12% per 10% refinery run-rate reduction.
    """
    # Define stated and testable assumptions
    assumptions = {
        "india_crude_consumption_mbd": 5.1,
        "crude_import_dependency_pct": 88.0,
        "import_volume_mbd": 4.49,
        "hormuz_import_share_pct": 42.5,
        "red_sea_import_share_pct": 25.0,
        "refinery_baseline_capacity_mbd": 4.7,
        "spr_total_capacity_mmbbl": 39.0,
        "refinery_operational_floor_pct": 86.0,
        "crude_price_elasticity_coefficient": 0.45,
        "gdp_growth_impact_per_10usd_price_spike_pct": 0.15,
        "gdp_growth_impact_per_10pct_refinery_drop_pct": 0.12,
    }

    # 1. Calculate Gross Import Shock (MBD)
    import_volume_mbd = assumptions["import_volume_mbd"]
    if scenario_type == "hormuz_closure":
        affected_volume = import_volume_mbd * (assumptions["hormuz_import_share_pct"] / 100.0)
        gross_shock_mbd = affected_volume * (loss_pct / 100.0)
        scenario_label = f"Strait of Hormuz {loss_pct}% throughput loss"
        base_brent_spike = 15.0 + (loss_pct / 100.0) * 25.0
    elif scenario_type == "red_sea_suspension":
        affected_volume = import_volume_mbd * (assumptions["red_sea_import_share_pct"] / 100.0)
        gross_shock_mbd = affected_volume * (loss_pct / 100.0)
        scenario_label = f"Red Sea Shipping {loss_pct}% disruption"
        base_brent_spike = 5.0 + (loss_pct / 100.0) * 12.0
    elif scenario_type == "opec_cut":
        affected_volume = import_volume_mbd * 0.60  # OPEC+ represents ~60% of India's contracted imports
        gross_shock_mbd = affected_volume * (loss_pct / 100.0)
        scenario_label = f"OPEC+ Emergency Supply Cut of {loss_pct}%"
        base_brent_spike = 8.0 + (loss_pct / 100.0) * 15.0
    else:  # custom
        gross_shock_mbd = import_volume_mbd * (loss_pct / 100.0)
        scenario_label = f"Custom Disruption ({loss_pct}% import loss)"
        base_brent_spike = (loss_pct / 100.0) * 20.0

    gross_shock_mbd = max(0.0, min(gross_shock_mbd, import_volume_mbd))

    # 2. Strategic Reserve Drawdown simulation
    spr_inputs = {
        "national_consumption_mbd": assumptions["india_crude_consumption_mbd"],
        "spr_cover_days": 9.5,
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
        # If SPR drawdown is active, use the draw rate calculated by the SPR agent
        spr_draw = day_data["spr_draw_mbd"] if spr_drawdown_active else 0.0
        
        # Net supply gap remaining after SPR drawdown
        net_gap = max(0.0, gross_shock_mbd - spr_draw)
        
        # Refinery run rate: drop based on the net crude gap
        refinery_run_rate = (assumptions["refinery_baseline_capacity_mbd"] - net_gap) / assumptions["refinery_baseline_capacity_mbd"]
        refinery_run_rate_pct = round(max(0.0, refinery_run_rate * 100.0), 2)
        refinery_run_rates.append(refinery_run_rate_pct)
        
        # Unmet demand is gap minus demand management/shed limit (e.g. 8%)
        unmet_demand = max(0.0, net_gap - (assumptions["india_crude_consumption_mbd"] * 0.08))
        total_unmet_demand_mmbbl += unmet_demand
        
        # Brent price projection day-by-day: rises initially, peaks mid-duration
        day_factor = math.sin((day / duration_days) * math.pi) if duration_days > 0 else 0.0
        current_spike = base_brent_spike * (0.8 + 0.3 * day_factor)
        
        # SPR release dampens global price volatility
        if spr_drawdown_active and gross_shock_mbd > 0:
            mitigation_ratio = spr_draw / gross_shock_mbd
            current_spike *= (1.0 - 0.22 * mitigation_ratio)
            
        brent_price = round(baseline_brent + current_spike, 2)
        brent_prices.append(brent_price)
        
        # Retail price increase in INR/litre
        fuel_price_increase_inr = round(current_spike * assumptions["crude_price_elasticity_coefficient"], 2)
        
        # Power sector stress (diesel/captive backup generation stress)
        refinery_drop_pct = 100.0 - refinery_run_rate_pct
        power_stress = (refinery_drop_pct * 1.55) + (unmet_demand / assumptions["india_crude_consumption_mbd"] * 250.0)
        power_stress = round(min(100.0, max(0.0, power_stress)), 2)
        power_stress_scores.append(power_stress)
        
        # GDP growth drag
        gdp_hit = - ((current_spike / 10.0) * assumptions["gdp_growth_impact_per_10usd_price_spike_pct"]) - ((refinery_drop_pct / 10.0) * assumptions["gdp_growth_impact_per_10pct_refinery_drop_pct"])
        gdp_hit = round(gdp_hit, 3)
        gdp_hits.append(gdp_hit)
        
        # Remaining SPR inventory calculation
        spr_inventory = max(0.0, spr_res["initial_inventory_mmbbl"] - sum(d["spr_draw_mbd"] for d in spr_schedule[:day])) if spr_drawdown_active else spr_res["initial_inventory_mmbbl"]
        
        daily_timeline.append({
            "day": day,
            "gross_import_shock_mbd": round(gross_shock_mbd, 3),
            "spr_draw_mbd": round(spr_draw, 3),
            "net_supply_gap_mbd": round(net_gap, 3),
            "refinery_run_rate_pct": refinery_run_rate_pct,
            "brent_price_usd": brent_price,
            "fuel_price_increase_inr_per_litre": fuel_price_increase_inr,
            "power_sector_stress_pct": power_stress,
            "gdp_growth_impact_pct": gdp_hit,
            "spr_inventory_mmbbl": round(spr_inventory, 3),
            "unmet_demand_mbd": round(unmet_demand, 3),
        })

    # Summarize simulation outcomes
    avg_brent = sum(brent_prices) / len(brent_prices) if brent_prices else baseline_brent
    avg_run_rate = sum(refinery_run_rates) / len(refinery_run_rates) if refinery_run_rates else 100.0
    avg_power_stress = sum(power_stress_scores) / len(power_stress_scores) if power_stress_scores else 0.0
    final_gdp_hit = sum(gdp_hits) / len(gdp_hits) if gdp_hits else 0.0
    peak_fuel_increase = max((d["fuel_price_increase_inr_per_litre"] for d in daily_timeline), default=0.0)

    # Determine stress levels based on thresholds
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

    return {
        "scenario_type": scenario_type,
        "scenario_label": scenario_label,
        "loss_pct": loss_pct,
        "duration_days": duration_days,
        "spr_drawdown_active": spr_drawdown_active,
        "assumptions": assumptions,
        "summary": {
            "gross_import_shock_mbd": round(gross_shock_mbd, 3),
            "average_refinery_run_rate_pct": round(avg_run_rate, 2),
            "refinery_stress_level": refinery_stress_level,
            "average_brent_price_usd": round(avg_brent, 2),
            "peak_fuel_price_increase_inr_per_litre": round(peak_fuel_increase, 2),
            "average_power_sector_stress_pct": round(avg_power_stress, 2),
            "power_stress_level": power_stress_level,
            "average_gdp_growth_impact_pct": round(final_gdp_hit, 3),
            "total_unmet_demand_mmbbl": round(total_unmet_demand_mmbbl, 3),
            "mitigation_percentage": round((gross_shock_mbd - (total_unmet_demand_mmbbl / duration_days)) / gross_shock_mbd * 100.0, 1) if gross_shock_mbd > 0 else 100.0,
        },
        "daily_timeline": daily_timeline,
    }
