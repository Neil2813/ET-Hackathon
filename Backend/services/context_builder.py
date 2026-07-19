from __future__ import annotations

import json
import logging
from typing import Any

from services.firestore_store import (
    get_incident,
    list_incidents,
    list_rfq_events,
    get_workflow_report,
    get_workflow_checkpoint,
)
from services.firestore import read_reasoning_steps
from services.governance_checkpoint import list_pending_checkpoints, governance_summary
from routers.helpers import (
    _context_payload_for_user,
    _context_suppliers_or_empty,
    _context_network_routes,
    _api_risk_events,
)

logger = logging.getLogger("services.context_builder")

class ContextBuilder:
    @staticmethod
    async def build_context(
        user_id: str,
        tenant_id: str,
        page: str,
        incident_id: str | None = None,
        supplier_id: str | None = None,
        route_id: str | None = None,
        workflow_id: str | None = None,
        filters: dict | None = None,
        selected_objects: list | None = None,
    ) -> dict[str, Any]:
        """
        Aggregate all available platform context based on active page and entities.
        Failures in sub-retrievals are caught and represented gracefully to avoid request failures.
        """
        context = {
            "page": page,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "filters": filters or {},
            "selected_objects": selected_objects or [],
        }

        # 1. KPIs Summary (Dashboard Context)
        try:
            suppliers = _context_suppliers_or_empty(user_id)
            risk_events = _api_risk_events()
            rfqs = list_rfq_events(limit=100)
            avg_exposure = 0.0
            if suppliers:
                avg_exposure = sum(s.get("exposureScore", 0.0) for s in suppliers) / len(suppliers)

            context["kpis"] = {
                "total_suppliers": len(suppliers),
                "active_risk_events": len(risk_events),
                "average_exposure_score": round(avg_exposure, 2),
                "rfqs_sent": len([r for r in rfqs if str(r.get("status", "")).lower() == "sent"]),
            }
        except Exception as exc:
            logger.warning("ContextBuilder: Failed to compile KPIs context: %s", exc)
            context["kpis"] = "Unavailable"

        # 2. Incident Context
        if incident_id:
            try:
                inc = get_incident(incident_id)
                if inc:
                    # Clean/scrub payload if it contains large json strings
                    context["active_incident"] = inc
                else:
                    context["active_incident"] = f"Incident ID {incident_id} not found."
            except Exception as exc:
                logger.error("ContextBuilder: Failed to fetch incident %s: %s", incident_id, exc)
                context["active_incident"] = "Error retrieving incident details."
        elif page in ("dashboard", "incidents", "incident-simulator"):
            try:
                recent_incidents = list_incidents(limit=10, tenant_id=tenant_id)
                context["recent_incidents"] = [{
                    "id": inc.get("id"),
                    "title": inc.get("title"),
                    "severity": inc.get("severity"),
                    "status": inc.get("status"),
                    "impact_exposure_usd": inc.get("impact_exposure_usd"),
                } for inc in recent_incidents]
            except Exception as exc:
                logger.warning("ContextBuilder: Failed to list recent incidents: %s", exc)

        # 3. Supplier Context
        if supplier_id:
            try:
                suppliers = _context_suppliers_or_empty(user_id)
                supplier = next((s for s in suppliers if str(s.get("id")) == str(supplier_id)), None)
                if supplier:
                    context["active_supplier"] = supplier
                else:
                    context["active_supplier"] = f"Supplier ID {supplier_id} not found in user context."
            except Exception as exc:
                logger.error("ContextBuilder: Failed to fetch supplier %s: %s", supplier_id, exc)
                context["active_supplier"] = "Error retrieving supplier details."
        elif page in ("dashboard", "network"):
            try:
                suppliers = _context_suppliers_or_empty(user_id)
                # Include top 5 high exposure suppliers
                sorted_suppliers = sorted(suppliers, key=lambda s: s.get("exposureScore", 0.0), reverse=True)
                context["top_suppliers"] = [{
                    "id": s.get("id"),
                    "name": s.get("name"),
                    "exposureScore": s.get("exposureScore"),
                    "country": s.get("country"),
                    "tier": s.get("tier"),
                } for s in sorted_suppliers[:5]]
            except Exception as exc:
                logger.warning("ContextBuilder: Failed to build network view context: %s", exc)

        # 4. Route Context
        if route_id:
            try:
                routes = _context_network_routes(user_id)
                route = next((r for r in routes if str(r.get("id")) == str(route_id) or str(r.get("route_id")) == str(route_id)), None)
                if route:
                    context["active_route"] = route
                else:
                    context["active_route"] = f"Route ID {route_id} not found."
            except Exception as exc:
                logger.error("ContextBuilder: Failed to fetch route %s: %s", route_id, exc)
                context["active_route"] = "Error retrieving route details."
        elif page in ("dashboard", "route-viewer"):
            try:
                routes = _context_network_routes(user_id)
                context["available_routes_summary"] = [
                    {
                        "id": r.get("id") or r.get("route_id"),
                        "origin": r.get("origin"),
                        "destination": r.get("destination"),
                        "mode": r.get("mode"),
                        "cost": r.get("cost_usd"),
                        "co2": r.get("co2_emissions_metric_tons"),
                    }
                    for r in routes[:5]
                ]
            except Exception as exc:
                logger.warning("ContextBuilder: Failed to compile routes summary: %s", exc)

        # 5. Governance / Workflow Context
        if workflow_id:
            try:
                report = get_workflow_report(workflow_id)
                checkpoint = get_workflow_checkpoint(workflow_id)
                steps = read_reasoning_steps(workflow_id, limit=20)
                context["active_workflow"] = {
                    "workflow_id": workflow_id,
                    "checkpoint": checkpoint or {},
                    "report": report or {},
                    "reasoning_steps": steps or []
                }
            except Exception as exc:
                logger.error("ContextBuilder: Failed to fetch workflow %s: %s", workflow_id, exc)
                context["active_workflow"] = "Error retrieving workflow/governance execution details."
        elif page in ("dashboard", "compliance"):
            try:
                pending = list_pending_checkpoints(tenant_id, limit=10)
                gov_sum = governance_summary(tenant_id)
                context["governance_status"] = {
                    "pending_checkpoints": [{
                        "id": c.get("id"),
                        "checkpoint_name": c.get("checkpoint_name"),
                        "status": c.get("status"),
                        "owner_role": c.get("owner_role"),
                    } for c in pending[:5]],
                    "summary": gov_sum or {}
                }
            except Exception as exc:
                logger.warning("ContextBuilder: Failed to compile governance context: %s", exc)

        # 6. Global Intelligence & RFQs Summary
        if page == "intelligence":
            try:
                context["active_risk_events"] = _api_risk_events()[:5]
            except Exception as exc:
                logger.warning("ContextBuilder: Failed to fetch risk events for intelligence: %s", exc)

        return context
