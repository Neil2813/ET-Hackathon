from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# IMO emission factors (grams of CO2 per metric ton of cargo per km traveled)
# Tanker VLCC: ~3.2 g/ton-km
# Tanker Suezmax: ~4.5 g/ton-km
EMISSION_FACTORS = {
    "tanker_vlcc": 3.2,
    "tanker_suezmax": 4.5,
    "sea": 5.1,
    "air": 500.0,
    "land": 62.0,
    "rail": 18.0,
    "hybrid": 40.0
}

# Standard cargo weights (metric tons)
CARGO_WEIGHTS = {
    "tanker_vlcc": 280000.0,
    "tanker_suezmax": 140000.0,
    "sea": 20000.0,
    "air": 100.0,
    "land": 20.0,
    "rail": 60.0,
    "hybrid": 20000.0
}

# Carbon pricing (USD per metric ton of CO2)
CARBON_PRICE_PER_TON = 85.00


def compute_route_co2(mode: str, distance_km: float) -> dict:
    """
    Compute estimated CO2 emissions, carbon offset cost, and ESG rating score.
    """
    mode_key = str(mode).strip().lower()
    factor = EMISSION_FACTORS.get(mode_key, 3.2)
    cargo_weight = CARGO_WEIGHTS.get(mode_key, 10000.0)

    # Grams to metric tons conversion: grams / 1,000,000
    co2_grams = distance_km * cargo_weight * factor
    co2_metric_tons = co2_grams / 1000000.0

    carbon_cost_usd = co2_metric_tons * CARBON_PRICE_PER_TON

    # ESG Score ranges from 10 to 100, penalizing long distances and heavy emissions
    penalty = (distance_km * 0.003) + (co2_metric_tons * 0.001)
    esg_score = max(10.0, min(100.0, 100.0 - penalty))

    return {
        "co2_emissions_metric_tons": round(co2_metric_tons, 1),
        "carbon_cost_usd": round(carbon_cost_usd, 2),
        "esg_score": round(esg_score, 1),
        "distance_km": round(distance_km, 1)
    }


def compute_co2_comparison(routes: list[dict]) -> list[dict]:
    """
    Given a list of routes, enrich each route with its CO2 emissions details
    and calculate delta relative to the first (usually baseline/direct) route.
    """
    if not routes:
        return []

    # Compute base emissions
    enriched = []
    for r in routes:
        mode = r.get("mode", "sea")
        dist = float(r.get("distance_km", 0.0))
        co2_data = compute_route_co2(mode, dist)
        enriched.append({**r, "co2_data": co2_data})

    # Add relative deltas
    base_co2 = enriched[0]["co2_data"]["co2_emissions_metric_tons"]
    base_cost = enriched[0]["co2_data"]["carbon_cost_usd"]

    for r in enriched:
        r_co2 = r["co2_data"]["co2_emissions_metric_tons"]
        r_cost = r["co2_data"]["carbon_cost_usd"]
        r["co2_data"].update({
            "co2_delta_tons": round(r_co2 - base_co2, 1),
            "carbon_cost_delta_usd": round(r_cost - base_cost, 2)
        })

    return enriched
