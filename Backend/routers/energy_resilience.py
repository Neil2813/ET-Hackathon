from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends

from services.firebase_auth import verify_firebase_or_local_token
from services.firestore_store import add_audit
from services.energy_resilience import (
    build_ais_anomaly_forecast,
    build_compatibility_matches,
    build_energy_resilience_dashboard,
    build_exchange_ledger,
    build_geopolitical_rag,
    build_spr_policy,
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


@router.post("/ml/train/xgboost")
async def train_xgboost_model(user=Depends(verify_firebase_or_local_token)) -> dict:
    result = _enqueue_celery_task("scheduler.tasks.train_xgboost")
    add_audit("xgboost_train", user.get("sub", "local"))
    return result
