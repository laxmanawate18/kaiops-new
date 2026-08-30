from fastapi import APIRouter, HTTPException, Depends, Query, Body
from fastapi.responses import StreamingResponse
import json
from typing import Optional, Dict, Any
from app.auth.dependencies import get_current_user
from app.auth.models import UserResponse, UserRole
from .models import (
    CreateSessionRequest, CreateSessionResponse,
    SendMessageRequest, SendMessageResponse,
    GetMessagesResponse, GetSessionsResponse,
    UpdateSessionRequest, DeleteSessionResponse,
    ChatStatsResponse, ChatSession, ChatMessage, MessageSender
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_db():
    from app.chat.agent_service import get_session_service
    return get_session_service()

# ==================== Session Management ====================

@router.post("/sessions", response_model=CreateSessionResponse, status_code=201)
async def create_session(
    request: CreateSessionRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    try:
        session = _get_db().create_api_session(
            user_id=current_user.id,
            session_name=request.name
        )
        return CreateSessionResponse(
            session=ChatSession(**session),
            message="Session created successfully"
        )
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.get("/sessions", response_model=GetSessionsResponse)
async def get_sessions(
    include_inactive: bool = Query(True, description="Include inactive sessions"),
    current_user: UserResponse = Depends(get_current_user)
):
    try:
        user_sessions = _get_db().get_user_sessions(
            user_id=current_user.id,
            include_inactive=include_inactive
        )
        sessions = user_sessions
        # Admins/team-leads also see the autonomous (RCA/runtime) sessions that the
        # background worker created. These are surfaced in the left panel so the
        # Slack console deep-links resolve to a real conversation instead of 404.
        # Runtime sessions are given priority so the most recent RCA (from the
        # Slack deep-link) appears at/near the top of the panel.
        if current_user.role in (UserRole.ADMIN, UserRole.TEAM_LEAD):
            runtime = _get_db().get_runtime_sessions(limit=50)
            seen = {s.get("id") for s in user_sessions}
            runtime_only = [s for s in runtime if s.get("id") not in seen]
            # Newest runtime first (they're already sorted desc by last_modified).
            sessions = runtime_only + user_sessions
        return GetSessionsResponse(
            sessions=[ChatSession(**s) for s in sessions],
            total=len(sessions)
        )
    except Exception as e:
        logger.error(f"Error getting sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get sessions: {str(e)}")


@router.get("/sessions/{session_id}", response_model=ChatSession)
async def get_session(
    session_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    # Admins/team leads may open autonomous (runtime) sessions read-only, e.g.
    # the console deep-link posted to Slack after an RCA. Regular users are still
    # restricted to sessions they own.
    allow_runtime = current_user.role in (UserRole.ADMIN, UserRole.TEAM_LEAD)
    session = _get_db().get_api_session(current_user.id, session_id, allow_runtime=allow_runtime)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found or access denied")
    return ChatSession(**session)


@router.patch("/sessions/{session_id}", response_model=ChatSession)
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    session = _get_db().update_session(
        user_id=current_user.id,
        session_id=session_id,
        **request.dict(exclude_none=True)
    )
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found or access denied")
    return ChatSession(**session)


@router.delete("/sessions/{session_id}", response_model=DeleteSessionResponse)
async def delete_session(
    session_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    success = _get_db().delete_api_session(current_user.id, session_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found or access denied")
    return DeleteSessionResponse(session_id=session_id, message="Session deleted successfully")


@router.delete("/sessions", response_model=dict)
async def delete_all_sessions(current_user: UserResponse = Depends(get_current_user)):
    count = _get_db().delete_all_user_sessions(current_user.id)
    return {"message": f"Deleted {count} sessions", "deleted_count": count}


# ==================== Message Management ====================

@router.post("/messages", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    current_user: UserResponse = Depends(get_current_user)
):
    if not (request.message or "").strip():
        raise HTTPException(status_code=422, detail="message cannot be empty")
    try:
        user_message = _get_db().add_message(
            user_id=current_user.id,
            session_id=request.session_id,
            sender=MessageSender.USER,
            text=request.message,
            metadata=request.metadata
        )
        if not user_message:
            raise HTTPException(status_code=404, detail=f"Session {request.session_id} not found or access denied")
        
        from app.chat.agent_service import process_message
        agent_result = await process_message(
            message=request.message,
            session_id=request.session_id,
            user_id=current_user.id,
            metadata=request.metadata
        )
        
        agent_response_text = agent_result["response"]
        agent_metadata = agent_result.get("metadata", {})
        
        agent_message = _get_db().add_message(
            user_id=current_user.id,
            session_id=request.session_id,
            sender=MessageSender.ASSISTANT,
            text=agent_response_text,
            metadata=agent_metadata
        )
        
        return SendMessageResponse(
            user_message=ChatMessage(**user_message),
            agent_message=ChatMessage(**agent_message) if agent_message else None,
            session_id=request.session_id,
            success=True
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return SendMessageResponse(
            user_message=None,
            agent_message=None,
            session_id=request.session_id,
            success=False,
            error_message=f"Failed to send message: {str(e)}"
        )


@router.post("/sessions/{session_id}/stream")
async def stream_message_endpoint(
    session_id: str,
    request: Dict[str, Any] = Body(...),
    current_user: UserResponse = Depends(get_current_user)
):
    # session_id comes from the path; the body only needs {message, metadata?}.
    message = (request or {}).get("message", "")
    metadata = (request or {}).get("metadata")
    if not message:
        raise HTTPException(status_code=422, detail="message is required")

    # Verify session ownership first (404 if not found), matching existing patterns
    session = _get_db().get_api_session(current_user.id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found or access denied")

    async def event_generator():
        from app.chat.agent_service import stream_message
        try:
            async for chunk in stream_message(message, session_id, current_user.id, metadata):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            logger.error(f"Error streaming message: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error_message': str(e)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive"
        }
    )


@router.post("/sessions/{session_id}/messages", response_model=ChatMessage, status_code=201)
async def add_message_to_session(
    session_id: str,
    request: Dict[str, Any] = Body(...),
    current_user: UserResponse = Depends(get_current_user)
):
    try:
        text = request.get("text")
        sender_str = request.get("sender", "user")
        metadata = request.get("metadata")
        
        if not text:
            raise HTTPException(status_code=400, detail="Message text is required")
        
        try:
            sender = MessageSender(sender_str)
        except ValueError:
            sender = MessageSender.USER
        
        message = _get_db().add_message(
            user_id=current_user.id,
            session_id=session_id,
            sender=sender,
            text=text,
            metadata=metadata
        )
        if not message:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found or access denied")
        return ChatMessage(**message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to add message: {str(e)}")


@router.get("/sessions/{session_id}/messages", response_model=GetMessagesResponse)
async def get_messages(
    session_id: str,
    limit: Optional[int] = Query(None, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: UserResponse = Depends(get_current_user)
):
    # Admins/team leads may read messages of autonomous (runtime) sessions so the
    # Slack console deep-link renders the RCA conversation.
    allow_runtime = current_user.role in (UserRole.ADMIN, UserRole.TEAM_LEAD)
    messages, total = _get_db().get_messages(
        user_id=current_user.id,
        session_id=session_id,
        limit=limit,
        offset=offset,
        allow_runtime=allow_runtime
    )
    if messages is None and total == 0:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found or access denied")
    
    return GetMessagesResponse(
        session_id=session_id,
        messages=[ChatMessage(**m) for m in messages],
        total=total
    )


# ==================== HITL Approval Gate ====================

# Whitelist registry of guarded tools that may be executed via /approve.
# Only tools listed here can ever be executed by an approval token.
TOOL_REGISTRY = {
    "restart_pod": None,          # populated lazily below
    "rollback_application": None,
    "sync_application": None,
}


def _get_tool_registry() -> Dict[str, Any]:
    """Lazily import and cache the real guarded tool callables."""
    if TOOL_REGISTRY["restart_pod"] is None:
        from agents.gcp_rca_agent.tools import restart_pod
        from agents.argocd_agent.tools import rollback_application, sync_application
        TOOL_REGISTRY["restart_pod"] = restart_pod
        TOOL_REGISTRY["rollback_application"] = rollback_application
        TOOL_REGISTRY["sync_application"] = sync_application
    return TOOL_REGISTRY


def _persist_messages(session_id: str, user_id: str, user_text: str, assistant_text: str, metadata: Dict[str, Any]):
    db = _get_db()
    db.add_message(user_id=user_id, session_id=session_id, sender=MessageSender.USER, text=user_text)
    assistant_message = db.add_message(
        user_id=user_id, session_id=session_id,
        sender=MessageSender.ASSISTANT, text=assistant_text, metadata=metadata
    )
    return assistant_message


@router.post("/sessions/{session_id}/approve", response_model=SendMessageResponse)
async def approve_action_endpoint(
    session_id: str,
    body: Dict[str, Any] = Body(...),
    current_user: UserResponse = Depends(get_current_user)
):
    """Execute the exact pending action identified by approval_token (single-use)."""
    token = (body or {}).get("approval_token")
    if not token:
        raise HTTPException(status_code=422, detail="approval_token is required")

    from app.chat.pending_actions import get_pending, consume_pending, reject_pending
    # Binding checks BEFORE consuming the single-use token so a failed
    # cross-user/cross-session attempt can no longer burn someone else's
    # pending action (previously consume-first made the token unrejectable).
    record = get_pending(token)
    if not record:
        raise HTTPException(status_code=404, detail="No pending action for this token")
    # Deliberately uniform 404 for any binding mismatch: avoids leaking token
    # existence and removes the earlier asymmetric 403-vs-404 behavior.
    if record.get("session_id") != session_id or record.get("user_id") != current_user.id:
        raise HTTPException(status_code=404, detail="No pending action for this token")

    tool_name = record.get("tool_name")
    registry = _get_tool_registry()
    func = registry.get(tool_name)
    if func is None:
        raise HTTPException(status_code=400, detail=f"Tool '{tool_name}' is not an approvable action")

    consumed = consume_pending(token)
    if not consumed:
        raise HTTPException(status_code=404, detail="No pending action for this token")

    # Kill the actionable card in stored history so a refetch never shows a
    # second live approval for an already-consumed token.
    _get_db().resolve_gate_message(session_id, token, "approved")

    args = dict(record.get("args") or {})
    try:
        result = await func(**args) if args else await func()
    except TypeError as te:
        raise HTTPException(status_code=400, detail=f"Missing required arguments for {tool_name}: {te}")
    except Exception as e:
        result = f"Execution failed: {e}"

    # Ground the executed outcome INSIDE the ADK session so subsequent turns
    # know the action already ran — otherwise "approved, please proceed"
    # follow-ups re-trigger the gated tool endlessly.
    try:
        from google.genai.types import Content as GenaiContent, Part as GenaiPart
        from google.adk.events import Event as AdkEvent

        adk_session = await _get_db().get_session(
            app_name="kaiops", user_id=current_user.id, session_id=session_id
        )
        if adk_session:
            sys_note = (
                f"[SYSTEM] Guarded tool '{tool_name}' was APPROVED by the user and "
                f"has ALREADY been executed out-of-band. Result:\n{result}\n"
                "Do NOT call this tool again for this request; answer using this "
                "recorded outcome."
            )
            outcome_event = AdkEvent(
                author="user",
                content=GenaiContent(role="user", parts=[GenaiPart(text=sys_note)]),
            )
            await _get_db().append_event(adk_session, outcome_event)
    except Exception as gnd_err:
        logger.warning(f"[WARN] Failed to ground approval outcome in ADK session: {gnd_err}")

    output_text = f"✅ **{tool_name} executed** (approved via HITL gate).\n\n```\n{result}\n```"
    metadata = {
        "hitl_approved": True,
        "tool_name": tool_name,
        "args": args,
        "requires_confirmation": False,
    }
    assistant_message = _persist_messages(
        session_id, current_user.id,
        f"[APPROVED] {tool_name}", output_text, metadata
    )

    return SendMessageResponse(
        user_message=None,
        agent_message=ChatMessage(**assistant_message) if assistant_message else None,
        session_id=session_id,
        success=True
    )


@router.post("/sessions/{session_id}/reject", response_model=SendMessageResponse)
async def reject_action_endpoint(
    session_id: str,
    body: Dict[str, Any] = Body(...),
    current_user: UserResponse = Depends(get_current_user)
):
    """Cancel a pending action without executing anything."""
    token = (body or {}).get("approval_token")
    if not token:
        raise HTTPException(status_code=422, detail="approval_token is required")

    from app.chat.pending_actions import get_pending, reject_pending as _reject_pending
    record = get_pending(token)
    if not record:
        raise HTTPException(status_code=404, detail="No pending action for this token")
    # Uniform 404 on binding mismatch (parity with /approve; no existence leak)
    if record.get("session_id") != session_id or record.get("user_id") != current_user.id:
        raise HTTPException(status_code=404, detail="No pending action for this token")

    tool_name = record.get("tool_name", "unknown_tool")
    rejected = _reject_pending(token)
    if not rejected:
        raise HTTPException(status_code=404, detail="No pending action for this token")

    # Same ghost-card scrub for the reject path.
    _get_db().resolve_gate_message(session_id, token, "rejected")

    ack_text = f"🚫 **{tool_name} was rejected.** No action was executed."
    metadata = {"hitl_rejected": True, "tool_name": tool_name}
    assistant_message = _persist_messages(
        session_id, current_user.id,
        f"[REJECTED] {tool_name}", ack_text, metadata
    )

    return SendMessageResponse(
        user_message=None,
        agent_message=ChatMessage(**assistant_message) if assistant_message else None,
        session_id=session_id,
        success=True
    )


@router.delete("/sessions/{session_id}/messages", response_model=dict)
async def clear_messages(
    session_id: str,
    current_user: UserResponse = Depends(get_current_user)
):
    success = _get_db().clear_session_messages(current_user.id, session_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found or access denied")
    return {"message": "Messages cleared successfully", "session_id": session_id}


# ==================== Statistics ====================

@router.get("/stats", response_model=ChatStatsResponse)
async def get_user_stats(current_user: UserResponse = Depends(get_current_user)):
    stats = _get_db().get_user_stats(current_user.id)
    stats["user_id"] = current_user.id
    return ChatStatsResponse(**stats)


@router.get("/admin/stats", response_model=dict)
async def get_admin_stats(current_user: UserResponse = Depends(get_current_user)):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return _get_db().get_all_stats()


@router.post("/incidents/simulate")
async def simulate_incident(
    request: Optional[Dict[str, Any]] = Body(default={}),
    current_user: UserResponse = Depends(get_current_user)
):
    """
    Simulate an autonomous background P0/P1 incident alert from Cloud Monitoring / PagerDuty.
    Creates an incident war room session and triggers the multi-agent RCA pipeline.
    """
    try:
        incident_name = request.get("incident_name", "🚨 P0 Outage: Payment-Gateway Pod CrashLoopBackOff")
        incident_prompt = request.get("prompt", (
            "EMERGENCY ALERT: Payment-Gateway service in production is failing with CrashLoopBackOff (500 error spike). "
            "Perform immediate Root Cause Analysis (RCA) across GCP GKE logs, check ArgoCD sync state, "
            "and propose remediation with Model Armor safety validation."
        ))
        
        # 1. Create a dedicated incident session
        session = _get_db().create_api_session(
            user_id=current_user.id,
            session_name=f"[INCIDENT] {incident_name[:30]}"
        )
        session_id = session["id"]
        
        # 2. Record alert trigger message
        _get_db().add_message(
            user_id=current_user.id,
            session_id=session_id,
            sender=MessageSender.USER,
            text=incident_prompt,
            metadata={"incident_type": "P0_ALERT", "source": "Cloud Monitoring Webhook"}
        )
        
        # 3. Process autonomous investigation through Google ADK
        from app.chat.agent_service import process_message
        agent_result = await process_message(
            message=incident_prompt,
            session_id=session_id,
            user_id=current_user.id,
            metadata={"incident_simulation": True}
        )
        
        agent_response_text = agent_result.get("response", "Investigation completed.")
        agent_metadata = agent_result.get("metadata", {})
        agent_metadata["is_incident_report"] = True
        agent_metadata["severity"] = "P0"
        
        # 4. Save agent RCA response
        agent_msg = _get_db().add_message(
            user_id=current_user.id,
            session_id=session_id,
            sender=MessageSender.ASSISTANT,
            text=agent_response_text,
            metadata=agent_metadata
        )
        
        return {
            "success": True,
            "session_id": session_id,
            "incident_name": incident_name,
            "agent_message": agent_msg,
            "reasoning_steps": agent_metadata.get("reasoning_steps", []),
            "requires_confirmation": agent_metadata.get("requires_confirmation", False),
            "pending_tool": agent_metadata.get("pending_tool")
        }
    except Exception as e:
        logger.error(f"Error simulating incident: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to simulate incident: {str(e)}")


@router.get("/health")
async def chat_health_check():
    return {
        "status": "healthy",
        "service": "chat_sessions",
        "message": "Chat session service is running with user isolation"
    }
