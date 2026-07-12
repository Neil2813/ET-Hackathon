from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Query

from services.firebase_auth import verify_firebase_or_local_token
from services.firestore_store import add_audit
from services.energy_resilience import (
    build_ais_anomaly_forecast,
    build_compatibility_matches,
    build_energy_resilience_dashboard,
    build_exchange_ledger,
    build_geopolitical_rag,
    build_spr_policy,
    build_all_blend_recipes,
    build_route_comparison,
)
from services.scenario_modeller import simulate_macro_scenario
from routers.schemas import (
    EnergyResilienceSPRRequest,
    CrudeCompatibilityRequest,
    AISForecastResponse,
    GeopoliticalRAGResponse,
    CrudeMatchResponse,
    ExchangeLedgerResponse,
    EnergyResilienceSPRResponse,
    EnergyResilienceDashboardResponse,
    CrudeBlendRecipeResponse,
    RouteComparisonResponse,
    ScenarioSimulationRequest,
    ScenarioSimulationResponse,
)
from routers.helpers import _resolved_request_tenant, _enqueue_celery_task

router = APIRouter(tags=["Energy Resilience"])


def _energy_tenant(user: dict[str, Any]) -> str:
    try:
        return _resolved_request_tenant(user)
    except Exception:
        return str(user.get("sub") or "default").strip() or "default"


@router.get("/api/energy-resilience/dashboard", response_model=EnergyResilienceDashboardResponse)
async def api_energy_resilience_dashboard(user=Depends(verify_firebase_or_local_token)) -> EnergyResilienceDashboardResponse:
    tenant_id = _energy_tenant(user)
    payload = build_energy_resilience_dashboard(tenant_id)
    add_audit("energy_resilience_dashboard", tenant_id)
    return payload


@router.get("/api/energy-resilience/ais", response_model=AISForecastResponse)
async def api_energy_resilience_ais(user=Depends(verify_firebase_or_local_token)) -> AISForecastResponse:
    add_audit("energy_resilience_ais_forecast", user.get("sub", "local"))
    return build_ais_anomaly_forecast()


@router.post("/api/energy-resilience/spr-policy", response_model=EnergyResilienceSPRResponse)
async def api_energy_resilience_spr_policy(
    payload: EnergyResilienceSPRRequest,
    user=Depends(verify_firebase_or_local_token),
) -> EnergyResilienceSPRResponse:
    add_audit("energy_resilience_spr_policy", user.get("sub", "local"))
    return build_spr_policy(payload.model_dump())


@router.post("/api/energy-resilience/crude-compatibility", response_model=CrudeMatchResponse)
async def api_energy_resilience_crude_compatibility(
    payload: CrudeCompatibilityRequest,
    user=Depends(verify_firebase_or_local_token),
) -> CrudeMatchResponse:
    add_audit("energy_resilience_crude_compatibility", f"{user.get('sub', 'local')}:{payload.blocked_grade}")
    return build_compatibility_matches(payload.blocked_grade)


@router.get("/api/energy-resilience/geopolitical-rag", response_model=GeopoliticalRAGResponse)
async def api_energy_resilience_geopolitical_rag(user=Depends(verify_firebase_or_local_token)) -> GeopoliticalRAGResponse:
    add_audit("energy_resilience_geopolitical_rag", user.get("sub", "local"))
    return build_geopolitical_rag()


@router.get("/api/energy-resilience/exchange-ledger", response_model=ExchangeLedgerResponse)
async def api_energy_resilience_exchange_ledger(user=Depends(verify_firebase_or_local_token)) -> ExchangeLedgerResponse:
    tenant_id = _energy_tenant(user)
    add_audit("energy_resilience_exchange_ledger", tenant_id)
    return build_exchange_ledger(tenant_id)


@router.get("/api/energy-resilience/blend-optimizer", response_model=CrudeBlendRecipeResponse)
async def api_blend_optimizer(
    blocked_grade: str = Query(default="iranian_light", description="ID of the blocked crude grade"),
    user=Depends(verify_firebase_or_local_token),
) -> CrudeBlendRecipeResponse:
    """
    LP-optimised multi-crude blend recipes for all refineries when a primary
    grade is disrupted. Uses scipy HiGHS solver to find the optimal mixture
    satisfying each refinery's API gravity, sulfur %, and viscosity spec.
    """
    add_audit("energy_resilience_blend_optimizer", f"{user.get('sub', 'local')}:{blocked_grade}")
    return build_all_blend_recipes(blocked_grade)


