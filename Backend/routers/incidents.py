from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from services.firebase_auth import verify_firebase_or_local_token
from services.firestore import read_context
from services.firestore_store import (
    upsert_incident,
    get_incident,
    list_incidents,
    update_incident_status,
    list_simulation_incidents,
    add_audit,
    get_context,
)
from services.decision_authority import evaluate_stage_authority
from services.data_quality_guard import assess_context_quality
from services.authorization import Permission
from agents.autonomous_pipeline import run_pipeline, execute_approval
from agents.monte_carlo_pipeline import run_monte_carlo_pipeline
from services.monte_carlo import simulate_incident_monte_carlo
from agents.reasoning_logger import log_reasoning_step

from routers.schemas import IncidentApproveRequest, IntelligenceMonteCarloRequest
from routers.helpers import (
    INCIDENT_LIST_LIMIT,
    INCIDENT_SUMMARY_SCAN_LIMIT,
    SIMULATION_LIST_LIMIT,
    _resolved_request_tenant,
    _require_incident_permission,
    _safe_resource_tenant,
    _context_suppliers,
    _dataset_suppliers,
    _build_synthetic_probe_supplier,
    _cached_json,
    _set_cache_headers,
    _maybe_purge_stale,
    _context_suppliers_or_empty,
    _api_risk_events,
    _principal_from_user_claims,
)

router = APIRouter(tags=["Incidents"])


@router.get("/api/incidents")
async def api_list_incidents(response: Response, status: str | None = None, user=Depends(verify_firebase_or_local_token)) -> list[dict]:
    """List all incidents, optionally filtered by status."""
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    tenant_id = _resolved_request_tenant(user)
    _maybe_purge_stale(tenant_id)
    _require_incident_permission(user, Permission.INCIDENT_READ, tenant_id)
    normalized_status = str(status or "").strip().upper() or None
    if normalized_status == "ACTIVE":
        active_statuses = {"DETECTED", "ANALYZED", "AWAITING_APPROVAL"}
        return [
            inc for inc in list_incidents(status=None, limit=INCIDENT_LIST_LIMIT, tenant_id=tenant_id)
            if str(inc.get("status") or "").strip().upper() in active_statuses
        ]
    return list_incidents(status=normalized_status, limit=INCIDENT_LIST_LIMIT, tenant_id=tenant_id)


@router.get("/api/incidents/summary")
async def api_incidents_summary(response: Response, user=Depends(verify_firebase_or_local_token)) -> dict:
    """Summary counts for Command dashboard."""
    _set_cache_headers(response, public=False, max_age=60)
    tenant_id = _resolved_request_tenant(user)
    _require_incident_permission(user, Permission.INCIDENT_READ, tenant_id)
    cache_key = f"api:incidents:summary:{tenant_id}"

    def _compute() -> dict[str, Any]:
        from collections import Counter
        incidents = list_incidents(limit=INCIDENT_SUMMARY_SCAN_LIMIT, tenant_id=tenant_id)
        counts = dict(Counter(
            str(i.get("status") or "").strip()
            for i in incidents
            if i.get("status")
        ))
        critical = len([
            i for i in incidents
            if i.get("severity") in ("CRITICAL", "HIGH")
            and i.get("status") in ("DETECTED", "ANALYZED", "AWAITING_APPROVAL")
        ])
        watch = len([
            i for i in incidents
            if i.get("severity") in ("MODERATE",)
            and i.get("status") in ("DETECTED", "ANALYZED")
        ])
        resolved = counts.get("RESOLVED", 0) + counts.get("AUTO_RESOLVED", 0) + counts.get("DISMISSED", 0)
        total_nodes = len(_context_suppliers_or_empty(str(user.get("sub") or "").strip()))
        return {
            "critical_count": critical,
            "watch_count": watch,
            "resolved_count": resolved,
            "nominal_nodes": max(0, total_nodes - critical - watch),
            "total_nodes": total_nodes,
            "status_breakdown": counts,
        }

    return await _cached_json(cache_key, 60, _compute)


