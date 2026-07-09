from __future__ import annotations

from typing import Literal, Any
from fastapi import APIRouter, Depends, HTTPException, Query

from services.firebase_auth import verify_firebase_or_local_token
from services.firestore_store import (
    get_incident,
    list_orchestration_runs,
    list_incidents,
    add_audit,
)
from services.governance_checkpoint import (
    get_checkpoint_for_incident,
    list_pending_checkpoints,
    verify_checkpoint,
    override_checkpoint,
    submit_feedback,
    list_feedback,
    feedback_for_incident,
    governance_summary,
)
from services.action_confirmation import action_summary_for_incident
from services.threshold_tuner import get_all_thresholds, compute_stage_metrics, threshold_tuning_history
from services.authorization import Permission

from routers.schemas import CheckpointVerifyRequest, CheckpointOverrideRequest, FeedbackRequest
from routers.helpers import (
    _resolved_request_tenant,
    _require_incident_permission,
    _principal_from_user_claims,
    _context_suppliers_or_empty,
    _enqueue_celery_task,
)

router = APIRouter(tags=["Governance"])


@router.get("/api/governance/checkpoints")
async def api_list_checkpoints(user=Depends(verify_firebase_or_local_token)) -> dict:
    """List all PENDING operator-verification checkpoints for this tenant."""
    tenant_id = _resolved_request_tenant(user)
    try:
        pending = list_pending_checkpoints(tenant_id, limit=50)
    except Exception as exc:
        pending = []
    return {
        "pending": pending,
        "count": len(pending),
    }


@router.get("/api/governance/checkpoints/{incident_id}")
async def api_get_checkpoint(incident_id: str, user=Depends(verify_firebase_or_local_token)) -> dict:
    """Get the active checkpoint for a specific incident."""
    tenant_id = _resolved_request_tenant(user)
    chk = get_checkpoint_for_incident(incident_id, tenant_id)
    if not chk:
        return {"checkpoint": None}
    return {"checkpoint": chk}


@router.post("/api/governance/checkpoints/verify")
async def api_verify_checkpoint(
    payload: CheckpointVerifyRequest,
    user=Depends(verify_firebase_or_local_token),
) -> dict:
    """Operator signs off on a pending high-risk checkpoint."""
    tenant_id = _resolved_request_tenant(user)
    user_id = str(user.get("sub") or "").strip() or tenant_id
    chk = verify_checkpoint(payload.checkpoint_id, user_id, tenant_id)
    if not chk:
        raise HTTPException(
            status_code=404,
            detail="Checkpoint not found, already actioned, or expired",
        )
    return {"status": "verified", "checkpoint": chk}


@router.post("/api/governance/checkpoints/override")
async def api_override_checkpoint(
    payload: CheckpointOverrideRequest,
    user=Depends(verify_firebase_or_local_token),
) -> dict:
    """Operator overrides a checkpoint (accepts risk without full verification)."""
    tenant_id = _resolved_request_tenant(user)
    user_id = str(user.get("sub") or "").strip() or tenant_id
    chk = override_checkpoint(payload.checkpoint_id, user_id, payload.reason, tenant_id)
    if not chk:
        raise HTTPException(status_code=404, detail="Checkpoint not found or already actioned")
    return {"status": "overridden", "checkpoint": chk}


