from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response

from services.firebase_auth import verify_firebase_or_local_token
from services.firestore_store import (
    add_audit,
    get_incident,
    list_audit,
    list_incidents,
    list_rfq_events,
    list_simulation_incidents,
)
from services.data_registry import data_registry_health_report
from services.event_bus import connection_count as ws_connection_count
from services.intelligence_gap_tracker import build_intelligence_gap_report
from services.authorization import Permission

from routers.helpers import (
    _context_suppliers,
    _api_risk_events,
    _network_graph,
    _cached_json,
    _set_cache_headers,
    _resolved_request_tenant,
    _require_incident_permission,
    _context_suppliers_or_empty,
    _context_payload_for_user,
    _context_payload_for_ar,
    _context_network_routes,
    _network_mode_availability,
    _ar_float,
    _ar_transport_mode,
    _ar_node_from_supplier,
    _ar_route_confidence,
    _event_impact_radius_km,
    _haversine_km,
)

logger = logging.getLogger("routers.analytics")
router = APIRouter(tags=["Analytics"])


@router.get("/api/dashboard/kpis")
async def api_dashboard_kpis(user=Depends(verify_firebase_or_local_token)) -> dict:
    user_id = str(user.get("sub") or "").strip()
    cache_key = f"kpis_{user_id}"

    async def produce_kpis():
        suppliers = _context_suppliers(user_id)
        events = _api_risk_events()
        rfqs = list_rfq_events(limit=500)
        return {
            "totalSuppliers": len(suppliers),
            "activeRiskEvents": len(events),
            "avgExposure": round(sum(s["exposureScore"] for s in suppliers) / max(1, len(suppliers)), 2),
            "rfqsSent": len([r for r in rfqs if str(r.get("status", "")).lower() == "sent"]),
        }

    return await _cached_json(cache_key, 15, produce_kpis)


@router.get("/api/dashboard/events")
async def api_dashboard_events() -> list[dict]:
    return await _cached_json("dashboard_events", 60, _api_risk_events)


@router.get("/api/dashboard/workflows")
async def api_dashboard_workflows() -> list[dict]:
    items: list[dict] = []
    for row in list_audit(limit=200):
        action = str(row.get("action", ""))
        if not action.startswith("workflow_"):
            continue
        payload = str(row.get("payload", ""))
        workflow_id = payload.split(":")[0] if ":" in payload else f"wf_{row.get('id')}"
        items.append(
            {
                "id": workflow_id,
                "title": action.replace("_", " ").title(),
                "description": payload or "Workflow event",
                "timestamp": row.get("timestamp"),
                "status": "active" if "updated" in action or "routes" in action else "complete",
            }
        )
    return items


@router.get("/api/dashboard/suppliers")
async def api_dashboard_suppliers(limit: int = 5, user=Depends(verify_firebase_or_local_token)) -> list[dict]:
    user_id = str(user.get("sub") or "").strip()
    suppliers = _context_suppliers(user_id)
    return suppliers[: max(1, int(limit))]


@router.get("/api/network/graph")
async def api_network_graph() -> dict[str, Any]:
    return _network_graph()


@router.get("/api/risks/events")
async def api_risks_events(region: str | None = None, severity: str | None = None) -> list[dict]:
    events = await api_dashboard_events()
    if severity:
        events = [e for e in events if e["severity"] == severity]
    if region:
        events = [e for e in events if e["region"] == region]
    return events


@router.get("/api/risks/suppliers")
async def api_risks_suppliers(
    tier: str | None = None,
    minScore: float | None = None,
    maxScore: float | None = None,
    user=Depends(verify_firebase_or_local_token),
) -> list[dict]:
    suppliers = await api_dashboard_suppliers(limit=5000, user=user)
    filtered = suppliers
    if tier:
        filtered = [s for s in filtered if s["tier"] == tier]
    if minScore is not None:
        filtered = [s for s in filtered if s["exposureScore"] >= float(minScore)]
    if maxScore is not None:
        filtered = [s for s in filtered if s["exposureScore"] <= float(maxScore)]
    return filtered


