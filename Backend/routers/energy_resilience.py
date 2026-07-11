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
from routers.schemas import EnergyResilienceSPRRequest, CrudeCompatibilityRequest
from routers.helpers import _resolved_request_tenant, _enqueue_celery_task

router = APIRouter(tags=["Energy Resilience"])


def _energy_tenant(user: dict[str, Any]) -> str:
    try:
        return _resolved_request_tenant(user)
    except Exception:
        return str(user.get("sub") or "default").strip() or "default"


@router.get("/api/energy-resilience/dashboard")
async def api_energy_resilience_dashboard(user=Depends(verify_firebase_or_local_token)) -> dict[str, Any]:
    tenant_id = _energy_tenant(user)
    payload = build_energy_resilience_dashboard(tenant_id)
    add_audit("energy_resilience_dashboard", tenant_id)
    return payload


@router.get("/api/energy-resilience/ais")
async def api_energy_resilience_ais(user=Depends(verify_firebase_or_local_token)) -> dict[str, Any]:
    add_audit("energy_resilience_ais_forecast", user.get("sub", "local"))
    return build_ais_anomaly_forecast()


@router.post("/api/energy-resilience/spr-policy")
async def api_energy_resilience_spr_policy(
    payload: EnergyResilienceSPRRequest,
    user=Depends(verify_firebase_or_local_token),
) -> dict[str, Any]:
    add_audit("energy_resilience_spr_policy", user.get("sub", "local"))
    return build_spr_policy(payload.model_dump())


@router.post("/api/energy-resilience/crude-compatibility")
async def api_energy_resilience_crude_compatibility(
    payload: CrudeCompatibilityRequest,
    user=Depends(verify_firebase_or_local_token),
) -> dict[str, Any]:
    add_audit("energy_resilience_crude_compatibility", f"{user.get('sub', 'local')}:{payload.blocked_grade}")
    return build_compatibility_matches(payload.blocked_grade)


@router.get("/api/energy-resilience/geopolitical-rag")
async def api_energy_resilience_geopolitical_rag(user=Depends(verify_firebase_or_local_token)) -> dict[str, Any]:
    add_audit("energy_resilience_geopolitical_rag", user.get("sub", "local"))
    return build_geopolitical_rag()


@router.get("/api/energy-resilience/exchange-ledger")
async def api_energy_resilience_exchange_ledger(user=Depends(verify_firebase_or_local_token)) -> dict[str, Any]:
    tenant_id = _energy_tenant(user)
    add_audit("energy_resilience_exchange_ledger", tenant_id)
    return build_exchange_ledger(tenant_id)


@router.get("/api/energy-resilience/blend-optimizer")
async def api_blend_optimizer(
    blocked_grade: str = Query(default="iranian_light", description="ID of the blocked crude grade"),
    user=Depends(verify_firebase_or_local_token),
) -> dict[str, Any]:
    """
    LP-optimised multi-crude blend recipes for all refineries when a primary
    grade is disrupted. Uses scipy HiGHS solver to find the optimal mixture
    satisfying each refinery's API gravity, sulfur %, and viscosity spec.
    """
    add_audit("energy_resilience_blend_optimizer", f"{user.get('sub', 'local')}:{blocked_grade}")
    return build_all_blend_recipes(blocked_grade)


@router.get("/api/energy-resilience/route-comparison")
async def api_route_comparison(
    corridor_risk: float = Query(default=0.65, ge=0.0, le=1.0, description="Bab el-Mandeb risk score 0–1"),
    user=Depends(verify_firebase_or_local_token),
) -> dict[str, Any]:
    """
    Suez Canal vs Cape of Good Hope routing comparison for Gulf→India crude tankers.
    Returns cost, transit time, war-risk premium, CO2, and a recommendation
    ('suez' | 'cape' | 'cape_strongly_recommended') driven by the live corridor risk score.
    """
    add_audit("energy_resilience_route_comparison", user.get("sub", "local"))
    return build_route_comparison(corridor_risk_score=corridor_risk)


@router.post("/ml/train/xgboost")
async def train_xgboost_model(user=Depends(verify_firebase_or_local_token)) -> dict:
    result = _enqueue_celery_task("scheduler.tasks.train_xgboost")
    add_audit("xgboost_train", user.get("sub", "local"))
    return result
