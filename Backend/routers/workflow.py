from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from services.firebase_auth import verify_firebase_or_local_token
from services.firestore import read_workflow_event, write_workflow_event, read_context, write_context
from services.firestore_store import (
    add_audit,
    create_rfq_event_linked,
    get_workflow_checkpoint,
    get_workflow_report,
    list_rfq_events,
    list_workflow_reports,
    upsert_workflow_report,
    read_reasoning_steps,
)
from services.master_data_validator import validate_network_graph
from services.tenant_quota import quota_manager
from services.mailer import send_rfq_email
from services.idempotency import derive_key, idempotency_guard, mark_completed, mark_failed
from services.data_quality_guard import assess_context_quality
from services.scenario_confidence import confidence_bounds
from services.data_registry import registry
from services.llm_analysis import generate_workflow_analysis
from services.authorization import Permission
from pdf.certificate import generate_audit_certificate, generate_workflow_audit_report_pdf
from agents.assessment_agent import run_assessment
from agents.routing_agent import run_routing
from agents.spr_optimization_agent import optimize_spr_drawdown
from agents.rfq_agent import draft_rfq
from agents.reasoning_logger import log_reasoning_step
from currency.frankfurter import convert_cost
from routing.decision import enrich_route_decision

from routers.schemas import (
    RouteRequest,
    SPRRequest,
    RFQDraftRequest,
    RFQSendRequest,
    WorkflowStateUpdate,
    WorkflowAnalyzeRequest,
    WorkflowStartRequest,
    WorkflowApprovalRequest,
    WorkflowReportStageUpsert,
    SCNetworkSaveRequest,
    SCNetworkMonitorRequest,
)
from routers.helpers import (
    workflow_graph_manager,
    _assert_workflow_owner,
    _assert_same_user,
    _resolve_point,
    _context_network_routes,
    _network_mode_availability,
    _resolve_customer_id_for_user,
    _can_read_reasoning_stream,
    _resolved_request_tenant,
    _require_incident_permission,
    _decision_evidence_status,
    _context_payload_for_user,
    _validate_detect_inputs,
    _assert_onboarding_readiness,
    _record_master_data_change,
    _haversine_km,
    _event_impact_radius_km,
    _cached_json,
    _api_risk_events,
)

logger = logging.getLogger("routers.workflow")
router = APIRouter(tags=["Workflow"])

_render_cache: dict[str, list[dict]] = {}


