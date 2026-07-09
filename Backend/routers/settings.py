from __future__ import annotations

import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Request

from services.firebase_auth import verify_firebase_or_local_token
from services.firestore import read_context, write_context
from services.firestore_store import (
    add_audit,
    get_context,
    list_audit,
    list_master_data_changes,
    list_rfq_events,
)
from routers.helpers import (
    _resolved_request_tenant,
    _context_suppliers_or_empty,
    _assert_same_user,
)

router = APIRouter(tags=["Settings & Master Data"])


@router.get("/api/settings/profile")
async def api_settings_profile(request: Request, user=Depends(verify_firebase_or_local_token)) -> dict:
    user_id = str(user.get("sub") or "").strip()
    tenant_id = _resolved_request_tenant(user)
    fs = read_context(user_id)
    ctx: dict[str, Any] = {}
    if isinstance(fs, dict) and fs:
        ctx = dict(fs)
    else:
        row = get_context(user_id) or {}
        try:
            ctx = json.loads(row.get("payload_json") or "{}") if isinstance(row, dict) else {}
        except Exception:
            ctx = {}

    profile = ctx.get("operator_profile") if isinstance(ctx.get("operator_profile"), dict) else {}
    return {
        "name": str(profile.get("name") or ""),
        "email": str(profile.get("email") or ""),
        "company": str(profile.get("company") or ctx.get("company_name") or ""),
        "role": str(profile.get("role") or "Admin"),
        "user_id": user_id,
        "tenant_id": tenant_id,
        "customer_id": str(ctx.get("customer_id") or tenant_id),
        "organization_id": str(ctx.get("organization_id") or tenant_id),
    }


@router.patch("/api/settings/profile")
async def api_settings_profile_patch(payload: dict, request: Request, user=Depends(verify_firebase_or_local_token)) -> dict:
    user_id = str(user.get("sub") or "").strip()
    if payload.get("user_id"):
        _assert_same_user(user, str(payload.get("user_id")))

    fs = read_context(user_id)
    ctx: dict[str, Any] = {}
    if isinstance(fs, dict) and fs:
        ctx = dict(fs)
    else:
        row = get_context(user_id) or {}
        try:
            ctx = json.loads(row.get("payload_json") or "{}") if isinstance(row, dict) else {}
        except Exception:
            ctx = {}

    profile = ctx.get("operator_profile") if isinstance(ctx.get("operator_profile"), dict) else {}
    for key in ("name", "email", "company", "role"):
        if key in payload and payload.get(key) is not None:
            profile[key] = payload.get(key)
    ctx["operator_profile"] = profile
    ctx["updated_at"] = datetime.now(timezone.utc).isoformat()

    write_context(user_id, ctx)
    add_audit("settings_profile_update", user_id)
    return await api_settings_profile(request, user)


@router.get("/api/settings/billing")
async def api_settings_billing(user=Depends(verify_firebase_or_local_token)) -> dict:
    tenant_id = _resolved_request_tenant(user)
    workflows_used = len([r for r in list_audit(limit=1000) if str(r.get("action", "")).startswith("workflow_")])
    rfqs_sent = len([r for r in list_rfq_events(limit=1000) if str(r.get("status", "")).lower() == "sent"])
    suppliers_used = len(_context_suppliers_or_empty(str(user.get("sub") or "").strip()))
    return {
        "plan": "Usage",
        "monthlyRate": 0,
        "workflowRunsUsed": workflows_used,
        "workflowRunsLimit": 1000,
        "rfqsSent": rfqs_sent,
        "suppliersUsed": suppliers_used,
        "suppliersLimit": max(200, suppliers_used),
        "tenantId": tenant_id,
    }


@router.get("/api/master-data/changes")
async def api_master_data_changes(limit: int = 200, user=Depends(verify_firebase_or_local_token)) -> dict[str, Any]:
    user_id = str(user.get("sub") or "").strip()
    return {"changes": list_master_data_changes(user_id, limit=max(1, min(limit, 1000)))}


@router.post("/api/master-data/propagate")
async def api_master_data_propagate(user=Depends(verify_firebase_or_local_token)) -> dict[str, Any]:
    user_id = str(user.get("sub") or "").strip()
    changes = list_master_data_changes(user_id, limit=100)
    if not changes:
        return {"status": "ok", "user_id": user_id, "propagated": 0, "affected_domains": []}
    domains = set()
    for change in changes:
        ctype = str(change.get("change_type") or "")
        if "network" in ctype:
            domains.update({"routing", "monitoring", "incident_generation"})
        if "onboarding" in ctype:
            domains.update({"assessment", "exposure", "workflow_input"})
    summary = {
        "status": "ok",
        "user_id": user_id,
        "propagated": len(changes),
        "affected_domains": sorted(domains),
        "latest_change_at": changes[0].get("created_at"),
    }
    add_audit("master_data_propagated", json.dumps(summary))
    return summary