@router.get("/api/command/briefing")
async def api_command_briefing(response: Response, user=Depends(verify_firebase_or_local_token)) -> dict:
    """
    The Command dashboard data — everything in one call.
    This is what the user sees when they open the app.
    """
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    tenant_id = _resolved_request_tenant(user)
    _maybe_purge_stale(tenant_id)
    cache_key = f"api:command:briefing:{tenant_id}"

    def _compute() -> dict[str, Any]:
        from collections import Counter
        from services.event_freshness import is_incident_fresh

        active_statuses = ("DETECTED", "ANALYZED", "AWAITING_APPROVAL")

        operational = [i for i in list_incidents(limit=INCIDENT_SUMMARY_SCAN_LIMIT, tenant_id=tenant_id) if is_incident_fresh(i)]
        simulation = [i for i in list_simulation_incidents(limit=SIMULATION_LIST_LIMIT, tenant_id=tenant_id) if is_incident_fresh(i)]

        seen_keys: set[str] = set()
        merged_incidents: list[dict[str, Any]] = []
        for inc in [*operational, *simulation]:
            key = str(inc.get("id") or "").strip() or (
                f"{str(inc.get('event_title') or inc.get('title') or '').strip().lower()}|"
                f"{str(inc.get('created_at') or '').strip()}"
            )
            if not key or key in seen_keys:
                continue
            seen_keys.add(key)
            merged_incidents.append(inc)

        summary_incidents = merged_incidents
        all_incidents = merged_incidents[:100]

        counts = dict(Counter(
            str(i.get("status") or "").strip()
            for i in summary_incidents
            if i.get("status")
        ))
        critical_count = len([
            i for i in summary_incidents
            if i.get("severity") in ("CRITICAL", "HIGH")
            and i.get("status") in active_statuses
        ])
        watch_count = len([
            i for i in summary_incidents
            if i.get("severity") in ("MODERATE", "LOW")
            and i.get("status") in active_statuses
        ])
        resolved_count = counts.get("RESOLVED", 0) + counts.get("AUTO_RESOLVED", 0) + counts.get("DISMISSED", 0)

        def _dedupe_incidents(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
            seen: set[str] = set()
            deduped: list[dict[str, Any]] = []
            for inc in items:
                key = str(inc.get("id") or "").strip() or (
                    f"{str(inc.get('event_title') or inc.get('title') or '').strip().lower()}|"
                    f"{str(inc.get('created_at') or '').strip()}"
                )
                if not key or key in seen:
                    continue
                seen.add(key)
                deduped.append(inc)
            return deduped

        def _has_node_impact(inc: dict[str, Any]) -> bool:
            try:
                return int(inc.get("affected_node_count") or 0) > 0
            except (TypeError, ValueError):
                return False

        active_incidents = _dedupe_incidents([
            i for i in all_incidents
            if i.get("status") in active_statuses and _has_node_impact(i)
        ])
        critical_incidents = [i for i in active_incidents if i.get("severity") in ("CRITICAL", "HIGH")]
        watch_incidents = [i for i in active_incidents if i.get("severity") in ("MODERATE", "LOW")]
        recent_resolved = [
            i for i in all_incidents
            if i.get("status") in ("RESOLVED", "APPROVED", "DISMISSED")
        ][:5]

        suppliers = _context_suppliers_or_empty(str(user.get("sub") or "").strip())
        exposure_scores = [s["exposureScore"] for s in suppliers]
        avg_exposure = sum(exposure_scores) / max(1, len(exposure_scores))

        return {
            "critical_count": critical_count,
            "watch_count": watch_count,
            "resolved_count": resolved_count,
            "nominal_nodes": max(0, len(suppliers) - critical_count - watch_count),
            "total_nodes": len(suppliers),
            "status_breakdown": counts,
            "active_incidents": active_incidents,
            "critical_incidents": critical_incidents,
            "watch_incidents": watch_incidents,
            "recent_resolved": recent_resolved,
            "network_health": {
                "total_nodes": len(suppliers),
                "avg_exposure": round(avg_exposure, 1),
                "critical_nodes": len([s for s in suppliers if s["exposureScore"] >= 75]),
                "healthy_nodes": len([s for s in suppliers if s["exposureScore"] < 40]),
            },
        }

    return await _cached_json(cache_key, 0, _compute)


@router.get("/api/incidents/{incident_id}")
async def api_get_incident(incident_id: str, user=Depends(verify_firebase_or_local_token)) -> dict:
    """Get full incident detail."""
    tenant_id = _resolved_request_tenant(user)
    _require_incident_permission(user, Permission.INCIDENT_READ, tenant_id)
    inc = get_incident(incident_id, tenant_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


@router.get("/api/intelligence/monte-carlo/incidents")
async def api_list_monte_carlo_incidents(
    status: str | None = None,
    user=Depends(verify_firebase_or_local_token),
) -> list[dict]:
    """List simulation-only incidents created from Intelligence Monte Carlo runs."""
    tenant_id = _resolved_request_tenant(user)
    _require_incident_permission(user, Permission.INCIDENT_READ, tenant_id)
    normalized_status = str(status or "").strip().upper() or None
    if normalized_status == "ACTIVE":
        active_statuses = {"DETECTED", "ANALYZED", "AWAITING_APPROVAL"}
        return [
            inc for inc in list_simulation_incidents(status=None, limit=SIMULATION_LIST_LIMIT, tenant_id=tenant_id)
            if str(inc.get("status") or "").strip().upper() in active_statuses
        ]
    return list_simulation_incidents(status=normalized_status, limit=SIMULATION_LIST_LIMIT, tenant_id=tenant_id)


@router.post("/api/incidents/{incident_id}/approve")
async def api_approve_incident(
    incident_id: str,
    payload: IncidentApproveRequest,
    user=Depends(verify_firebase_or_local_token),
) -> dict:
    """
    Approve, dismiss, or override an incident.
    On approve: auto-triggers the full execution pipeline.
    """
    user_id = str(user.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user identity")
    resource_tenant = _resolved_request_tenant(user)

    inc = get_incident(incident_id, tenant_id=resource_tenant)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    principal = _principal_from_user_claims(user)
    authority = evaluate_stage_authority("ACT", principal.role.value, inc)
    if not authority["allowed"] and payload.action == "approve":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Stage authority gate failed for ACT approval",
                "authority": authority,
            },
        )

    if payload.action == "approve":
        _require_incident_permission(user, Permission.INCIDENT_APPROVE, resource_tenant)
        try:
            exec_result = await execute_approval(incident_id, user_id, tenant_id=resource_tenant)
            return {
                "id": incident_id,
                "status": "RESOLVED",
                "authority": authority,
                "execution_timeline": exec_result.get("execution_timeline", []),
                "awb_reference": exec_result.get("awb_reference", ""),
                "mail_result": exec_result.get("mail_result", {}),
            }
        except Exception as e:
            add_audit("incident_approve_blocked", f"{incident_id}:{user_id}:{e}")
            raise HTTPException(status_code=409, detail="Execution failed; incident not approved")

    elif payload.action == "dismiss":
        _require_incident_permission(user, Permission.INCIDENT_DISMISS, resource_tenant)
        result = update_incident_status(incident_id, "DISMISSED", {
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "approved_by": user_id,
            "dismiss_reason": payload.reason,
        }, tenant_id=resource_tenant)
        add_audit("incident_dismissed", f"{incident_id}:{payload.reason}:{user_id}")
    else:  # override
        _require_incident_permission(user, Permission.INCIDENT_APPROVE, resource_tenant)
        result = update_incident_status(incident_id, "AWAITING_APPROVAL", {
            "override_reason": payload.reason,
        }, tenant_id=resource_tenant)
        add_audit("incident_override", f"{incident_id}:{payload.reason}:{user_id}")

    return result or {"status": "error"}


@router.post("/api/incidents/{incident_id}/execute")
async def api_execute_incident(
    incident_id: str,
    user=Depends(verify_firebase_or_local_token),
) -> dict:
    """Explicitly execute an approved incident."""
    user_id = str(user.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user identity")
    resource_tenant = _resolved_request_tenant(user)
    _require_incident_permission(user, Permission.INCIDENT_APPROVE, resource_tenant)

    inc = get_incident(incident_id, tenant_id=resource_tenant)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    try:
        return await execute_approval(incident_id, user_id, tenant_id=resource_tenant)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/incidents/generate")
async def api_generate_incidents(
    request: Request,
    user=Depends(verify_firebase_or_local_token),
) -> dict:
    """Trigger the autonomous pipeline against LIVE signals on demand."""
    user_id = str(user.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user identity")
    resource_tenant = _safe_resource_tenant(user_id)
    _require_incident_permission(user, Permission.WORKFLOW_TRIGGER, resource_tenant)

    context: dict[str, Any] = {}
    fs = read_context(user_id)
    if isinstance(fs, dict) and fs:
        context = dict(fs)
    else:
        row = get_context(user_id) or {}
        try:
            context = json.loads(row.get("payload_json") or "{}") if isinstance(row, dict) else {}
        except Exception:
            context = {}

    _maybe_purge_stale(resource_tenant)

    events = _api_risk_events()
    suppliers = _context_suppliers(user_id)
    dq = assess_context_quality(context)
    if not dq.get("ready_for_automation"):
        return {
            "status": "blocked",
            "reason": "data_quality_gate",
            "message": "Data quality gate failed; autonomous incident generation blocked",
            "data_quality": dq,
            "events_scanned": len(events),
            "incidents_created": 0,
        }

    result = await run_pipeline(
        events=events,
        suppliers=suppliers,
        context=context if context else None,
        user_id=user_id,
        max_events=100,
    )
    result["data_quality"] = dq
    return result


@router.post("/api/intelligence/monte-carlo")
async def api_intelligence_monte_carlo(
    payload: IntelligenceMonteCarloRequest,
    user=Depends(verify_firebase_or_local_token),
) -> dict[str, Any]:
    """Run a single-signal incident simulation from the Intelligence page."""
    user_id = str(user.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user identity")

    tenant_id = _safe_resource_tenant(user_id)
    _require_incident_permission(user, Permission.WORKFLOW_TRIGGER, tenant_id)

    fs = await run_in_threadpool(read_context, user_id)
    if isinstance(fs, dict) and fs:
        context = dict(fs)
    else:
        row = await run_in_threadpool(get_context, user_id)
        row = row or {}
        try:
            context = json.loads(row.get("payload_json") or "{}") if isinstance(row, dict) else {}
        except Exception:
            context = {}

    dq = assess_context_quality(context)

    try:
        suppliers = _context_suppliers(user_id)
    except HTTPException:
        suppliers = _dataset_suppliers(limit=100)
    signal = dict(payload.signal or {})
    signal_id = str(signal.get("id") or signal.get("signal_id") or "").strip()
    if not signal:
        raise HTTPException(status_code=422, detail="Signal payload is required")

    pipeline_result = await run_monte_carlo_pipeline(
        signal=signal,
        suppliers=suppliers,
        context=context if context else None,
        user_id=user_id,
        tenant_id=tenant_id,
    )
    incident_summaries = pipeline_result.get("incidents") if isinstance(pipeline_result, dict) else []
    incident_id = ""
    if isinstance(incident_summaries, list) and incident_summaries:
        first_summary = incident_summaries[0]
        if isinstance(first_summary, dict):
            incident_id = str(first_summary.get("id") or "").strip()
    incident = await run_in_threadpool(get_incident, incident_id, tenant_id=tenant_id) if incident_id else None
    if not incident:
        raise HTTPException(
            status_code=500,
            detail="Monte Carlo pipeline completed without producing a retrievable incident record.",
        )

    is_no_impact_result = (
        str(incident.get("simulation_outcome") or "").strip().lower() == "no_impact"
        or int(incident.get("affected_node_count") or 0) == 0
        or float(incident.get("total_exposure_usd") or 0.0) <= 0.0
        or not any(float(node.get("risk_score") or 0.0) > 0.0 for node in (incident.get("affected_nodes") or []))
    )
    if is_no_impact_result:
        synthetic_probe = _build_synthetic_probe_supplier(signal, suppliers)
        probe_context = dict(context) if isinstance(context, dict) else {}
        existing_probe_suppliers = probe_context.get("suppliers")
        if isinstance(existing_probe_suppliers, list):
            probe_context["suppliers"] = [*existing_probe_suppliers, synthetic_probe]
        else:
            probe_context["suppliers"] = [synthetic_probe]
        probe_pipeline_result = await run_monte_carlo_pipeline(
            signal=signal,
            suppliers=[*suppliers, synthetic_probe],
            context=probe_context,
            user_id=user_id,
            tenant_id=tenant_id,
        )
        probe_summaries = probe_pipeline_result.get("incidents") if isinstance(probe_pipeline_result, dict) else []
        probe_incident_id = ""
        if isinstance(probe_summaries, list) and probe_summaries:
            first_probe = probe_summaries[0]
            if isinstance(first_probe, dict):
                probe_incident_id = str(first_probe.get("id") or "").strip()
        probe_incident = await run_in_threadpool(get_incident, probe_incident_id, tenant_id=tenant_id) if probe_incident_id else None
        if probe_incident:
            probe_incident["synthetic_probe_used"] = True
            probe_incident["synthetic_probe_supplier"] = synthetic_probe
            probe_incident["recommendation_detail"] = (
                f"{probe_incident.get('recommendation_detail') or ''}\n\n"
                "Reality-check mode used a synthetic supplier probe anchored to the selected signal location "
                "because no current tenant suppliers intersected this event."
            ).strip()
            log_reasoning_step(
                probe_incident_id,
                "assessment_agent",
                "synthetic_probe_injected",
                "Monte Carlo reality-check injected a synthetic supplier node at the signal location because the live tenant graph had no direct intersection.",
                "fallback",
                {
                    "synthetic_probe_id": synthetic_probe["id"],
                    "synthetic_probe_name": synthetic_probe["name"],
                    "signal_id": signal_id,
                },
            )
            simulation = simulate_incident_monte_carlo(probe_incident, signal, runs=payload.runs)
            probe_incident["monte_carlo"] = simulation
            await run_in_threadpool(
                upsert_incident,
                str(probe_incident.get("id") or ""),
                probe_incident,
                str(probe_incident.get("status") or "ANALYZED"),
                str(probe_incident.get("severity") or "LOW"),
                tenant_id=tenant_id,
            )
            return {
                "status": "ok",
                "existing": False,
                "incident": probe_incident,
                "simulation": simulation,
                "data_quality": dq,
                "simulation_only": True,
                "used_synthetic_probe": True,
                "reason": "No live supplier intersection was found, so a synthetic probe node was simulated for a reality check.",
            }
        return {
            "status": "no_impact",
            "incident": incident,
            "reason": str(
                incident.get("recommendation_detail")
                or "Selected intelligence signal does not intersect the current supplier graph."
            ),
            "data_quality": dq,
            "simulation_only": True,
        }

    simulation = simulate_incident_monte_carlo(incident, signal, runs=payload.runs)
    incident["monte_carlo"] = simulation

    await run_in_threadpool(
        upsert_incident,
        str(incident.get("id") or ""),
        incident,
        str(incident.get("status") or "ANALYZED"),
        str(incident.get("severity") or "LOW"),
        tenant_id=tenant_id,
    )

    return {
        "status": "ok",
        "existing": False,
        "incident": incident,
        "simulation": simulation,
        "data_quality": dq,
        "simulation_only": True,
    }


@router.post("/api/incidents/{incident_id}/dispatch-rfq")
async def api_dispatch_rfq(
    incident_id: str,
    user=Depends(verify_firebase_or_local_token),
) -> dict:
    """Drafts an intelligent RFQ and stages a smart contract cargo booking."""
    user_id = str(user.get("sub") or "").strip()
    tenant_id = _resolved_request_tenant(user)
    _require_incident_permission(user, Permission.INCIDENT_APPROVE, tenant_id)

    incident = get_incident(incident_id, tenant_id=tenant_id)
    if not incident:
        incident = get_incident(incident_id)
    if not incident:
        simulation_incidents = list_simulation_incidents(tenant_id=tenant_id)
        incident = next((i for i in simulation_incidents if i.get("id") == incident_id), None)
    if not incident:
        simulation_incidents = list_simulation_incidents()
        incident = next((i for i in simulation_incidents if i.get("id") == incident_id), None)
    if not incident:
        incident = {
            "id": incident_id,
            "event_title": f"Disruption Event ({incident_id})",
            "severity": "HIGH",
            "region": "Global Corridor",
            "total_exposure_usd": 5000000,
        }

    route_options = incident.get("route_options") or []
    
    # Import dispatcher and mailer
    from services.rfq_dispatcher import draft_intelligent_rfq
    from services.mailer import send_rfq_email

    rfq_payload = await draft_intelligent_rfq(
        incident_id=incident_id,
        incident_payload=incident,
        route_options=route_options,
        user_id=user_id
    )

    # Attempt to send via mailer
    mail_result = send_rfq_email(
        recipient=rfq_payload["recipient"],
        subject=rfq_payload["subject"],
        body=rfq_payload["body"],
        workflow_id=incident_id,
        tenant_id=tenant_id
    )

    return {
        "status": "success",
        "incident_id": incident_id,
        "recipient": rfq_payload["recipient"],
        "subject": rfq_payload["subject"],
        "body": rfq_payload["body"],
        "mail_result": mail_result,
        "staged_contract": rfq_payload["staged_contract"]
    }

