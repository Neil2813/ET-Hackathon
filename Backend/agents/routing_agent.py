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
    workflow_id: str | None = None,
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

    # Compute CO2 footprint deltas
    from services.co2_optimizer import compute_co2_comparison
    route_options_enriched = compute_co2_comparison(decision["route_options"])

    # Persist via SQLAlchemy ORM
    for option in route_options_enriched:
        try:
            from db.orm_models import save_co2_route_event
            co2 = option.get("co2_data", {})
            save_co2_route_event(
                workflow_id=workflow_id,
                mode=option.get("mode", "sea"),
                distance_km=float(option.get("distance_km", 0.0)),
                co2_tons=float(co2.get("co2_emissions_metric_tons", 0.0)),
                carbon_cost=float(co2.get("carbon_cost_usd", 0.0)),
                esg_score=float(co2.get("esg_score", 100.0))
            )
        except Exception:
            pass

    return {
        "route_comparison": route_options_enriched,
        "currency_risk_index": await compute_currency_risk_index(origin_country_code, dest_country_code),
        "recommended_mode": recommended_mode,
        "next_best_mode": decision.get("next_best_mode", ""),
        "delivery_answer": decision.get("delivery_answer", ""),
        "next_best_route_answer": decision.get("next_best_route_answer", ""),
        "cost_answer": decision.get("cost_answer", ""),
        "customer_impact_answer": decision.get("customer_impact_answer", ""),
        "decision_summary": decision.get("decision_summary", {}),
    }
