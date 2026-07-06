from __future__ import annotations

from currency.frankfurter import convert_cost
from currency.risk_index import compute_currency_risk_index
from routing.decision import crude_route_decision
from routing.sea import crude_tanker_route


async def run_routing(
    origin_lat: float,
    origin_lng: float,
    origin_country_code: str,
    origin_label: str,
    dest_lat: float,
    dest_lng: float,
    dest_country_code: str,
    dest_label: str,
    target_currency: str,
    commodity: str = "crude_oil",
) -> dict:
    if abs(origin_lat - dest_lat) < 1e-6 and abs(origin_lng - dest_lng) < 1e-6:
        raise ValueError("Origin and destination cannot be identical")
    if not all(
        isinstance(v, (int, float))
        for v in (origin_lat, origin_lng, dest_lat, dest_lng)
    ):
        raise ValueError("Invalid routing coordinates")

    chokepoint = "Strait of Hormuz" if origin_country_code.upper() in {"SA", "IQ", "AE", "IR", "KW"} else "Red Sea"
    comparison = [
        crude_tanker_route(origin_lat, origin_lng, dest_lat, dest_lng, tanker_class="VLCC", chokepoint=chokepoint),
        crude_tanker_route(origin_lat, origin_lng, dest_lat, dest_lng, tanker_class="Suezmax", chokepoint=chokepoint),
        crude_tanker_route(origin_lat, origin_lng, dest_lat, dest_lng, tanker_class="VLCC", force_cape=True, chokepoint=chokepoint),
    ]
    for mode in comparison:
        mode["cost"] = await convert_cost(mode["cost_usd"], target_currency)
    decision = crude_route_decision(comparison, current_mode="tanker_vlcc")
    recommended_mode = str(decision.get("recommended_mode") or "")
    if not recommended_mode:
        raise ValueError("No valid route modes computed")
    return {
        "route_comparison": decision["route_options"],
        "currency_risk_index": await compute_currency_risk_index(origin_country_code, dest_country_code),
        "recommended_mode": recommended_mode,
        "next_best_mode": decision.get("next_best_mode", ""),
        "delivery_answer": decision.get("delivery_answer", ""),
        "next_best_route_answer": decision.get("next_best_route_answer", ""),
        "cost_answer": decision.get("cost_answer", ""),
        "customer_impact_answer": decision.get("customer_impact_answer", ""),
        "decision_summary": decision.get("decision_summary", {}),
    }
