from __future__ import annotations

import os
import logging
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.firebase_auth import verify_firebase_or_local_token
from services.copilot_service import CopilotService
from services.conversation_service import ConversationService
from services.context_builder import ContextBuilder
from routers.helpers import _resolved_request_tenant

logger = logging.getLogger("routers.copilot")
router = APIRouter(tags=["AI Operations Copilot"])

class CopilotChatRequest(BaseModel):
    message: str
    page: str
    incidentId: str | None = None
    supplierId: str | None = None
    routeId: str | None = None
    workflowId: str | None = None
    tenantId: str | None = None
    filters: dict | None = None
    selectedObjects: list | None = None


@router.post("/api/copilot/chat")
async def api_copilot_chat(
    payload: CopilotChatRequest,
    user=Depends(verify_firebase_or_local_token)
):
    """
    Stream copilot responses using Server Sent Events (SSE).
    """
    user_id = str(user.get("sub") or "").strip()
    tenant_id = _resolved_request_tenant(user)

    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    async def event_generator():
        async for chunk in CopilotService.stream_chat(
            user_id=user_id,
            tenant_id=tenant_id,
            message=payload.message,
            page=payload.page,
            incident_id=payload.incidentId,
            supplier_id=payload.supplierId,
            route_id=payload.routeId,
            workflow_id=payload.workflowId,
            filters=payload.filters,
            selected_objects=payload.selectedObjects,
        ):
            yield chunk

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/api/copilot/history")
async def api_copilot_history(user=Depends(verify_firebase_or_local_token)):
    """
    Retrieve message history for the active conversation.
    """
    user_id = str(user.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    conversation_id = ConversationService.get_or_create_active_conversation(user_id)
    messages = ConversationService.get_conversation_messages(conversation_id)
    return {"conversation_id": conversation_id, "messages": messages}


@router.post("/api/copilot/clear")
async def api_copilot_clear(user=Depends(verify_firebase_or_local_token)):
    """
    Clear all message history in the user's active conversation.
    """
    user_id = str(user.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    conversation_id = ConversationService.get_or_create_active_conversation(user_id)
    ConversationService.clear_conversation(conversation_id)
    return {"status": "success", "message": "Conversation history cleared."}


@router.get("/api/copilot/suggestions")
async def api_copilot_suggestions(
    page: str = Query("dashboard"),
    user=Depends(verify_firebase_or_local_token)
):
    """
    Get dynamic context-aware suggestion chips based on the user's current page.
    """
    clean_page = str(page).strip().lower()
    
    if clean_page == "dashboard":
        suggestions = ["Executive Briefing", "Today's Incidents", "Risk Summary"]
    elif clean_page in ("incidents", "incident-simulator"):
        suggestions = ["Explain Incident", "Suggest Mitigation", "Generate Incident Report"]
    elif clean_page == "network":
        suggestions = ["Analyze Supplier", "Supplier Exposure", "Alternative Suppliers"]
    elif clean_page == "route-viewer":
        suggestions = ["Compare Routes", "Explain Route", "Optimize Route"]
    elif clean_page == "compliance":
        suggestions = ["Explain Decision", "Pending Approvals", "Policy Summary"]
    else:
        suggestions = ["Executive Briefing", "Today's Incidents", "Risk Summary"]

    return {"suggestions": suggestions}


@router.get("/api/copilot/context")
async def api_copilot_context(
    page: str,
    incidentId: str | None = None,
    supplierId: str | None = None,
    routeId: str | None = None,
    workflowId: str | None = None,
    user=Depends(verify_firebase_or_local_token)
):
    """
    Retrieve aggregated context. Disabled/hidden in production modes,
    accessible only in development for transparency.
    """
    dev_mode = os.getenv("DEV_MODE", "false").strip().lower() == "true"
    if not dev_mode:
        raise HTTPException(status_code=403, detail="Context endpoint is disabled in production environments.")

    user_id = str(user.get("sub") or "").strip()
    tenant_id = _resolved_request_tenant(user)

    context_data = await ContextBuilder.build_context(
        user_id=user_id,
        tenant_id=tenant_id,
        page=page,
        incident_id=incidentId,
        supplier_id=supplierId,
        route_id=routeId,
        workflow_id=workflowId,
    )
    return context_data