@router.get("/api/exposure/summary")
async def api_exposure_summary(user=Depends(verify_firebase_or_local_token)) -> dict:
    suppliers = _context_suppliers(str(user.get("sub") or "").strip())
    avg = sum(s["exposureScore"] for s in suppliers) / max(1, len(suppliers))
    critical = len([s for s in suppliers if s["exposureScore"] >= 75])
    return {"avgScore": round(avg, 1), "criticalNodes": critical, "totalMonitored": len(suppliers)}


@router.get("/api/exposure/suppliers")
async def api_exposure_suppliers(user=Depends(verify_firebase_or_local_token)) -> list[dict]:
    return await api_dashboard_suppliers(limit=5000, user=user)


@router.get("/exposure/all")
async def exposure_all(user=Depends(verify_firebase_or_local_token)) -> list[dict]:
    add_audit("exposure_all_read", user.get("sub", "local"))
    rows = _context_suppliers(str(user.get("sub") or "").strip())
    return [{"supplier_id": r["id"], "name": r["name"], "score": r["exposureScore"]} for r in rows]


@router.get("/exposure/{supplier_id}")
async def exposure_one(supplier_id: str, user=Depends(verify_firebase_or_local_token)) -> dict:
    rows = _context_suppliers(str(user.get("sub") or "").strip())
    selected = next((r for r in rows if r["id"] == supplier_id), None)
    if not selected:
        raise HTTPException(status_code=404, detail="Supplier not found")
    score = float(selected["exposureScore"])
    return {
        "supplier_id": supplier_id,
        "score": score,
        "breakdown": {
            "geo": round(min(1.0, score / 120), 3),
            "weather": round(min(1.0, score / 180), 3),
            "tier": round(min(1.0, score / 220), 3),
        },
        "requested_by": user.get("sub", "local"),
    }


