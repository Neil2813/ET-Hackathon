from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Response

from services.firebase_auth import verify_firebase_or_local_token
from services.firestore_store import list_audit, get_audit, list_workflow_reports
from services.data_registry import registry
from currency.frankfurter import convert_cost
from pdf.certificate import generate_audit_certificate

logger = logging.getLogger("routers.audit")
router = APIRouter(tags=["Audit Log & Compliance"])


def _audit_numeric_id(value: str) -> int | None:
    raw = (value or "").strip()
    if raw.startswith("aud_"):
        raw = raw.replace("aud_", "", 1)
    try:
        return int(raw)
    except Exception:
        return None


@router.get("/audit/all")
async def audit_all(user=Depends(verify_firebase_or_local_token)) -> list[dict]:
    return list_audit(limit=100)


@router.get("/api/audit")
async def api_audit() -> list[dict]:
    rows = list_audit(limit=200)
    return [
        {
            "id": f"aud_{row['id']}",
            "action": row["action"],
            "payload": row.get("payload", ""),
            "event": row["action"],
            "suppliers": row.get("payload", ""),
            "decision": row["action"],
            "executedBy": "system",
            "timestamp": row["timestamp"],
            "durationMs": 0,
        }
        for row in rows
    ]


@router.get("/audit/certificate/{audit_id}")
async def audit_certificate(audit_id: str, user=Depends(verify_firebase_or_local_token)) -> Response:
    usd = float(registry.mode_cost_baseline.get("land", 7500.0))
    converted = await convert_cost(usd, "USD")
    lines = [
        "Observe -> Orient -> Decide -> Act completed",
        f"Estimated impact USD: {usd}",
        f"Converted impact: {converted['local']} {converted['currency']}",
    ]
    content = generate_audit_certificate(audit_id, user.get("sub", "local-user"), lines)
    return Response(content=content, media_type="application/pdf")


@router.get("/api/audit/{audit_id}/pdf")
async def api_audit_pdf(audit_id: str) -> Response:
    numeric = _audit_numeric_id(audit_id)
    if numeric is None:
        raise HTTPException(status_code=422, detail="Invalid audit id")
    row = get_audit(numeric)
    if not row:
        raise HTTPException(status_code=404, detail="Not Found")

    summary = [
        f"Event: {row.get('action', '')}",
        f"Timestamp: {row.get('timestamp', '')}",
        f"Payload: {row.get('payload', '')}",
    ]
    content = generate_audit_certificate(f"aud_{numeric}", "system", summary)
    return Response(content=content, media_type="application/pdf")


@router.get("/api/audit/export")
async def api_audit_export() -> Response:
    rows = list_audit(limit=200)
    lines: list[str] = []
    for r in rows:
        lines.append(f"[aud_{r.get('id')}] {r.get('timestamp')} — {r.get('action')} — {r.get('payload')}")
    content = generate_audit_certificate("audit_export", "system", lines)
    return Response(content=content, media_type="application/pdf")


@router.get("/api/audit/compliance")
async def api_audit_compliance() -> dict:
    reports = list_workflow_reports(limit=1000)
    response_times = []
    actions: dict[str, int] = {}
    for r in reports:
        summary = r.get("summary") if isinstance(r.get("summary"), dict) else {}
        rt = summary.get("response_time_seconds")
        if isinstance(rt, (int, float)):
            response_times.append(float(rt))
        action = str(summary.get("action_taken") or "unknown")
        actions[action] = actions.get(action, 0) + 1
    avg_rt = sum(response_times) / max(1, len(response_times))
    return {
        "total_workflows": len(reports),
        "avg_response_time_seconds": round(avg_rt, 1),
        "actions_breakdown": actions,
    }


@router.get("/api/workflows")
async def api_workflow_reports() -> list[dict]:
    return list_workflow_reports(limit=200)
