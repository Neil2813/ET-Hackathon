from __future__ import annotations

import json
import logging
from fastapi import APIRouter, Depends, HTTPException

from services.firebase_auth import verify_firebase_or_local_token
from services.tenant_quota import quota_manager
from services.master_data_validator import validate_supplier_rows
from services.firestore import write_context, read_context
from services.firestore_store import get_context, add_audit
from routers.schemas import OnboardingRequest
from routers.helpers import (
    _assert_same_user,
    _scrub_context,
    _record_master_data_change,
)

logger = logging.getLogger("routers.onboarding")
router = APIRouter(tags=["Onboarding"])


@router.post("/api/onboarding/validate")
async def onboarding_validate(payload: OnboardingRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    """Staging area endpoint for pre-flighting massive CSVs before committing."""
    _assert_same_user(user, payload.user_id)
    supplier_check = validate_supplier_rows([s for s in payload.suppliers if isinstance(s, dict)])
    
    warnings = supplier_check.warnings.copy()
    
    # Check for DUNS duplication within the payload
    seen_duns = set()
    for s in payload.suppliers:
        if isinstance(s, dict):
            duns = s.get("dunsNumber") or s.get("duns_number")
            name = s.get("name")
            if duns:
                if duns in seen_duns:
                    warnings.append(f"Duplicate DUNS/LEI found across rows for '{name}': {duns}. This may cause deduplication.")
                seen_duns.add(duns)

    return {
        "valid": supplier_check.valid,
        "errors": supplier_check.errors,
        "warnings": warnings,
        "staged_supplier_count": len(payload.suppliers),
        "staged_logistics_count": len(payload.logistics_nodes)
    }


@router.post("/onboarding/complete")
async def onboarding_complete(payload: OnboardingRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    _assert_same_user(user, payload.user_id)
    supplier_check = validate_supplier_rows([s for s in payload.suppliers if isinstance(s, dict)])
    if not supplier_check.valid:
        raise HTTPException(status_code=422, detail={"message": "Invalid supplier master data", "errors": supplier_check.errors})
    
    # Enforce quota limits
    try:
        quota_manager.check_network_size(payload.user_id, len(payload.suppliers) + len(payload.logistics_nodes))
        quota_manager.enforce_rate_limit(payload.user_id, "onboarding")
    except Exception as e:
        raise HTTPException(status_code=429, detail=str(e))
        
    scrubbed = _scrub_context(payload)
    scrubbed["master_data_version"] = int((scrubbed.get("master_data_version") or 0)) + 1
    try:
        result = write_context(payload.user_id, scrubbed)
    except Exception as exc:
        logger.exception("Failed to persist onboarding context for %s", payload.user_id)
        raise HTTPException(status_code=503, detail="Unable to save onboarding context. Check backend storage configuration.") from exc
    _record_master_data_change(
        payload.user_id,
        "onboarding_context_update",
        {
            "suppliers_count": len(payload.suppliers),
            "logistics_nodes_count": len(payload.logistics_nodes),
            "warnings": supplier_check.warnings,
            "master_data_version": scrubbed["master_data_version"],
        },
    )
    try:
        add_audit("onboarding_complete", payload.user_id)
    except Exception as exc:
        logger.warning("Failed to write onboarding audit for %s: %s", payload.user_id, exc)
    return {"status": "ok", **result}


@router.post("/api/onboarding/complete")
async def api_onboarding_complete(payload: OnboardingRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    return await onboarding_complete(payload, user)


@router.get("/api/contexts/{user_id}")
async def api_context_get(user_id: str, user=Depends(verify_firebase_or_local_token)) -> dict:
    _assert_same_user(user, user_id)
    # Load context from Firestore.
    fs = read_context(user_id)
    if isinstance(fs, dict) and fs:
        context = dict(fs)
        context.pop("user_id", None)
        context.pop("workflow_id", None)
        updated = str(context.get("updated_at") or "")
        return {"user_id": user_id, "updated_at": updated, "context": context}

    row = get_context(user_id)
    if not row:
        return {"user_id": user_id, "updated_at": None, "context": {}}
    try:
        payload = json.loads(row.get("payload_json") or "{}")
    except Exception:
        payload = {}
    return {"user_id": row.get("user_id"), "updated_at": row.get("updated_at"), "context": payload}


@router.get("/api/onboarding/status/{user_id}")
async def api_onboarding_status(user_id: str, user=Depends(verify_firebase_or_local_token)) -> dict:
    _assert_same_user(user, user_id)
    fs = read_context(user_id)
    payload: dict = {}
    updated_at = None
    if isinstance(fs, dict) and fs:
        payload = dict(fs)
        payload.pop("user_id", None)
        updated_at = payload.get("updated_at")
    else:
        row = get_context(user_id)
        if row:
            updated_at = row.get("updated_at")
            try:
                payload = json.loads(row.get("payload_json") or "{}")
            except Exception:
                payload = {}

    suppliers = payload.get("suppliers") if isinstance(payload, dict) else None
    nodes = payload.get("logistics_nodes") if isinstance(payload, dict) else None
    complete = (
        bool(payload)
        and isinstance(suppliers, list)
        and len(suppliers) > 0
        and isinstance(nodes, list)
        and len(nodes) > 0
        and bool(payload.get("company_name"))
    )
    return {"user_id": user_id, "complete": complete, "updated_at": updated_at}