@router.get("/api/ar/assets")
async def api_ar_assets(user=Depends(verify_firebase_or_local_token)) -> dict[str, Any]:
    """Globe-ready supply chain payload for the dashboard AR view."""
    user_id = str(user.get("sub") or "").strip()
    tenant_id = _resolved_request_tenant(user)
    ctx = _context_payload_for_ar(user_id, tenant_id)
    network = ctx.get("supply_chain_network") if isinstance(ctx.get("supply_chain_network"), dict) else {}

    raw_nodes = network.get("nodes") if isinstance(network, dict) else []
    raw_routes = network.get("routes") if isinstance(network, dict) else []
    nodes: list[dict[str, Any]] = []
    if isinstance(raw_nodes, list) and raw_nodes:
        for idx, item in enumerate(raw_nodes):
            if not isinstance(item, dict):
                continue
            nodes.append({
                "id": str(item.get("id") or f"node_{idx+1}"),
                "name": str(item.get("name") or item.get("label") or f"Node {idx+1}"),
                "type": str(item.get("type") or "supplier"),
                "tier": item.get("tier") if item.get("tier") else "Tier 2",
                "lat": _ar_float(item.get("lat")),
                "lng": _ar_float(item.get("lng")),
                "country": str(item.get("country") or ""),
                "criticality": str(item.get("criticality") or "medium").lower(),
                "exposureScore": _ar_float(item.get("exposureScore") or item.get("exposure_score"), 50),
                "daily_throughput_usd": _ar_float(item.get("daily_throughput_usd"), 100_000),
                "transport_modes": item.get("transport_modes") if isinstance(item.get("transport_modes"), dict) else {"sea": False, "air": False, "land": True},
            })
    else:
        suppliers = ctx.get("suppliers") if isinstance(ctx.get("suppliers"), list) else []
        nodes = [_ar_node_from_supplier(item, idx) for idx, item in enumerate(suppliers) if isinstance(item, dict)]

    nodes = [n for n in nodes if -90 <= n["lat"] <= 90 and -180 <= n["lng"] <= 180 and not (n["lat"] == 0 and n["lng"] == 0)]
    by_id = {n["id"]: n for n in nodes}

    routes: list[dict[str, Any]] = []
    if isinstance(raw_routes, list) and raw_routes:
        for idx, route in enumerate(raw_routes):
            if not isinstance(route, dict):
                continue
            from_id = str(route.get("from_node_id") or route.get("from") or route.get("source") or "")
            to_id = str(route.get("to_node_id") or route.get("to") or route.get("target") or "")
            from_node, to_node = by_id.get(from_id), by_id.get(to_id)
            if not from_node or not to_node:
                continue
            confidence = _ar_route_confidence(route, from_node, to_node)
            cost = _ar_float(route.get("cost_per_unit_usd") or route.get("cost_usd"), 2000)
            baseline_cost = _ar_float(route.get("baseline_cost_usd"), cost * 1.08)
            co2_delta = _ar_float(route.get("co2_delta_kg") or route.get("co2_delta"), 0)
            routes.append({
                "id": str(route.get("id") or f"route_{idx+1}"),
                "from_node_id": from_id,
                "to_node_id": to_id,
                "mode": _ar_transport_mode(route.get("mode")),
                "active": bool(route.get("active", True)),
                "confidence": confidence,
                "cost_usd": round(cost, 2),
                "cost_delta_usd": round(cost - baseline_cost, 2),
                "co2_delta_kg": round(co2_delta, 2),
                "startLat": from_node["lat"],
                "startLng": from_node["lng"],
                "endLat": to_node["lat"],
                "endLng": to_node["lng"],
            })
    elif len(nodes) > 1:
        hub = next((n for n in nodes if n["type"] in {"factory", "warehouse", "destination"}), nodes[0])
        for idx, node in enumerate(nodes):
            if node["id"] == hub["id"]:
                continue
            mode = _ar_transport_mode("air" if abs(node["lng"] - hub["lng"]) > 80 else next((m for m, ok in node["transport_modes"].items() if ok), "land"))
            routes.append({
                "id": f"route_{hub['id']}_{node['id']}",
                "from_node_id": hub["id"],
                "to_node_id": node["id"],
                "mode": mode,
                "active": True,
                "confidence": round(max(0.2, min(1.0, 1 - (_ar_float(node.get("exposureScore"), 50) / 140))), 2),
                "cost_usd": round(1200 + idx * 180, 2),
                "cost_delta_usd": round(-80 + idx * 12, 2),
                "co2_delta_kg": round((idx % 5 - 2) * 18.5, 2),
                "startLat": hub["lat"],
                "startLng": hub["lng"],
                "endLat": node["lat"],
                "endLng": node["lng"],
            })

    active_statuses = {"DETECTED", "ANALYZED", "AWAITING_APPROVAL"}
    operational_incidents = [
        inc for inc in list_incidents(status=None, limit=200, tenant_id=tenant_id)
        if str(inc.get("status") or "").upper() in active_statuses
    ]
    simulation_incidents = [
        inc for inc in list_simulation_incidents(status=None, limit=200, tenant_id=tenant_id)
        if str(inc.get("status") or "").upper() in active_statuses
    ]
    def _severity_rank(value: Any) -> int:
        sev = str(value or "").strip().upper()
        return {"CRITICAL": 4, "HIGH": 3, "ANALYZED": 2, "MODERATE": 2, "LOW": 1}.get(sev, 0)

    merged_by_id: dict[str, dict[str, Any]] = {}
    for inc in [*operational_incidents, *simulation_incidents]:
        inc_id = str(inc.get("id") or inc.get("incident_id") or "").strip()
        if not inc_id:
            continue
        existing = merged_by_id.get(inc_id)
        if existing is None:
            merged_by_id[inc_id] = inc
            continue
        existing_count = int(existing.get("affected_node_count") or 0)
        candidate_count = int(inc.get("affected_node_count") or 0)
        existing_nodes = existing.get("affected_nodes") if isinstance(existing.get("affected_nodes"), list) else []
        candidate_nodes = inc.get("affected_nodes") if isinstance(inc.get("affected_nodes"), list) else []
        existing_score = (existing_count, len(existing_nodes), _severity_rank(existing.get("severity")))
        candidate_score = (candidate_count, len(candidate_nodes), _severity_rank(inc.get("severity")))
        if candidate_score > existing_score:
            merged_by_id[inc_id] = inc
    active_incidents: list[dict[str, Any]] = list(merged_by_id.values())
    disruptions = []
    for inc in active_incidents:
        event_payload = inc.get("event") if isinstance(inc.get("event"), dict) else {}
        lat = (
            inc.get("lat") or inc.get("event_lat") or inc.get("latitude")
            or event_payload.get("lat") or event_payload.get("latitude")
        )
        lng = (
            inc.get("lng") or inc.get("event_lng") or inc.get("longitude")
            or event_payload.get("lng") or event_payload.get("longitude")
        )
        lat_f, lng_f = _ar_float(lat), _ar_float(lng)
        if lat_f == 0 and lng_f == 0:
            affected = inc.get("affected_suppliers") if isinstance(inc.get("affected_suppliers"), list) else []
            match = next((by_id.get(str(s.get("id") or s.get("supplier_id") or "")) for s in affected if isinstance(s, dict)), None)
            if not match:
                affected_nodes = inc.get("affected_nodes") if isinstance(inc.get("affected_nodes"), list) else []
                for node in affected_nodes:
                    if not isinstance(node, dict):
                        continue
                    node_id = str(node.get("node_id") or node.get("id") or "")
                    match = by_id.get(node_id)
                    if match:
                        break
            if match:
                lat_f, lng_f = match["lat"], match["lng"]
        if lat_f == 0 and lng_f == 0:
            candidates: list[tuple[float, float]] = []
            for node in (inc.get("affected_nodes") if isinstance(inc.get("affected_nodes"), list) else []):
                if not isinstance(node, dict):
                    continue
                nlat = _ar_float(node.get("lat") or node.get("latitude"))
                nlng = _ar_float(node.get("lng") or node.get("longitude"))
                if not (nlat == 0 and nlng == 0):
                    candidates.append((nlat, nlng))
            for sup in (inc.get("affected_suppliers") if isinstance(inc.get("affected_suppliers"), list) else []):
                if not isinstance(sup, dict):
                    continue
                slat = _ar_float(sup.get("lat") or sup.get("latitude"))
                slng = _ar_float(sup.get("lng") or sup.get("longitude"))
                if not (slat == 0 and slng == 0):
                    candidates.append((slat, slng))
            if candidates:
                lat_f = sum(c[0] for c in candidates) / len(candidates)
                lng_f = sum(c[1] for c in candidates) / len(candidates)
        if lat_f == 0 and lng_f == 0:
            continue
        disruptions.append({
            "id": str(inc.get("id") or inc.get("incident_id") or uuid4()),
            "title": str(inc.get("event_title") or inc.get("title") or "Active disruption"),
            "severity": str(inc.get("severity") or "HIGH").upper(),
            "lat": lat_f,
            "lng": lng_f,
            "radius_km": _event_impact_radius_km(inc),
            "exposure_usd": _ar_float(inc.get("total_exposure_usd"), 0),
            "min_stockout_days": _ar_float(inc.get("min_stockout_days"), 0),
            "affected_nodes": inc.get("affected_nodes") if isinstance(inc.get("affected_nodes"), list) else [],
            "affected_suppliers": inc.get("affected_suppliers") if isinstance(inc.get("affected_suppliers"), list) else [],
            "route_options": inc.get("route_options") if isinstance(inc.get("route_options"), list) else [],
        })

    return {
        "nodes": nodes,
        "routes": routes,
        "disruptions": disruptions,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/api/ws/status")
async def api_ws_status():
    """Returns the number of active WebSocket connections."""
    return {"active_connections": ws_connection_count()}


@router.get("/api/intelligence/gaps")
async def api_intelligence_gaps(user=Depends(verify_firebase_or_local_token)) -> dict[str, Any]:
    user_id = str(user.get("sub") or "").strip()
    context = _context_payload_for_user(user_id)
    return build_intelligence_gap_report(user_id=user_id, context=context)


@router.get("/api/data/health")
async def api_data_health(user=Depends(verify_firebase_or_local_token)) -> dict[str, Any]:
    return data_registry_health_report()
