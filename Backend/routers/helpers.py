from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import time
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import HTTPException, Response

from services.firebase_auth import verify_firebase_or_local_token
from services.firestore import read_context, read_reasoning_steps, read_workflow_event, write_context, write_workflow_event
from services.data_registry import registry
from services.firestore_store import (
    add_audit,
    get_context,
    get_incident,
    get_workflow_report,
    get_workflow_checkpoint,
    list_signals,
    append_master_data_change,
    list_incidents,
    list_simulation_incidents,
    list_contexts,
    purge_stale_incidents,
)
from services.master_data_validator import validate_network_graph, validate_supplier_rows
from services.authorization import Permission, Principal, Role, policy
from services.decision_authority import evaluate_stage_authority
from services.data_quality_guard import assess_context_quality
from services.scenario_confidence import confidence_bounds
from services.cache_provider import cache_get_or_set
from managers.chatbot_manager import ChatbotManager
from workflows.langgraph_workflow import WorkflowGraphManager
from routers.schemas import OnboardingRequest, Coordinates

logger = logging.getLogger("routers.helpers")

# Singletons
chatbot_manager = ChatbotManager()
workflow_graph_manager = WorkflowGraphManager()

INCIDENT_LIST_LIMIT = 200
INCIDENT_SUMMARY_SCAN_LIMIT = 250
SIMULATION_LIST_LIMIT = 200

# ---------------------------------------------------------------------------
# Background purge helper — fires purge_stale_incidents at most once per
# 5 minutes per tenant so it never blocks a request path.
# ---------------------------------------------------------------------------
_PURGE_INTERVAL_S: float = 300.0  # 5 minutes
_last_purge_ts: dict[str, float] = {}


def _maybe_purge_stale(tenant_id: str) -> None:
    """Schedule purge_stale_incidents as a background task, rate-limited per tenant."""
    now = time.monotonic()
    last = _last_purge_ts.get(tenant_id, 0.0)
    if now - last < _PURGE_INTERVAL_S:
        return  # Already ran recently — skip
    _last_purge_ts[tenant_id] = now

    async def _run() -> None:
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: purge_stale_incidents(tenant_id=tenant_id, max_age_days=7)
            )
        except Exception as exc:
            logger.warning("Background purge_stale_incidents failed for %s: %s", tenant_id, exc)

    asyncio.ensure_future(_run())