@router.get("/api/energy-resilience/route-comparison", response_model=RouteComparisonResponse)
async def api_route_comparison(
    corridor_risk: float = Query(default=0.65, ge=0.0, le=1.0, description="Bab el-Mandeb risk score 0–1"),
    user=Depends(verify_firebase_or_local_token),
) -> RouteComparisonResponse:
    """
    Suez Canal vs Cape of Good Hope routing comparison for Gulf→India crude tankers.
    Returns cost, transit time, war-risk premium, CO2, and a recommendation
    ('suez' | 'cape' | 'cape_strongly_recommended') driven by the live corridor risk score.
    """
    add_audit("energy_resilience_route_comparison", user.get("sub", "local"))
    return build_route_comparison(corridor_risk_score=corridor_risk)


@router.post("/api/energy-resilience/simulate-scenario", response_model=ScenarioSimulationResponse)
async def api_simulate_scenario(
    payload: ScenarioSimulationRequest,
    user=Depends(verify_firebase_or_local_token),
) -> ScenarioSimulationResponse:
    """
    Simulate a crude oil supply disruption scenario and propagate its impacts on
    refinery run rates, Brent oil prices, retail fuel prices, power-sector stress, and GDP growth.
    """
    tenant_id = _energy_tenant(user)
    add_audit("energy_resilience_simulate_scenario", f"{tenant_id}:{payload.scenario_type}")
    return simulate_macro_scenario(
        scenario_type=payload.scenario_type,
        loss_pct=payload.loss_pct,
        duration_days=payload.duration_days,
        spr_drawdown_active=payload.spr_drawdown_active,
        country=payload.country,
    )


@router.post("/api/energy-resilience/policy-briefing")
async def api_energy_resilience_policy_briefing(
    payload: dict,
    user=Depends(verify_firebase_or_local_token),
) -> dict:
    """
    Generate a formatted cabinet briefing summary (markdown) for the Ministry
    of Petroleum or National Security Council using LLM provider.
    """
    from services.llm_provider import complete

    scenario_label = payload.get("scenario_label", "Disruption")
    summary = payload.get("summary") or {}
    assumptions = payload.get("assumptions") or {}
    country = assumptions.get("country", "India")
    currency = payload.get("currency_symbol", "$")

    prompt = (
        f"You are the senior National Security Advisor on Energy Security for {country}.\n"
        f"Generate a formal, highly concise, 1-page executive policy brief for the Prime Minister's Office.\n"
        f"The cabinet needs to make an immediate decision under severe time pressure.\n\n"
        f"--- CRISIS DATA SUMMARY ---\n"
        f"- Event: {scenario_label}\n"
        f"- Import Shock Rate: {summary.get('gross_import_shock_mbd')} MBD\n"
        f"- Refinery Processing Run-Rate: {summary.get('average_refinery_run_rate_pct')}% (Status: {summary.get('refinery_stress_level')})\n"
        f"- Power Sector Stress: {summary.get('average_power_sector_stress_pct')}% (Status: {summary.get('power_stress_level')})\n"
        f"- Average Brent Futures: ${summary.get('average_brent_price_usd')}/bbl\n"
        f"- Retail Fuel Price Spike: {currency}{summary.get('peak_fuel_price_increase_local')}/litre\n"
        f"- GDP Drag Projection: {summary.get('average_gdp_growth_impact_pct')}% drag\n"
        f"- SPR Draw Mitigation active: {payload.get('spr_drawdown_active')}\n"
        f"- Expected GDP Cost Avoided (via SPR release): ${summary.get('expected_cost_avoided_usd'):,.0f} USD\n"
        f"- Estimated Mitigation ROI: {summary.get('resilience_roi_pct')}% (against platform operations)\n\n"
        f"--- BRIEFING FORMAT ---\n"
        f"Structure the briefing with short, bulleted sections:\n"
        f"1. **EXECUTIVE VERDICT** (2 sentences warning on overall national safety and economic impact)\n"
        f"2. **CRITICAL BOTTLE-NECKS** (List of 2 bullet points on refineries and electricity grid stress)\n"
        f"3. **MITIGATION EFFICIENCY** (Brief evaluation of the SPR drawdown - was it sufficient? Mention the GDP savings and return-on-investment)\n"
        f"4. **RECOMMENDED ACTIONS** (3 concrete, immediate policy actions: procurement, pricing policy, and emergency conservation)\n\n"
        f"Respond ONLY with the clean Markdown content. Avoid greetings or introductory remarks."
    )

    try:
        briefing_text = await complete(prompt=prompt, system="You are an expert energy advisor.")
    except Exception as exc:
        briefing_text = f"**Error generating briefing:** {str(exc)}"

    return {"briefing": briefing_text}



@router.post("/ml/train/xgboost")
async def train_xgboost_model(user=Depends(verify_firebase_or_local_token)) -> dict:
    result = _enqueue_celery_task("scheduler.tasks.train_xgboost")
    add_audit("xgboost_train", user.get("sub", "local"))
    return result

