from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from services.firebase_auth import verify_firebase_or_local_token
from services.data_registry import disruption_snapshot, data_registry_health_report
from services.firestore_store import (
    get_orchestration_run,
    list_orchestration_runs,
    get_workflow_report,
    upsert_workflow_report,
)
from ml.xgboost_model import MODEL_PATH
from routers.schemas import AgentChatRequest
from routers.helpers import (
    chatbot_manager,
    workflow_graph_manager,
    _enqueue_celery_task,
    _resolved_request_tenant,
    _assert_workflow_owner,
    _resolve_customer_id_for_user,
)

logger = logging.getLogger("routers.utility")
router = APIRouter(tags=["System Utilities"])


@router.get("/api/ping")
async def ping() -> dict:
    """Lightweight keepalive endpoint — no auth, no DB calls. Used by the frontend to prevent Render cold-starts."""
    return {"status": "ok"}


@router.get("/api/tasks/{task_id}")
async def api_task_status(task_id: str, user=Depends(verify_firebase_or_local_token)) -> dict:
    """Return Celery task status/result for async backend jobs."""
    try:
        from celery.result import AsyncResult
        from scheduler.celery_app import celery_app

        result = AsyncResult(task_id, app=celery_app)
        payload: dict[str, Any] = {
            "task_id": task_id,
            "status": result.status,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else False,
        }
        if result.ready():
            payload["result"] = result.result if result.successful() else str(result.result)
        return payload
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Task queue unavailable: {exc}")


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dataset": disruption_snapshot(),
        "dataset_health": data_registry_health_report(),
        "fallbacks": {"state_store": "firestore"},
        "xgboost_model_loaded": MODEL_PATH.exists(),
    }


@router.post("/api/agents/chat")
async def api_agents_chat(payload: AgentChatRequest, user=Depends(verify_firebase_or_local_token)) -> dict:
    if payload.workflow_id:
        _assert_workflow_owner(user, payload.workflow_id)
    result = await chatbot_manager.process_message(
        message=payload.message,
        workflow_id=payload.workflow_id,
        session_id=payload.session_id,
        context=payload.context,
    )

    wf = (payload.workflow_id or "").strip()
    report_output = result.outputs.get("reporting_agent")
    if wf and isinstance(report_output, dict) and report_output.get("markdown"):
        existing = get_workflow_report(wf) or {"workflow_id": wf}
        existing["chat_agent_report"] = report_output["markdown"]
        upsert_workflow_report(wf, existing)

    return {
        "conversation_id": result.conversation_id,
        "sequence": result.sequence,
        "route": result.route,
        "supervisor": result.supervisor,
        "outputs": result.outputs,
        "text": result.final_text,
    }


@router.get("/api/orchestration/runs")
async def api_orchestration_runs(entity_id: str | None = None, user=Depends(verify_firebase_or_local_token)) -> dict[str, Any]:
    tenant_id = _resolved_request_tenant(user)
    return {"runs": list_orchestration_runs(entity_id=entity_id, tenant_id=tenant_id, limit=200)}


@router.get("/api/orchestration/runs/{run_id}")
async def api_orchestration_run_get(run_id: str, user=Depends(verify_firebase_or_local_token)) -> dict[str, Any]:
    tenant_id = _resolved_request_tenant(user)
    run = get_orchestration_run(run_id, tenant_id=tenant_id)
    if not run:
        raise HTTPException(status_code=404, detail="Orchestration run not found")
    return run


@router.post("/api/orchestration/replay/workflow/{workflow_id}")
async def api_orchestration_replay_workflow(workflow_id: str, user=Depends(verify_firebase_or_local_token)) -> dict[str, Any]:
    _assert_workflow_owner(user, workflow_id)
    tenant_id = _resolve_customer_id_for_user(str(user.get("sub") or "").strip())
    return await workflow_graph_manager.replay_workflow(workflow_id, tenant_id=tenant_id)


@router.post("/api/orchestration/replay/autonomous/{run_id}")
async def api_orchestration_replay_autonomous(run_id: str, user=Depends(verify_firebase_or_local_token)) -> dict[str, Any]:
    tenant_id = _resolved_request_tenant(user)
    from agents.autonomous_pipeline import replay_autonomous_run
    return await replay_autonomous_run(run_id, tenant_id=tenant_id)