def _enqueue_celery_task(task_name: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    try:
        from scheduler.celery_app import celery_app

        task = celery_app.send_task(task_name, args=args, kwargs=kwargs)
        return {"status": "queued", "task_id": task.id, "task_name": task_name}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Task queue unavailable: {exc}")


def _set_cache_headers(response: Response, *, public: bool, max_age: int = 30) -> None:
    scope = "public" if public else "private"
    response.headers["Cache-Control"] = f"{scope}, max-age={max_age}"


async def _cached_json(cache_key: str, ttl_seconds: int, producer) -> Any:
    return await cache_get_or_set(
        cache_key,
        producer,
        ttl_seconds=ttl_seconds,
    )


def _resolve_point(c: Coordinates) -> tuple[float, float]:
    if c.lat is not None and c.lng is not None:
        return c.lat, c.lng
    port = registry.find_port_by_city_country(c.city, c.country)
    if port:
        return port.lat, port.lng
    raise HTTPException(status_code=422, detail="Provide lat/lng or resolvable city+country in Dataset/ports.json")


def _scrub_context(payload: OnboardingRequest) -> dict[str, Any]:
    data = payload.model_dump()
    customer_id = str(data.get("customer_id") or "").strip()
    if not customer_id:
        basis = str(data.get("company_name") or payload.user_id).strip().lower().replace(" ", "-")
        customer_id = f"cust_{basis}" if basis else f"cust_{payload.user_id}"
    data["customer_id"] = customer_id
    data["gmail_oauth_token_present"] = bool(data.pop("gmail_oauth_token", None))
    if data.get("slack_webhook"):
        data["slack_webhook"] = "***redacted***"
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    return data


def _assert_same_user(user: dict[str, Any], requested_user_id: str) -> str:
    subject = str(user.get("sub") or "").strip()
    if not subject:
        raise HTTPException(status_code=401, detail="Missing user subject")
    if subject != str(requested_user_id or "").strip():
        raise HTTPException(status_code=403, detail="Cross-tenant access denied")
    return subject


def _parse_tier(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw in {"1", "tier 1", "t1"}:
        return "Tier 1"
    if raw in {"2", "tier 2", "t2"}:
        return "Tier 2"
    if raw in {"3", "tier 3", "t3"}:
        return "Tier 3"
    return "Tier 2"  # fallback instead of crashing


def _normalized_supplier_row(item: dict[str, Any], idx: int) -> dict[str, Any]:
    try:
        lat = float(item.get("lat", item.get("latitude", 0.0)) or 0.0)
        lng = float(item.get("lng", item.get("longitude", 0.0)) or 0.0)
    except (ValueError, TypeError):
        lat, lng = 0.0, 0.0

    if lat < -90 or lat > 90 or lng < -180 or lng > 180:
        lat, lng = 0.0, 0.0

    supplier_id = str(item.get("id") or item.get("supplier_id") or f"sup_{idx+1}").strip()
    exposure = float(item.get("exposureScore", item.get("exposure_score", 50.0)) or 0.0)
    
    mode_raw = str(item.get("mode") or item.get("transport_mode") or "land").strip().lower()
    if mode_raw not in {"sea", "air", "land", "rail", "multimodal"}:
        mode_raw = "land"

    return {
        "id": supplier_id,
        "name": str(item.get("name") or item.get("supplier_name") or supplier_id),
        "country": str(item.get("country") or ""),
        "location": str(item.get("location") or item.get("address") or ""),
        "tier": _parse_tier(item.get("tier")),
        "category": str(item.get("category") or "Supplier"),
        "exposureScore": exposure,
        "trend": _score_to_trend(exposure),
        "status": _score_to_status(exposure),
        "lat": lat,
        "lng": lng,
        "mode": mode_raw,
    }


def _context_payload_for_user(user_id: str) -> dict[str, Any]:
    fs = read_context(user_id)
    if isinstance(fs, dict) and fs:
        data = dict(fs)
        data.pop("user_id", None)
        data.pop("workflow_id", None)
        return data
    row = get_context(user_id) or {}
    try:
        payload = json.loads(row.get("payload_json") or "{}") if isinstance(row, dict) else {}
    except Exception:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _context_payload_for_ar(user_id: str, tenant_id: str) -> dict[str, Any]:
    """
    Resolve context for AR surfaces across legacy keying patterns.
    Priority:
    1) user_id
    2) tenant_id (when different)
    3) scan contexts for payload.customer_id == tenant_id
    """
    primary = _context_payload_for_user(user_id)
    if primary:
        return primary

    if tenant_id and tenant_id != user_id:
        by_tenant = _context_payload_for_user(tenant_id)
        if by_tenant:
            return by_tenant

    try:
        for row in list_contexts(limit=1000):
            try:
                payload = json.loads(row.get("payload_json") or "{}")
            except Exception:
                payload = {}
            if not isinstance(payload, dict):
                continue
            customer_id = str(payload.get("customer_id") or payload.get("company_name") or "").strip()
            if customer_id and customer_id == tenant_id:
                return payload
    except Exception:
        pass
    return {}


def _context_suppliers(user_id: str) -> list[dict[str, Any]]:
    payload = _context_payload_for_user(user_id)
    suppliers = payload.get("suppliers")
    if not isinstance(suppliers, list) or len(suppliers) == 0:
        raise HTTPException(status_code=422, detail="No customer suppliers configured")
    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(suppliers):
        if not isinstance(item, dict):
            continue
        normalized.append(_normalized_supplier_row(item, idx))
    if not normalized:
        raise HTTPException(status_code=422, detail="No valid customer suppliers available")
    return normalized


def _context_suppliers_or_empty(user_id: str) -> list[dict[str, Any]]:
    try:
        return _context_suppliers(user_id)
    except HTTPException as exc:
        if exc.status_code in {404, 422}:
            return []
        raise


def _context_network_routes(user_id: str) -> list[dict[str, Any]]:
    payload = _context_payload_for_user(user_id)
    network = payload.get("supply_chain_network") if isinstance(payload.get("supply_chain_network"), dict) else {}
    routes = network.get("routes") if isinstance(network, dict) else []
    if not isinstance(routes, list):
        return []
    return [r for r in routes if isinstance(r, dict)]


def _network_mode_availability(routes: list[dict[str, Any]]) -> dict[str, bool]:
    availability = {"sea": False, "air": False, "land": False, "hybrid": False, "tanker_vlcc": False, "tanker_suezmax": False}
    for route in routes:
        mode = str(route.get("mode") or "").strip().lower()
        if mode in availability:
            availability[mode] = True
    availability["hybrid"] = availability["sea"] and availability["land"]
    availability["tanker_vlcc"] = availability["tanker_vlcc"] or availability["sea"]
    availability["tanker_suezmax"] = availability["tanker_suezmax"] or availability["sea"]
    return availability


def _record_master_data_change(user_id: str, change_type: str, payload: dict[str, Any]) -> None:
    try:
        append_master_data_change(user_id, change_type, payload)
    except Exception as exc:
        logger.warning("Failed to record master data change for %s: %s", user_id, exc)


def _resolve_customer_id_for_user(user_id: str) -> str:
    context = _context_payload_for_user(user_id)
    customer_id = str(context.get("customer_id") or context.get("company_name") or "").strip()
    if not customer_id:
        raise HTTPException(status_code=422, detail="Missing customer ownership context")
    return customer_id


def _resolve_workflow_owner(workflow_id: str) -> tuple[str, str]:
    checkpoint = get_workflow_checkpoint(workflow_id) or {}
    if isinstance(checkpoint, dict):
        owner = str(checkpoint.get("user_id") or "").strip()
        customer_id = str(checkpoint.get("customer_id") or "").strip()
        if owner:
            return owner, customer_id
    report = get_workflow_report(workflow_id) or {}
    if isinstance(report, dict):
        owner = str(report.get("user_id") or "").strip()
        customer_id = str(report.get("customer_id") or "").strip()
        if owner:
            return owner, customer_id
    raise HTTPException(status_code=404, detail="Orphan workflow")


def _assert_workflow_owner(user: dict[str, Any], workflow_id: str) -> str:
    owner, workflow_customer_id = _resolve_workflow_owner(workflow_id)
    subject = _assert_same_user(user, owner)
    request_customer_id = _resolve_customer_id_for_user(subject)
    if workflow_customer_id and workflow_customer_id != request_customer_id:
        raise HTTPException(status_code=403, detail="Cross-tenant workflow access denied")
    return subject


def _can_read_reasoning_stream(user: dict[str, Any], workflow_id: str) -> str:
    if workflow_id.startswith(("inc_", "sim_")):
        tenant_id = _resolved_request_tenant(user)
        _require_incident_permission(user, Permission.INCIDENT_READ, tenant_id)
        incident = get_incident(workflow_id, tenant_id=tenant_id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        return tenant_id
    return _assert_workflow_owner(user, workflow_id)


def _build_synthetic_probe_supplier(signal: dict[str, Any], existing_suppliers: list[dict[str, Any]]) -> dict[str, Any]:
    signal_id = str(signal.get("id") or signal.get("signal_id") or "probe").strip() or "probe"
    title = str(signal.get("title") or signal.get("event_type") or "Selected signal").strip() or "Selected signal"
    location = str(signal.get("location") or "Signal impact zone").strip() or "Signal impact zone"
    lat = float(signal.get("lat") or 0.0)
    lng = float(signal.get("lng") or 0.0)
    severity_raw = float(signal.get("severity_raw") or signal.get("severity") or 5.0)
    transport_mode = str(signal.get("transport_mode") or "air").strip().lower()
    if transport_mode not in {"sea", "air", "land", "mixed"}:
        transport_mode = "air"

    throughput_total = 0.0
    country_candidates: list[str] = []
    for supplier in existing_suppliers:
        if not isinstance(supplier, dict):
            continue
        try:
            throughput_total += float(supplier.get("daily_throughput_usd") or 0.0)
        except (TypeError, ValueError):
            pass
        country = str(supplier.get("country") or "").strip()
        if country:
            country_candidates.append(country)
    avg_daily_throughput = throughput_total / max(1, len(existing_suppliers))
    probe_country = country_candidates[0] if country_candidates else str(signal.get("country") or "Synthetic")

    return {
        "id": f"synthetic_probe_{signal_id}",
        "supplier_id": f"synthetic_probe_{signal_id}",
        "name": f"Synthetic Probe Node · {title[:48]}",
        "location": location,
        "city": location,
        "country": probe_country,
        "lat": lat,
        "lng": lng,
        "tier": 1,
        "category": "Synthetic Monte Carlo probe",
        "transport_mode": transport_mode,
        "mode": transport_mode,
        "status": "High",
        "trend": "up",
        "exposureScore": min(95.0, max(55.0, severity_raw * 10.0)),
        "contract_value_usd": max(150_000.0, avg_daily_throughput * 18 or 250_000.0),
        "daily_throughput_usd": max(12_500.0, avg_daily_throughput or 25_000.0),
        "safety_stock_days": max(2, min(7, int(round(7.5 - min(severity_raw, 7.0) / 1.5)))),
        "lead_time_days": max(2, min(8, int(round(2.0 + severity_raw / 2.5)))),
        "criticality": "high",
        "single_source": True,
        "incoterm": "DAP",
        "tenant_overlay_applied": False,
        "is_backup": False,
        "is_synthetic_probe": True,
        "synthetic_probe_reason": "Created for Monte Carlo reality-check when no tenant suppliers intersect the selected signal.",
    }


def _validate_detect_inputs(selected_signal: dict[str, Any], affected_suppliers: list[dict[str, Any]]) -> None:
    if not isinstance(selected_signal, dict) or not selected_signal:
        raise HTTPException(status_code=422, detail="DETECT requires selected_signal")
    if not isinstance(selected_signal.get("lat"), (int, float)) or not isinstance(selected_signal.get("lng"), (int, float)):
        raise HTTPException(status_code=422, detail="DETECT requires signal geolocation")
    if not str(selected_signal.get("event_type") or selected_signal.get("title") or "").strip():
        raise HTTPException(status_code=422, detail="DETECT requires event context")
    if not isinstance(affected_suppliers, list) or len(affected_suppliers) == 0:
        raise HTTPException(status_code=422, detail="DETECT requires mapped affected suppliers")


def _principal_from_user_claims(user: dict[str, Any]) -> Principal:
    user_id = str(user.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user identity")
    tenant_id = _resolved_request_tenant(user)
    role_raw = str(user.get("role") or "admin").strip().lower()
    try:
        role = Role(role_raw)
    except Exception:
        role = Role.ADMIN
    return Principal(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        email=str(user.get("email") or ""),
        is_service_account=bool(user.get("service_account") or False),
    )


def _require_incident_permission(user: dict[str, Any], permission: Permission, resource_tenant_id: str) -> Principal:
    principal = _principal_from_user_claims(user)
    if not policy.check(principal, permission, resource_tenant_id=resource_tenant_id):
        raise HTTPException(status_code=403, detail=f"Missing permission: {permission.value}")
    return principal


def _safe_resource_tenant(user_id: str) -> str:
    try:
        return _resolve_customer_id_for_user(user_id)
    except Exception:
        return user_id


def _resolved_request_tenant(user: dict[str, Any]) -> str:
    user_id = str(user.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid user identity")
        
    resolved_tenant_id = _safe_resource_tenant(user_id)
    if resolved_tenant_id and resolved_tenant_id != user_id:
        return resolved_tenant_id

    if str(user.get("source") or "").strip() == "local-bypass":
        if resolved_tenant_id:
            return resolved_tenant_id

    claimed_tenant_id = str(user.get("tenant_id") or user.get("org_id") or "").strip()
    if claimed_tenant_id:
        return claimed_tenant_id

    dev_tenant_id = os.getenv("DEV_TENANT_ID", "").strip()
    if dev_tenant_id:
        return dev_tenant_id

    return user_id


def _onboarding_completeness_gaps(context: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    suppliers = context.get("suppliers") if isinstance(context.get("suppliers"), list) else []
    network = context.get("supply_chain_network") if isinstance(context.get("supply_chain_network"), dict) else {}
    nodes = network.get("nodes") if isinstance(network.get("nodes"), list) else []
    routes = network.get("routes") if isinstance(network.get("routes"), list) else []
    contacts_ok = bool(context.get("primary_contact_email") or context.get("primary_contact_name"))
    if len(suppliers) == 0:
        gaps.append("suppliers")
    if len(nodes) == 0:
        gaps.append("network_nodes")
    if len(routes) == 0:
        gaps.append("network_routes")
    if not contacts_ok:
        gaps.append("operator_contacts")
    has_tiered = any(str(s.get("tier") or "").strip().lower() in {"tier 1", "tier 2", "tier 3", "1", "2", "3"} for s in suppliers if isinstance(s, dict))
    if not has_tiered:
        gaps.append("tier_mapping")
    has_incoterm = any(bool(str(r.get("incoterm") or "").strip()) for r in routes if isinstance(r, dict))
    if not has_incoterm:
        gaps.append("incoterm_mapping")
    return gaps


def _assert_onboarding_readiness(user_id: str) -> None:
    context = _context_payload_for_user(user_id)
    gaps = _onboarding_completeness_gaps(context)
    if gaps:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Onboarding completeness gate failed; workflow start blocked.",
                "missing": gaps,
            },
        )


def _signal_corroboration_count(signal: dict[str, Any]) -> int:
    raw = signal.get("corroboration_count")
    if isinstance(raw, (int, float)):
        return int(raw)
    corroborated_by = signal.get("corroborated_by")
    if isinstance(corroborated_by, list):
        return max(0, len([x for x in corroborated_by if x]))
    return 0


def _signal_freshness_hours(signal: dict[str, Any]) -> float | None:
    timestamp = (
        signal.get("detected_at")
        or signal.get("timestamp")
        or signal.get("created_at")
    )
    if not timestamp:
        return None
    try:
        ts = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - ts).total_seconds() / 3600.0
    except Exception:
        return None


def _decision_evidence_status(signal: dict[str, Any]) -> dict[str, Any]:
    corroboration_count = _signal_corroboration_count(signal)
    freshness_hours = _signal_freshness_hours(signal)
    freshness_ok = freshness_hours is not None and freshness_hours <= 24
    corroboration_ok = corroboration_count >= 2
    return {
        "corroboration_count": corroboration_count,
        "freshness_hours": round(freshness_hours, 2) if isinstance(freshness_hours, (int, float)) else None,
        "corroboration_ok": corroboration_ok,
        "freshness_ok": freshness_ok,
        "actionable": bool(corroboration_ok and freshness_ok),
    }


def _severity_to_score(label: str) -> float:
    mapping = {"critical": 90.0, "high": 75.0, "medium": 50.0, "low": 25.0}
    return mapping.get((label or "").strip().lower(), 45.0)


def _score_to_status(score: float) -> str:
    if score >= 85:
        return "Critical"
    if score >= 70:
        return "High"
    if score >= 45:
        return "Medium"
    return "Low"


def _score_to_trend(score: float) -> str:
    if score >= 70:
        return "up"
    if score <= 35:
        return "down"
    return "stable"


def _parsed_signals(limit: int = 200) -> list[dict[str, Any]]:
    rows = list_signals(limit=limit)
    parsed: list[dict[str, Any]] = []
    for row in rows:
        try:
            payload = json.loads(row.get("payload_json") or "{}")
            if isinstance(payload, dict):
                payload.setdefault("signal_id", row.get("signal_id"))
                payload.setdefault("created_at", row.get("created_at"))
                parsed.append(payload)
        except Exception:
            continue
    return parsed


def _dataset_suppliers(limit: int = 50) -> list[dict[str, Any]]:
    suppliers: list[dict[str, Any]] = []
    for idx, port in enumerate(registry.ports[: max(1, limit)]):
        exposure = round(25 + ((abs(port.lat) + abs(port.lng)) % 70), 1)
        # Alternate modes (sea, air, land) for demonstration
        modes = ["sea", "air", "land"]
        in_mode = modes[idx % len(modes)]
        suppliers.append(
            {
                "id": f"sup_{idx + 1}",
                "name": f"{port.city} Node",
                "country": port.country,
                "location": f"{port.city}, {port.country}",
                "tier": f"Tier {(idx % 3) + 1}",
                "category": "Logistics",
                "exposureScore": exposure,
                "trend": _score_to_trend(exposure),
                "status": _score_to_status(exposure),
                "lat": port.lat,
                "lng": port.lng,
                "mode": in_mode,
            }
        )
    return suppliers


def _api_risk_events() -> list[dict]:
    # Imports hoisted out of the loop to avoid repeated module lookups.
    from services.event_freshness import extract_event_timestamp, is_event_fresh
    from services.signal_geocode import geocode_signal

    events: list[dict] = []
    for idx, sig in enumerate(_parsed_signals(limit=500)):
        severity_value = float(sig.get("severity", 0) or 0)
        severity_label = "LOW"
        if severity_value >= 8:
            severity_label = "CRITICAL"
        elif severity_value >= 6:
            severity_label = "HIGH"
        elif severity_value >= 4:
            severity_label = "MEDIUM"

        sig = geocode_signal(sig)
        title_str = str(sig.get("title") or sig.get("event_type") or "Disruption signal")
        desc_str = str(sig.get("description") or sig.get("location") or "Signal-derived event")

        if not is_event_fresh(sig, max_event_days=30):
            continue
        event_ts = extract_event_timestamp(sig)
        ts = event_ts.isoformat() if event_ts else str(sig.get("created_at") or datetime.now(timezone.utc).isoformat())

        # Infer mode from content if not present
        inferred_mode = str(sig.get("mode") or "").lower()
        if not inferred_mode:
            content = (title_str + " " + desc_str).lower()
            if any(k in content for k in ["sea", "port", "ship", "vessel", "maritime", "ocean"]):
                inferred_mode = "sea"
            elif any(k in content for k in ["air", "flight", "plane", "airport", "aviation"]):
                inferred_mode = "air"
            elif any(k in content for k in ["road", "truck", "rail", "land", "highway", "border"]):
                inferred_mode = "land"
            else:
                inferred_mode = "land"

        events.append(
            {
                "id": str(sig.get("id") or sig.get("signal_id") or f"evt_{idx+1}"),
                "title": title_str,
                "event_type": str(sig.get("event_type") or "signal"),
                "severity": severity_label,
                "severity_raw": severity_value,
                "description": desc_str,
                "timestamp": ts,
                "analyst": str(sig.get("source") or "signal-pipeline"),
                "source": str(sig.get("source") or "signal-pipeline"),
                "source_category": str(sig.get("source_category") or ""),
                "lat": float(sig.get("lat", 0) or 0),
                "lng": float(sig.get("lng", 0) or 0),
                "location_precision": str(sig.get("location_precision") or "exact"),
                "region": str(sig.get("region") or sig.get("location") or "Unknown"),
                "url": _normalized_url(str(sig.get("url") or "")),
                "mode": inferred_mode,
                "supplier_id": str(sig.get("supplier_id") or sig.get("node_id") or ""),
            }
        )
    return [e for e in events if e["lat"] != 0 or e["lng"] != 0]


def _normalized_url(raw: str | None) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if "." in value:
        return f"https://{value}"
    return ""


def _region_from_lat_lng(lat: float, lng: float) -> str:
    if lng < -30:
        if lat >= 37:
            return "northeast"
        if lat >= 30:
            return "midwest"
        return "south"
    return "west"


def _network_graph(limit_ports: int = 20, limit_airports: int = 20) -> dict[str, Any]:
    hubs: list[dict[str, Any]] = []

    for idx, port in enumerate(registry.ports[: max(1, limit_ports)]):
        hubs.append(
            {
                "id": f"port_{idx+1}",
                "city": port.city,
                "lng": float(port.lng),
                "lat": float(port.lat),
                "type": "primary" if idx < 8 else "secondary",
                "shipments": int(200 + ((idx * 37) % 1200)),
                "region": _region_from_lat_lng(float(port.lat), float(port.lng)),
            }
        )

    airport_added = 0
    for ap in registry.airports:
        if airport_added >= limit_airports:
            break
        try:
            lat = float(ap.get("lat"))
            lng = float(ap.get("lon"))
        except Exception:
            continue
        city = str(ap.get("city") or ap.get("name") or "Airport")
        hubs.append(
            {
                "id": f"airport_{airport_added+1}",
                "city": city,
                "lng": lng,
                "lat": lat,
                "type": "secondary",
                "shipments": int(150 + ((airport_added * 29) % 900)),
                "region": _region_from_lat_lng(lat, lng),
            }
        )
        airport_added += 1

    routes: list[dict[str, Any]] = []
    for i in range(len(hubs)):
        for j in range(i + 1, min(i + 4, len(hubs))):
            mode = "air" if ("airport_" in hubs[i]["id"] or "airport_" in hubs[j]["id"]) else "ground"
            shipments = int((hubs[i]["shipments"] + hubs[j]["shipments"]) / 6)
            delayed = (i + j) % 7 == 0
            routes.append(
                {
                    "from": hubs[i]["id"],
                    "to": hubs[j]["id"],
                    "mode": mode,
                    "shipments": shipments,
                    "status": "delayed" if delayed else "active",
                }
            )

    return {"hubs": hubs, "routes": routes}


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in km."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _event_impact_radius_km(event: dict) -> float:
    """Return the geospatial impact radius of an event based on its type."""
    title = str(event.get("title", "") or event.get("type", "")).lower()
    if any(w in title for w in ("cyclone", "typhoon", "hurricane")): return 400
    if "earthquake" in title: return 250
    if "flood" in title: return 150
    if any(w in title for w in ("wildfire", "fire")): return 80
    if any(w in title for w in ("strike", "congestion")): return 50
    if any(w in title for w in ("war", "conflict", "geopolit")): return 300
    if any(w in title for w in ("port", "shipping")): return 80
    return 150


def _ar_float(value: Any, default: float = 0.0) -> float:
    try:
        n = float(value)
        return n if -1e12 < n < 1e12 else default
    except Exception:
        return default


def _ar_transport_mode(raw: Any) -> str:
    mode = str(raw or "").strip().lower()
    if mode in {"sea", "ocean", "ship", "maritime"}:
        return "sea"
    if mode in {"air", "flight", "aviation"}:
        return "air"
    if mode in {"land", "ground", "road", "rail", "truck"}:
        return "land"
    return "land"


def _ar_route_confidence(route: dict[str, Any], from_node: dict[str, Any] | None, to_node: dict[str, Any] | None) -> float:
    explicit = route.get("confidence") or route.get("confidence_score") or route.get("reliability")
    if explicit is not None:
        return max(0.1, min(1.0, _ar_float(explicit, 0.75)))
    criticality_penalty = {"critical": 0.2, "high": 0.14, "medium": 0.08, "low": 0.02}
    route_penalty = 0.06 if route.get("is_primary") is False else 0.0
    node_penalty = max(
        criticality_penalty.get(str((from_node or {}).get("criticality") or "").lower(), 0.08),
        criticality_penalty.get(str((to_node or {}).get("criticality") or "").lower(), 0.08),
    )
    return round(max(0.15, min(1.0, 0.92 - node_penalty - route_penalty)), 2)


def _ar_node_from_supplier(item: dict[str, Any], idx: int) -> dict[str, Any]:
    node = _normalized_supplier_row(item, idx)
    return {
        "id": node["id"],
        "name": node["name"],
        "type": "supplier",
        "tier": node["tier"],
        "lat": node["lat"],
        "lng": node["lng"],
        "country": node["country"],
        "criticality": "critical" if node["exposureScore"] >= 75 else "high" if node["exposureScore"] >= 60 else "medium",
        "exposureScore": node["exposureScore"],
        "daily_throughput_usd": _ar_float(item.get("daily_throughput_usd"), 100_000),
        "transport_modes": {"sea": node["mode"] == "sea", "air": node["mode"] == "air", "land": node["mode"] == "land"},
    }