@router.post("/workflow/assess")
async def workflow_assess(payload: WorkflowAssessRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    _assert_workflow_owner(user, payload.workflow_id)
    result = run_assessment(payload.workflow_id, payload.event_type, payload.severity, payload.suppliers)
    if not result.get("affected_suppliers"):
        write_workflow_event(payload.workflow_id, "assess", 0.0)
        log_reasoning_step(
            payload.workflow_id,
            "assessment_agent",
            "mapping_exception",
            "ASSESS produced zero mapped suppliers. Escalated as UNMAPPED_SIGNAL for manual entity resolution.",
            "error",
            {
                "event_type": payload.event_type,
                "input_suppliers": len(payload.suppliers),
                "status": "UNMAPPED_SIGNAL",
            },
        )
        return {
            **result,
            "status": "UNMAPPED_SIGNAL",
            "escalated": True,
            "required_action": "manual_entity_resolution",
            "assessed_by": user.get("sub", "local"),
        }
    write_workflow_event(payload.workflow_id, "assess", result["confidence_score"])
    add_audit("workflow_assess", payload.workflow_id)
    log_reasoning_step(
        payload.workflow_id,
        "assessment_agent",
        "assessment_complete",
        f"Event type={payload.event_type}, severity={payload.severity:.1f}. "
        f"Exposure USD ≈ ${float(result['financial_exposure_usd']):,.0f}, "
        f"confidence={float(result['confidence_score']):.2f}.",
        "success",
        {
            "financial_exposure_usd": result["financial_exposure_usd"],
            "confidence_score": result["confidence_score"],
            "days_at_risk": result["days_at_risk"],
        },
    )
    converted = await convert_cost(float(result["financial_exposure_usd"]), "USD")
    log_reasoning_step(
        payload.workflow_id,
        "assessment_agent",
        "currency_conversion",
        f"Frankfurter: 1 USD = {converted.get('rate', 0):.4f} {converted.get('currency', 'USD')} "
        f"({converted.get('rate_date', '')}). "
        f"Local ≈ {converted.get('local', 0):,.2f} {converted.get('currency', '')}.",
        "success",
        {"rate": converted.get("rate"), "currency": converted.get("currency"), "local_amount": converted.get("local")},
    )
    return {
        **result,
        "financial_exposure": converted,
        "assessed_by": user.get("sub", "local"),
    }


@router.post("/workflow/routes")
async def workflow_routes(payload: RouteRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    origin_lat, origin_lng = _resolve_point(payload.origin)
    dest_lat, dest_lng = _resolve_point(payload.destination)
    if abs(origin_lat - dest_lat) < 1e-6 and abs(origin_lng - dest_lng) < 1e-6:
        raise HTTPException(status_code=422, detail="Origin and destination must differ")
    owner_id = str(user.get("sub") or "").strip()
    if payload.workflow_id:
        owner_id = _assert_workflow_owner(user, payload.workflow_id)
    result = await run_routing(
        origin_lat,
        origin_lng,
        payload.origin.country_code,
        f"{payload.origin.city or origin_lat},{payload.origin.country or ''}",
        dest_lat,
        dest_lng,
        payload.destination.country_code,
        f"{payload.destination.city or dest_lat},{payload.destination.country or ''}",
        payload.target_currency.upper(),
        payload.commodity,
    )
    comparison = result.get("route_comparison") if isinstance(result.get("route_comparison"), list) else []
    network_routes = _context_network_routes(owner_id)
    if network_routes:
        mode_availability = _network_mode_availability(network_routes)
        comparison = [row for row in comparison if isinstance(row, dict) and mode_availability.get(str(row.get("mode") or "").lower(), False)]
        constrained_decision = enrich_route_decision(comparison, current_mode="tanker_vlcc")
        result.update(
            {
                "route_comparison": constrained_decision.get("route_options", comparison),
                "recommended_mode": constrained_decision.get("recommended_mode", ""),
                "next_best_mode": constrained_decision.get("next_best_mode", ""),
                "delivery_answer": constrained_decision.get("delivery_answer", ""),
                "next_best_route_answer": constrained_decision.get("next_best_route_answer", ""),
                "cost_answer": constrained_decision.get("cost_answer", ""),
                "customer_impact_answer": constrained_decision.get("customer_impact_answer", ""),
                "decision_summary": constrained_decision.get("decision_summary", {}),
            }
        )
        comparison = result["route_comparison"]
        result["mode_constraints"] = mode_availability
    seen_modes = {str(row.get("mode") or "") for row in comparison if isinstance(row, dict)}
    if not seen_modes:
        raise HTTPException(status_code=422, detail="Disconnected route set; no valid route outputs")
    if str(result.get("recommended_mode") or "") not in {"sea", "air", "land", "hybrid", "tanker_vlcc", "tanker_suezmax"}:
        raise HTTPException(status_code=422, detail="Invalid recommended transport mode")
    add_audit("workflow_routes", user.get("sub", "local"))
    wf_id = (payload.workflow_id or "").strip()
    if wf_id:
        log_reasoning_step(
            wf_id,
            "routing_agent",
            "route_comparison",
            f"Computed VLCC/Suezmax/Cape tanker options; recommended_mode={result.get('recommended_mode')}, "
            f"next_best_mode={result.get('next_best_mode')}, currency_risk_index={result.get('currency_risk_index')}.",
            "success",
            {
                "recommended_mode": result.get("recommended_mode"),
                "next_best_mode": result.get("next_best_mode"),
                "decision_summary": result.get("decision_summary"),
                "currency_risk_index": result.get("currency_risk_index"),
            },
        )
    return result


@router.post("/workflow/spr-optimize")
async def workflow_spr_optimize(payload: SPRRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    result = optimize_spr_drawdown(payload.model_dump())
    add_audit("workflow_spr_optimize", user.get("sub", "local"))
    return {
        **result,
        "optimized_by": user.get("sub", "local"),
    }


@router.post("/api/workflow/spr-optimize")
async def api_workflow_spr_optimize(payload: SPRRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    return await workflow_spr_optimize(payload, user)


@router.post("/workflow/rfq/draft")
async def rfq_draft(payload: RFQDraftRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    _assert_same_user(user, payload.user_id)
    drafted = draft_rfq(payload.recipient, payload.event_context, payload.quantities)
    drafted["estimated_cost"] = await convert_cost(5000.0, "USD")
    drafted["generated_by"] = user.get("sub", "local")
    return drafted


@router.post("/workflow/rfq/send")
async def rfq_send(payload: RFQSendRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    requestor = _assert_same_user(user, payload.user_id)
    _assert_workflow_owner(user, payload.workflow_id)
    checkpoint = get_workflow_checkpoint(payload.workflow_id) or {}
    stage = str(checkpoint.get("current_stage") or "").upper()
    if bool(checkpoint.get("waiting_human")) or stage not in {"ACT", "AUDIT"}:
        raise HTTPException(status_code=409, detail="Workflow is not approved for external RFQ dispatch")
    expected_approval_token = derive_key("rfq_send", payload.workflow_id, requestor)
    if payload.approval_token != expected_approval_token:
        raise HTTPException(status_code=403, detail="Invalid approval token for RFQ dispatch")

    send_key = derive_key(
        "rfq_send",
        payload.workflow_id,
        payload.recipient.strip().lower(),
        payload.subject.strip(),
        payload.body.strip(),
    )
    guard = idempotency_guard(send_key, ttl_seconds=86400, owner_id=requestor)
    if guard.is_duplicate:
        return guard.cached_response or {"status": "already_sent", "workflow_id": payload.workflow_id}
    if guard.is_in_flight:
        return {"status": "in_flight", "workflow_id": payload.workflow_id}

    rfq_id = f"rfq_{uuid4().hex[:10]}"
    create_rfq_event_linked(
        rfq_id,
        payload.user_id,
        payload.workflow_id,
        payload.recipient,
        payload.subject,
        payload.body,
        "sent",
    )
    try:
        mail_result = send_rfq_email(payload.recipient, payload.subject, payload.body)
        response = {
            "status": "sent",
            "rfq_id": rfq_id,
            "workflow_id": payload.workflow_id,
            "mail": mail_result,
            "sent_by": user.get("sub", "local"),
            "approval_note": payload.approval_note or "",
        }
        mark_completed(send_key, response)
        add_audit("rfq_sent", rfq_id)
        return response
    except Exception:
        mark_failed(send_key)
        raise


@router.get("/workflow/state/{workflow_id}")
async def workflow_state(workflow_id: str, stage: Literal["detect", "assess", "decide", "act", "audit"] = "assess", user=Depends(verify_firebase_or_local_token)) -> dict:
    _assert_workflow_owner(user, workflow_id)
    stored = read_workflow_event(workflow_id)
    if stored:
        return stored
    return write_workflow_event(workflow_id, stage, 0.5)


@router.post("/workflow/state/{workflow_id}")
async def workflow_state_update(workflow_id: str, payload: WorkflowStateUpdate, user=Depends(verify_firebase_or_local_token)) -> dict:
    _assert_workflow_owner(user, workflow_id)
    record = write_workflow_event(workflow_id, payload.stage, payload.confidence)
    add_audit("workflow_state_updated", f"{workflow_id}:{payload.stage}:{payload.confidence}:{user.get('sub', 'local')}")
    return record


@router.get("/ports")
async def ports() -> list[dict]:
    return [{"city": p.city, "country": p.country, "lat": p.lat, "lng": p.lng} for p in registry.ports]


@router.get("/airports")
async def airports() -> list[dict]:
    return registry.airports


@router.get("/workflow/rfq/events")
async def rfq_events(user=Depends(verify_firebase_or_local_token)) -> list[dict]:
    return list_rfq_events(limit=100)


@router.post("/api/workflow/analyze")
async def api_workflow_analyze(payload: WorkflowAnalyzeRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    if payload.workflow_id:
        _assert_workflow_owner(user, payload.workflow_id)
    result = await generate_workflow_analysis(
        event=payload.event,
        suppliers=payload.suppliers,
        assessment=payload.assessment,
        workflow_id=payload.workflow_id,
    )
    wf = (payload.workflow_id or "").strip()
    if wf:
        prefer = (os.getenv("LLM_PROVIDER") or "groq").strip().lower()
        used = result.provider
        is_fallback = used == "local" or (used == "groq" and prefer == "gemini")
        log_reasoning_step(
            wf,
            "assessment_agent",
            "gemini_assessment" if used == "gemini" else "llm_analysis",
            f"Assessment narrative generated via {used} (LLM_PROVIDER={prefer}).",
            "fallback" if is_fallback else "success",
            {"provider": used, "llm_provider_env": prefer},
        )
    provider = str(result.provider or "local").strip().lower()
    calibration_factor = {"gemini": 1.0, "groq": 0.92, "local": 0.85}.get(provider, 0.9)
    assessment_conf = None
    if isinstance(payload.assessment, dict):
        raw = payload.assessment.get("confidence_score") or payload.assessment.get("confidence")
        if isinstance(raw, (int, float)):
            assessment_conf = float(raw)
    if assessment_conf is None:
        assessment_conf = 0.5
    evidence = _decision_evidence_status(payload.event if isinstance(payload.event, dict) else {})
    calibrated_conf = max(0.0, min(1.0, assessment_conf * calibration_factor))
    context = _context_payload_for_user(str(user.get("sub") or "").strip())
    dq = assess_context_quality(context)
    bounds = confidence_bounds(calibrated_conf, float(dq.get("score") or 0.0), provider)
    actionable = bool(evidence["actionable"] and bounds["actionable"])
    return {
        "provider": result.provider,
        "analysis": result.text,
        "decision_quality": {
            "provider": provider,
            "calibration_factor": calibration_factor,
            "raw_recommendation_confidence": round(assessment_conf, 4),
            "calibrated_recommendation_confidence": round(calibrated_conf, 4),
            "evidence": evidence,
            "data_quality": dq,
            "confidence_bounds": bounds,
            "actionable": actionable,
            "action_block_reason": "" if actionable else "insufficient_evidence_or_uncalibrated_confidence",
        },
    }


@router.post("/api/workflow/start")
async def api_workflow_start(payload: WorkflowStartRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    _assert_same_user(user, payload.user_id)
    _assert_onboarding_readiness(payload.user_id)
    _validate_detect_inputs(payload.selected_signal, payload.affected_suppliers)
    customer_id = _resolve_customer_id_for_user(payload.user_id)
    network_routes = _context_network_routes(payload.user_id)
    initial_state = {
        "workflow_id": payload.workflow_id,
        "user_id": payload.user_id,
        "customer_id": customer_id,
        "current_stage": "DETECT",
        "signals": [payload.selected_signal] if payload.selected_signal else [],
        "selected_signal": payload.selected_signal,
        "affected_suppliers": payload.affected_suppliers,
        "exposure_usd": 0.0,
        "exposure_local": 0.0,
        "local_currency": payload.local_currency,
        "days_at_risk": 0,
        "confidence": 0.0,
        "currency_risk_index": 0.0,
        "inflation_rate": 0.0,
        "assessment_summary": "",
        "route_comparison": [],
        "network_routes": network_routes,
        "recommended_mode": "",
        "rl_confidence": 0.0,
        "rfq_sent": False,
        "action_state": {"generated": False, "executed": False, "confirmed": False},
        "reasoning_steps": [],
    }
    return await workflow_graph_manager.start_workflow(initial_state)


@router.post("/api/workflow/{workflow_id}/approve")
async def api_workflow_approve(workflow_id: str, payload: WorkflowApprovalRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    owner = _assert_workflow_owner(user, workflow_id)
    approved = await workflow_graph_manager.approve_decision(workflow_id, action=payload.action, mode=payload.mode)
    approved["rfq_approval_token"] = derive_key("rfq_send", workflow_id, owner)
    return approved


@router.post("/api/workflow/report")
async def api_workflow_report_upsert(payload: WorkflowReportStageUpsert, user=Depends(verify_firebase_or_local_token)) -> dict:
    _assert_workflow_owner(user, payload.workflow_id)
    existing = get_workflow_report(payload.workflow_id) or {"workflow_id": payload.workflow_id}
    existing.setdefault("user_id", _resolve_workflow_owner(payload.workflow_id))
    stage_order = ["detect", "assess", "decide", "act", "audit"]
    idx = stage_order.index(payload.stage)
    if idx > 0:
        prior = stage_order[idx - 1]
        if prior not in existing:
            raise HTTPException(status_code=409, detail=f"Cannot write {payload.stage} before {prior}")
    if payload.stage == "audit":
        act_payload = existing.get("act") if isinstance(existing.get("act"), dict) else {}
        action_state = act_payload.get("action_state") if isinstance(act_payload.get("action_state"), dict) else {}
        if not bool(action_state.get("confirmed")):
            raise HTTPException(status_code=409, detail="Cannot write audit before ACT confirmation")
    existing[payload.stage] = payload.payload
    existing["updated_at"] = datetime.now(timezone.utc).isoformat()

    summary = existing.get("summary") if isinstance(existing.get("summary"), dict) else {}
    detect_evt = (existing.get("detect") or {}).get("event") if isinstance(existing.get("detect"), dict) else None
    if isinstance(detect_evt, dict):
        summary["event_title"] = detect_evt.get("title") or detect_evt.get("event_type")
        summary["region"] = detect_evt.get("region") or detect_evt.get("location")
    assess = existing.get("assess") if isinstance(existing.get("assess"), dict) else {}
    if isinstance(assess, dict):
        summary["exposure_usd"] = assess.get("exposure_usd")
        summary["affected_nodes"] = assess.get("affected_nodes")
    decide = existing.get("decide") if isinstance(existing.get("decide"), dict) else {}
    if isinstance(decide, dict):
        summary["recommended_mode"] = decide.get("recommended_mode")
    act = existing.get("act") if isinstance(existing.get("act"), dict) else {}
    if isinstance(act, dict):
        summary["action_taken"] = act.get("decision")
        action_state = act.get("action_state") if isinstance(act.get("action_state"), dict) else {}
        if action_state:
            summary["act_generated"] = bool(action_state.get("generated"))
            summary["act_executed"] = bool(action_state.get("executed"))
            summary["act_confirmed"] = bool(action_state.get("confirmed"))
    audit = existing.get("audit") if isinstance(existing.get("audit"), dict) else {}
    if isinstance(audit, dict):
        summary["response_time_seconds"] = audit.get("response_time_seconds")

    rt_val = summary.get("response_time_seconds")
    if not isinstance(rt_val, (int, float)) or float(rt_val) <= 0:
        detect = existing.get("detect") if isinstance(existing.get("detect"), dict) else {}
        act2 = existing.get("act") if isinstance(existing.get("act"), dict) else {}
        detected_at = None
        executed_at = None
        if isinstance(detect, dict):
            detected_at = detect.get("detected_at") or (detect.get("event") or {}).get("timestamp")
        if isinstance(act2, dict):
            executed_at = act2.get("executed_at")
        try:
            if detected_at and executed_at:
                start_ms = datetime.fromisoformat(str(detected_at).replace("Z", "+00:00")).timestamp() * 1000
                end_ms = datetime.fromisoformat(str(executed_at).replace("Z", "+00:00")).timestamp() * 1000
                summary["response_time_seconds"] = max(0, int(round((end_ms - start_ms) / 1000)))
        except Exception:
            pass
    existing["summary"] = summary

    upsert_workflow_report(payload.workflow_id, existing)
    return {"status": "ok", "workflow_id": payload.workflow_id, "stage": payload.stage}


@router.get("/api/workflow/reasoning/{workflow_id}")
async def api_workflow_reasoning(workflow_id: str, user=Depends(verify_firebase_or_local_token)) -> dict[str, Any]:
    _can_read_reasoning_stream(user, workflow_id)
    steps = read_reasoning_steps(workflow_id, limit=500)
    return {"workflow_id": workflow_id, "steps": steps}


@router.get("/api/workflow/reasoning/{workflow_id}/render")
async def api_workflow_reasoning_render(
    workflow_id: str, user=Depends(verify_firebase_or_local_token)
) -> dict[str, Any]:
    _can_read_reasoning_stream(user, workflow_id)

    if workflow_id in _render_cache:
        return {"workflow_id": workflow_id, "steps": _render_cache[workflow_id]}

    raw_steps = read_reasoning_steps(workflow_id, limit=500)
    if not raw_steps:
        return {"workflow_id": workflow_id, "steps": []}

    import json as _json
    import os as _os

    groq_key = _os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return {"workflow_id": workflow_id, "steps": raw_steps}

    try:
        from groq import AsyncGroq as _AsyncGroq
        _client = _AsyncGroq(api_key=groq_key)

        steps_payload = _json.dumps(
            [
                {
                    "agent": s.get("agent"),
                    "stage": s.get("stage"),
                    "status": s.get("status"),
                    "detail": s.get("detail"),
                    "output": s.get("output") or {},
                    "timestamp": s.get("timestamp"),
                }
                for s in raw_steps
            ],
            default=str,
        )

        prompt = (
            "You are a supply chain intelligence narrator for Praecantator, an autonomous SCRM platform. "
            "Below is a JSON array of agent reasoning steps from a live incident workflow. "
            "For EACH step, write a rich, detailed summary paragraph (at least 3-4 sentences) that deeply explains what the agent did, "
            "its findings, and the implications — in clean, precise, operator-facing English. Do not just output one line. "
            "DO NOT include any raw field mappings in the text (e.g., do not write 'recipient -> ...' or 'provider -> ...'). "
            "DO NOT mention internal technical names like 'Groq', 'SQLite', 'Firestore', 'Firebase', 'fallback', 'degraded mode', or any infrastructure detail. "
            "DO NOT use corporate jargon or passive voice. Be direct and informative. "
            "Return a JSON array with the same order as the input. Each element must have exactly these keys: "
            "\"agent\", \"stage\", \"status\", \"timestamp\", \"narrative\". "
            "The narrative key replaces the detail field with your clean, detailed prose. "
            "Return ONLY valid JSON — no markdown, no explanation, no code fences.\n\n"
            f"Input steps:\n{steps_payload}"
        )

        resp = await _client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            temperature=0.3,
        )
        raw_text = resp.choices[0].message.content or "[]"
        raw_text = raw_text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```", 2)[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.rsplit("```", 1)[0]

        rendered = _json.loads(raw_text.strip())

        merged: list[dict] = []
        for i, step in enumerate(raw_steps):
            overlay = rendered[i] if i < len(rendered) else {}
            merged.append({**step, "narrative": overlay.get("narrative", step.get("detail", ""))})

        _render_cache[workflow_id] = merged
        return {"workflow_id": workflow_id, "steps": merged}

    except Exception as exc:
        logger.warning(f"[reasoning/render] Groq enrichment failed: {exc} — returning raw steps")
        return {"workflow_id": workflow_id, "steps": raw_steps}


@router.get("/api/workflow/state/{workflow_id}")
async def api_workflow_state(workflow_id: str, user=Depends(verify_firebase_or_local_token)) -> dict[str, Any]:
    _assert_workflow_owner(user, workflow_id)
    checkpoint = get_workflow_checkpoint(workflow_id) or {}
    event = read_workflow_event(workflow_id) or {}
    state = checkpoint if checkpoint else event
    status = "waiting_human" if state.get("waiting_human") else ("complete" if state.get("current_stage") == "AUDIT" else "running")
    return {"workflow_id": workflow_id, "status": status, "state": state, "event": event}


@router.get("/api/workflow/report/{workflow_id}")
async def api_workflow_report_get(workflow_id: str, user=Depends(verify_firebase_or_local_token)) -> dict:
    _assert_workflow_owner(user, workflow_id)
    report = get_workflow_report(workflow_id)
    if not report:
        return {"workflow_id": workflow_id}
    return report


@router.get("/api/workflow/report/{workflow_id}/pdf")
async def api_workflow_report_pdf(workflow_id: str, request: Request, user=Depends(verify_firebase_or_local_token)) -> Response:
    _assert_workflow_owner(user, workflow_id)
    report = get_workflow_report(workflow_id)
    if not report:
        raise HTTPException(status_code=404, detail="Not Found")
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    rt_val = summary.get("response_time_seconds")
    if not isinstance(rt_val, (int, float)) or float(rt_val) <= 0:
        detect = report.get("detect") if isinstance(report.get("detect"), dict) else {}
        act = report.get("act") if isinstance(report.get("act"), dict) else {}
        detected_at = None
        executed_at = None
        if isinstance(detect, dict):
            detected_at = detect.get("detected_at") or (detect.get("event") or {}).get("timestamp")
        if isinstance(act, dict):
            executed_at = act.get("executed_at")
        try:
            if detected_at and executed_at:
                start_ms = datetime.fromisoformat(str(detected_at).replace("Z", "+00:00")).timestamp() * 1000
                end_ms = datetime.fromisoformat(str(executed_at).replace("Z", "+00:00")).timestamp() * 1000
                summary["response_time_seconds"] = max(0, int(round((end_ms - start_ms) / 1000)))
                report["summary"] = summary
                upsert_workflow_report(workflow_id, report)
        except Exception:
            pass
    user_id = str(user.get("sub") or "").strip()
    ctx = read_context(user_id)
    if not (isinstance(ctx, dict) and ctx):
        row = get_context(user_id) or {}
        try:
            ctx = json.loads(row.get("payload_json") or "{}") if isinstance(row, dict) else {}
        except Exception:
            ctx = {}
    profile = ctx.get("operator_profile") if isinstance(ctx, dict) and isinstance(ctx.get("operator_profile"), dict) else {}
    requested_by = str(profile.get("name") or "").strip()
    if profile.get("email"):
        requested_by = f"{requested_by} <{profile.get('email')}>".strip()
    if not requested_by or requested_by == "<None>":
        requested_by = user_id

    if not report.get("appendix_nlp"):
        try:
            from services.llm_analysis import generate_appendix_nlp
            report["appendix_nlp"] = await generate_appendix_nlp(report)
            upsert_workflow_report(workflow_id, report)
        except Exception as e:
            report["appendix_nlp"] = f"NLP Generation fallback failed completely: {e}"

    content = generate_workflow_audit_report_pdf(report, requested_by=requested_by)
    return Response(content=content, media_type="application/pdf")


@router.post("/api/workflow/routes")
async def api_workflow_routes(payload: RouteRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    return await workflow_routes(payload, user)


@router.post("/api/workflow/network")
async def api_save_network(payload: SCNetworkSaveRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    user_id = _assert_same_user(user, payload.user_id)
    nodes_dump = [n.model_dump() for n in payload.nodes]
    routes_dump = [r.model_dump() for r in payload.routes]
    graph_check = validate_network_graph(nodes_dump, routes_dump)
    if not graph_check.valid:
        raise HTTPException(status_code=422, detail={"message": "Invalid network graph", "errors": graph_check.errors})

    try:
        quota_manager.check_network_size(user_id, len(payload.nodes))
        quota_manager.enforce_rate_limit(user_id, "save_network")
    except Exception as e:
        raise HTTPException(status_code=429, detail=str(e))

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

    ctx["supply_chain_network"] = {
        "nodes": nodes_dump,
        "routes": routes_dump,
        "description": payload.description,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "node_count": len(payload.nodes),
        "route_count": len(payload.routes),
    }
    ctx["master_data_version"] = int((ctx.get("master_data_version") or 0)) + 1
    ctx["updated_at"] = datetime.now(timezone.utc).isoformat()

    write_context(user_id, ctx)
    _record_master_data_change(
        user_id,
        "network_graph_update",
        {
            "node_count": len(payload.nodes),
            "route_count": len(payload.routes),
            "warnings": graph_check.warnings,
            "master_data_version": ctx["master_data_version"],
        },
    )
    add_audit("sc_network_saved", user_id)

    return {
        "status": "ok",
        "user_id": user_id,
        "node_count": len(payload.nodes),
        "route_count": len(payload.routes),
        "saved_at": ctx["supply_chain_network"]["saved_at"],
    }


@router.get("/api/workflow/network/{user_id}")
async def api_get_network(user_id: str, user=Depends(verify_firebase_or_local_token)) -> dict:
    _assert_same_user(user, user_id)
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

    network = ctx.get("supply_chain_network") or {}
    return {
        "user_id": user_id,
        "network": network,
        "has_network": bool(network.get("nodes")),
    }


@router.post("/api/workflow/network/monitor")
async def api_network_monitor(payload: SCNetworkMonitorRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    _assert_same_user(user, payload.user_id)
    if not payload.nodes:
        return {"filtered_events": [], "total_scanned": len(payload.events), "intersection_count": 0}

    events_to_check = payload.events if payload.events else _api_risk_events()

    filtered: list[dict[str, Any]] = []
    escalated_unmapped: list[dict[str, Any]] = []

    for evt in events_to_check:
        try:
            evt_lat = float(evt.get("lat", 0) or 0)
            evt_lng = float(evt.get("lng", 0) or 0)
        except Exception:
            continue
        if evt_lat == 0 and evt_lng == 0:
            continue

        radius_km = _event_impact_radius_km(evt)
        matched_nodes: list[dict[str, Any]] = []

        for node in payload.nodes:
            try:
                dist = _haversine_km(evt_lat, evt_lng, float(node.lat), float(node.lng))
            except Exception:
                continue
            if dist <= radius_km:
                impact_type = "direct" if dist <= radius_km / 3 else "indirect"
                matched_nodes.append({
                    "node_id": node.id,
                    "node_name": node.name,
                    "node_type": node.type,
                    "distance_km": round(dist, 1),
                    "impact_type": impact_type,
                    "criticality": node.criticality,
                    "daily_throughput_usd": node.daily_throughput_usd,
                })

        if not matched_nodes:
            escalated_unmapped.append(
                {
                    "event_id": evt.get("id") or evt.get("signal_id") or "",
                    "title": evt.get("title") or evt.get("event_type") or "unknown_event",
                    "status": "UNMAPPED_SIGNAL",
                    "escalation_reason": "No network node match; manual entity resolution required.",
                }
            )
            continue

        max_crit_map = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        max_crit = max((max_crit_map.get(n["criticality"], 1) for n in matched_nodes), default=1)
        total_throughput_at_risk = sum(n["daily_throughput_usd"] for n in matched_nodes)

        filtered.append({
            **evt,
            "network_match": {
                "matched_nodes": matched_nodes,
                "matched_node_count": len(matched_nodes),
                "impact_radius_km": radius_km,
                "max_criticality_score": max_crit,
                "total_throughput_at_risk_usd": total_throughput_at_risk,
                "has_direct_impact": any(n["impact_type"] == "direct" for n in matched_nodes),
            }
        })

    sev_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    filtered.sort(
        key=lambda e: (
            sev_rank.get(str(e.get("severity", "LOW")).upper(), 1),
            float((e.get("network_match") or {}).get("total_throughput_at_risk_usd", 0)),
        ),
        reverse=True,
    )

    return {
        "filtered_events": filtered,
        "total_scanned": len(events_to_check),
        "intersection_count": len(filtered),
        "node_count": len(payload.nodes),
        "escalated_unmapped_signals": escalated_unmapped,
        "unmapped_count": len(escalated_unmapped),
    }