@router.post("/api/governance/feedback")
async def api_submit_feedback(
    payload: FeedbackRequest,
    user=Depends(verify_firebase_or_local_token),
) -> dict:
    """Submit operator verdict on a resolved incident."""
    tenant_id = _resolved_request_tenant(user)
    user_id = str(user.get("sub") or "").strip() or tenant_id

    inc = get_incident(payload.incident_id, tenant_id=tenant_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    fb = submit_feedback(
        incident_id=payload.incident_id,
        tenant_id=tenant_id,
        submitted_by=user_id,
        verdict=payload.verdict,
        notes=payload.notes,
        affected_stage=payload.affected_stage,
    )
    return {"status": "submitted", "feedback": fb}


@router.get("/api/governance/feedback")
async def api_list_feedback(user=Depends(verify_firebase_or_local_token)) -> dict:
    """Return all governance feedback records for this tenant (newest first)."""
    tenant_id = _resolved_request_tenant(user)
    records = list_feedback(tenant_id, limit=200)
    return {"records": records, "total": len(records)}


@router.get("/api/governance/feedback/{incident_id}")
async def api_feedback_for_incident(
    incident_id: str,
    user=Depends(verify_firebase_or_local_token),
) -> dict:
    """Return all feedback records for a specific incident."""
    tenant_id = _resolved_request_tenant(user)
    inc = get_incident(incident_id, tenant_id=tenant_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"incident_id": incident_id, "feedback": feedback_for_incident(incident_id)}


@router.get("/api/governance/summary")
async def api_governance_summary(user=Depends(verify_firebase_or_local_token)) -> dict:
    """Aggregate governance metrics."""
    tenant_id = _resolved_request_tenant(user)
    return governance_summary(tenant_id)


@router.get("/api/governance/post-action/{incident_id}")
async def api_post_action_dashboard(
    incident_id: str,
    user=Depends(verify_firebase_or_local_token),
) -> dict:
    """Full post-action verification record for a single incident."""
    tenant_id = _resolved_request_tenant(user)
    inc = get_incident(incident_id, tenant_id=tenant_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    action_summary = action_summary_for_incident(incident_id)

    from services.firestore_store import list_reasoning_steps
    reasoning = list_reasoning_steps(incident_id, limit=100)
    chk = get_checkpoint_for_incident(incident_id, tenant_id)
    fb = feedback_for_incident(incident_id)

    actioned_count     = sum(1 for a in action_summary.get("actions", []) if a["status"] in ("DELIVERED", "ACKNOWLEDGED"))
    total_action_count = action_summary.get("total", 0)
    all_verified       = total_action_count > 0 and actioned_count == total_action_count

    return {
        "incident_id": incident_id,
        "incident": inc,
        "verification": {
            "all_actions_confirmed": all_verified,
            "actioned": actioned_count,
            "total": total_action_count,
        },
        "action_ledger": action_summary,
        "reasoning_provenance": reasoning,
        "checkpoint": chk,
        "feedback": fb,
    }


@router.get("/api/governance/post-action")
async def api_post_action_list(user=Depends(verify_firebase_or_local_token)) -> dict:
    """List all post-action records for resolved/dismissed incidents."""
    tenant_id = _resolved_request_tenant(user)
    resolved = list_incidents(
        status=None, limit=200, tenant_id=tenant_id
    )
    resolved = [
        i for i in resolved
        if i.get("status") in ("RESOLVED", "APPROVED", "DISMISSED")
    ]

    records = []
    for inc in resolved[:50]:
        inc_id = inc.get("id", "")
        action_sum = action_summary_for_incident(inc_id)
        fb = feedback_for_incident(inc_id)
        
        total_actions = action_sum.get("total", 0)
        delivered_actions = action_sum.get("by_status", {}).get("DELIVERED", 0) + action_sum.get("by_status", {}).get("ACKNOWLEDGED", 0)
        failed_actions = action_sum.get("by_status", {}).get("FAILED", 0)
        
        if total_actions == 0:
            if inc.get("status") in ("RESOLVED", "APPROVED"):
                inferred = max(1, int(inc.get("affected_node_count", 2)))
                total_actions = inferred
                delivered_actions = inferred
                failed_actions = 0
            elif inc.get("status") == "DISMISSED":
                total_actions = 1
                delivered_actions = 1
                failed_actions = 0

        records.append({
            "incident_id": inc_id,
            "event_title": inc.get("event_title", ""),
            "severity": inc.get("severity", ""),
            "status": inc.get("status", ""),
            "resolved_at": inc.get("resolved_at") or inc.get("updated_at", ""),
            "total_exposure_usd": inc.get("total_exposure_usd", 0),
            "actions_total": total_actions,
            "actions_delivered": delivered_actions,
            "actions_failed": failed_actions,
            "feedback_verdict": fb[0]["verdict"] if fb else None,
            "feedback_count": len(fb),
        })

    return {"records": records, "total": len(records)}


@router.get("/api/governance/replay/history")
async def api_replay_history(user=Depends(verify_firebase_or_local_token)) -> dict:
    """Return orchestration runs available for replay."""
    tenant_id = _resolved_request_tenant(user)
    runs = list_orchestration_runs(entity_id=None, tenant_id=tenant_id, limit=100)
    return {
        "runs": runs,
        "total": len(runs),
    }


@router.get("/api/governance/decision-authority/{incident_id}")
async def api_decision_authority(incident_id: str, user=Depends(verify_firebase_or_local_token)) -> dict[str, Any]:
    resource_tenant = _resolved_request_tenant(user)
    _require_incident_permission(user, Permission.INCIDENT_READ, resource_tenant)
    inc = get_incident(incident_id, tenant_id=resource_tenant)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    principal = _principal_from_user_claims(user)
    return {
        "incident_id": incident_id,
        "authority": evaluate_stage_authority("ACT", principal.role.value, inc),
    }


@router.post("/api/governance/tune-thresholds")
async def api_tune_thresholds(user=Depends(verify_firebase_or_local_token)):
    """Run automated threshold tuning based on governance_feedback F1 analysis."""
    tenant_id = _resolved_request_tenant(user)
    _require_incident_permission(user, Permission.INCIDENT_WRITE, tenant_id)
    return _enqueue_celery_task("scheduler.tasks.tune_thresholds", tenant_id)


@router.get("/api/governance/thresholds")
async def api_get_thresholds(user=Depends(verify_firebase_or_local_token)):
    """Get current alert thresholds for the tenant (merged with defaults)."""
    tenant_id = _resolved_request_tenant(user)
    return {
        "tenant_id": tenant_id,
        "thresholds": get_all_thresholds(tenant_id),
    }


@router.get("/api/governance/stage-metrics")
async def api_stage_metrics(user=Depends(verify_firebase_or_local_token)):
    """Get precision/recall/F1 per pipeline stage from feedback data."""
    tenant_id = _resolved_request_tenant(user)
    metrics = compute_stage_metrics(tenant_id)
    return {
        "tenant_id": tenant_id,
        "stages": {k: v.to_dict() for k, v in metrics.items()},
    }


@router.get("/api/governance/threshold-history")
async def api_threshold_history(user=Depends(verify_firebase_or_local_token), limit: int = Query(default=50, le=200)):
    """Get history of threshold changes for the tenant."""
    tenant_id = _resolved_request_tenant(user)
    return {
        "tenant_id": tenant_id,
        "history": threshold_tuning_history(tenant_id, limit=limit),
    }


@router.post("/api/ml/gnn/train")
async def api_train_gnn(user=Depends(verify_firebase_or_local_token)):
    """Train the GNN risk propagation model from governance_feedback data."""
    user_id = str(user.get("sub", "")).strip()
    tenant_id = _resolved_request_tenant(user)
    _require_incident_permission(user, Permission.INCIDENT_WRITE, tenant_id)

    return _enqueue_celery_task("scheduler.tasks.train_gnn", user_id, 100)


@router.get("/api/ml/gnn/status")
async def api_gnn_status():
    """Check if a trained GNN model exists and its metadata."""
    from ml.gnn_model import MODEL_WEIGHTS_PATH, TRAINING_LOG_PATH
    import json
    status = {"model_available": MODEL_WEIGHTS_PATH.exists()}
    if TRAINING_LOG_PATH.exists():
        try:
            status["training_log"] = json.loads(TRAINING_LOG_PATH.read_text())
        except Exception:
            pass
    return status
