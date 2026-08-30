"""
Agent service for handling AI agent calls in chat.
This service integrates with the KaiOPS SRE Agent using the correct ADK invocation pattern.
"""

import logging
import re
import os
from typing import Dict, Any, Optional
from google.adk.runners import Runner
from google.genai.types import Content, Part
from genai_retry_wrapper import with_genai_retry
from app.chat.custom_session_service import VertexFirestoreSessionService

logger = logging.getLogger(__name__)


def _rtc_keys(actions) -> object:
    """Defensively extract requested_tool_confirmations keys/items.

    Depending on the installed ADK version this field may be a dict
    ({confirmation_id: ToolConfirmation}) or a plain list of
    ToolConfirmation objects. Never assume .keys() exists.
    """
    try:
        rtc = getattr(actions, "requested_tool_confirmations", None)
        if isinstance(rtc, dict):
            return list(rtc.keys())
        if isinstance(rtc, list):
            return rtc
    except Exception:
        pass
    return None


def _get_rtc(event):
    """Return event.actions.requested_tool_confirmations only if it is a dict or list."""
    rtc = getattr(getattr(event, "actions", None), "requested_tool_confirmations", None)
    return rtc if isinstance(rtc, (dict, list)) else None

# Global services
_session_service: Optional[VertexFirestoreSessionService] = None
_runner: Optional[Runner] = None
AGENT_AVAILABLE = False

try:
    from agents import root_agent
    
    # Initialize ADK services using our custom cloud-native memory bank
    _session_service = VertexFirestoreSessionService()
    _runner = Runner(
        agent=root_agent, 
        app_name="kaiops", 
        session_service=_session_service
    )
    AGENT_AVAILABLE = True
    logger.info("[OK] ADK Agent Runner initialized successfully with root_agent")
except Exception as e:
    logger.error(f"[FAIL] Failed to load root agent or initialize runner: {e}")
    AGENT_AVAILABLE = False

async def _run_stream_with_start_retry(runner: Runner, user_id: str, session_id: str, user_content: Content):
    """Async generator over runner events with patient retries on transient
    GenAI failures (e.g., 429 RESOURCE_EXHAUSTED) that strike before any event
    is produced. Waits 30s/60s/90s between attempts per ops guidance; gives up
    with a clear error only after the full backoff schedule is exhausted."""
    delays = (30.0, 60.0, 90.0)
    import asyncio as _aio
    from genai_retry_wrapper import _is_transient as _is_transient_err

    last_exc = None
    for attempt in range(len(delays) + 1):
        it = runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_content,
        ).__aiter__()
        try:
            first = await it.__anext__()
        except StopAsyncIteration:
            return
        except Exception as exc:  # noqa: BLE001 - classified below
            last_exc = exc
            if attempt < len(delays) and _is_transient_err(exc):
                wait = delays[attempt]
                logger.warning(
                    "[RETRY] Transient GenAI error starting stream "
                    "(attempt %d/%d): %s — waiting %.0fs",
                    attempt + 1, len(delays) + 1, exc, wait,
                )
                await _aio.sleep(wait)
                continue
            raise
        yield first
        async for ev in it:
            yield ev
        return
    raise last_exc


def get_session_service() -> VertexFirestoreSessionService:
    if not _session_service:
        raise RuntimeError("Session service is not initialized")
    return _session_service


def _dedupe_repeated_sections(text: str, min_block_len: int = 120, max_window_lines: int = 12) -> str:
    """Remove exact-duplicate contiguous multi-line blocks (LLMs sometimes emit
    the same section 2-4x). Line-anchored: a duplicate anywhere whose window
    matches an already-output window byte-for-byte is dropped. Windows are
    always registered in DESCENDING size order so future duplicates of any
    sub-block length can match; blank runs collapse afterwards."""
    if not text or ("\n" not in text):
        return text

    lines = text.split("\n")
    n = len(lines)

    def _win(a: int, b: int) -> str:
        return "\n".join(lines[a:b]).strip()

    seen: set[str] = set()
    res: list[str] = []
    i = 0
    while i < n:
        # Blank separators are never dedupe anchors: a window starting on an
        # empty line can byte-match an earlier boundary window and silently
        # swallow the legit content that follows it.
        if not lines[i].strip():
            res.append(lines[i])
            i += 1
            continue
        hi = min(n, i + max_window_lines)
        skip = None
        for size in range(hi - i, 1, -1):
            w = _win(i, i + size)
            if len(w) >= min_block_len and w in seen:
                skip = size
                break
        if skip:
            i += skip
            continue
        for size in range(hi - i, 1, -1):
            w = _win(i, i + size)
            if len(w) >= min_block_len:
                seen.add(w)
        res.append(lines[i])
        i += 1

    out = "\n".join(res)
    out = re.sub(r"\n{3,}", "\n\n", out)
    if text.endswith("\n"):
        out += "\n"
    return out


@with_genai_retry(max_retries=3, base_delay=30.0, max_delay=60.0)
async def _run_agent_session(runner: Runner, user_id: str, session_id: str, user_content: Content) -> tuple[str, dict]:
    """
    Execute the agent session with retry logic for GenAI overload errors.
    Wraps the async generator consumption to allow retrying the entire generation process.
    """
    response_parts = []
    extra_metadata = {"reasoning_steps": []}
    step_count = 0
    
    async for event in runner.run_async(
        user_id=user_id, 
        session_id=session_id, 
        new_message=user_content
    ):
        # Capture Tool Calls for Real-Time Reasoning Pipeline
        if hasattr(event, 'actions') and event.actions:
            if hasattr(event.actions, 'tool_calls') and event.actions.tool_calls:
                for tc in event.actions.tool_calls:
                    step_count += 1
                    tool_name = getattr(tc, 'name', 'cloud_tool')
                    extra_metadata["reasoning_steps"].append({
                        "step": step_count,
                        "title": f"Invoking {tool_name}",
                        "description": f"Querying telemetry and state via {tool_name}",
                        "status": "completed"
                    })
            
            # Handle HITL / Model Armor Confirmation Requests
            # Same as streaming path: parse on every event — the wrapper call
            # (adk_request_confirmation) arrives on an earlier event than rtc.
            if _get_rtc(event) or (
                event.content and event.content.parts
                and any(
                    getattr(p, "function_call", None) is not None
                    and getattr(p.function_call, "name", "") == "adk_request_confirmation"
                    for p in event.content.parts
                )
            ):
                # Parse the adk_request_confirmation wrapper to recover the
                # real tool name + args so approval executes exactly what was
                # requested.
                from app.chat.pending_actions import create_pending
                for conf in _extract_confirmations(event):
                    tool_name = conf["tool_name"]
                    extra_metadata["requires_confirmation"] = True
                    extra_metadata["pending_tool"] = tool_name
                    try:
                        approval_token = create_pending(
                            session_id=session_id, user_id=user_id, tool_name=tool_name,
                            args=conf.get("args"),
                        )
                        extra_metadata["approval_token"] = approval_token
                        # Post a Slack message with Approve/Reject buttons bound to
                        # this exact token, so the dev can approve from Slack.
                        try:
                            from agents.sre_agent.slack_notify import post_hitl_approval
                            frontend_url = os.environ.get("KAI_OPS_FRONTEND_URL", "https://kaiops-sre.searceinc.net")
                            post_hitl_approval(
                                session_id=session_id, user_id=user_id,
                                tool_name=tool_name, approval_token=approval_token,
                                session_link=f"{frontend_url}/console/{session_id}",
                            )
                        except Exception as slack_err:
                            logger.warning(f"[WARN] post_hitl_approval failed: {slack_err}")
                    except Exception as tok_err:
                        logger.error(f"[FAIL] Failed to register pending action: {tok_err}")
                    # NOTE: key name is a frontend contract (ApprovalCard.tsx). This block is
                    # KaiOps' own HITL destructive-action gate. Google Cloud Model Armor is
                    # provisioned separately as template `kaiops-governance-template`
                    # (docs/FEATURE_PROGRESS.md §4); the Agent Gateway exposes no model-armor
                    # binding field, so platform filters apply at the app/eval layer.
                    extra_metadata["model_armor"] = {
                        "status": "GUARDRAIL_INTERCEPTED",
                        "policy": "DESTRUCTIVE_ACTION_PROTECTION",
                        "target": tool_name
                    }
                    response_parts.append(
                        f"\n\n⚠️ **Action Required**: The agent wants to execute a destructive action (`{tool_name}`).\n"
                        "Please confirm to proceed."
                    )

        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_parts.append(part.text)
                    
    # Truthful fallback when the run used NO tools: never fabricate
    # telemetry steps that did not happen.
    if not extra_metadata["reasoning_steps"]:
        extra_metadata["reasoning_steps"] = [{
            "step": 1,
            "title": "Direct response",
            "description": "Answered from session context without external tool calls",
            "status": "completed",
        }]

    final_text = _dedupe_repeated_sections("".join(response_parts))
    return final_text, extra_metadata


def _extract_confirmations(event) -> list[dict]:
    """Parse ADK tool-confirmation requests from an event.

    ADK wraps each pending confirmation in a synthetic function call named
    ``adk_request_confirmation`` whose args contain:
      originalFunctionCall: {name, args, id}  — the real guarded tool call
      toolConfirmation: {...}

    Returns a list of dicts: [{"tool_name": str, "args": dict}, ...]
    """
    confirmations: list[dict] = []
    if not (event.content and event.content.parts):
        return confirmations
    for part in event.content.parts:
        fc = getattr(part, "function_call", None)
        if fc is None:
            continue
        if getattr(fc, "name", "") != "adk_request_confirmation":
            continue
        args = getattr(fc, "args", None) or {}
        original = args.get("originalFunctionCall") or {}
        # originalFunctionCall may be a dict or a pydantic model depending on
        # how ADK serialized it.
        if hasattr(original, "get"):
            name = original.get("name")
            call_args = original.get("args") or {}
        else:
            name = getattr(original, "name", None)
            call_args = getattr(original, "args", None) or {}
        try:
            call_args = dict(call_args or {})
        except Exception:
            call_args = {}
        if name:
            confirmations.append({"tool_name": name, "args": call_args})
    return confirmations


async def _ensure_adk_session(user_id: str, session_id: str):
    """Get or create the ADK session used for agent memory."""
    session = await _session_service.get_session(
        app_name="kaiops",
        user_id=user_id,
        session_id=session_id
    )
    if not session:
        logger.info(f"[NEW] Creating new ADK session for {session_id}")
        await _session_service.create_session(
            app_name="kaiops",
            user_id=user_id,
            session_id=session_id
        )


def _build_user_content(message: str, metadata: Optional[Dict[str, Any]] = None) -> Content:
    """Build a multimodal user Content object (text + optional images)."""
    parts = [Part(text=message)]

    metadata = metadata or {}
    images = metadata.get("images", [])
    if images:
        logger.info(f"📸 Found {len(images)} images in message metadata for Vision Analysis")
        import base64
        from google.genai.types import Blob
        for img in images:
            try:
                mime_type = img.get("mime_type", "image/jpeg")
                b64_data = img.get("data")
                if b64_data:
                    # Strip standard data URI prefix if present
                    if "," in b64_data:
                        b64_data = b64_data.split(",", 1)[1]
                    image_bytes = base64.b64decode(b64_data)
                    parts.append(Part(inline_data=Blob(data=image_bytes, mime_type=mime_type)))
            except Exception as img_err:
                logger.warning(f"Failed to process image attachment: {img_err}")

    return Content(role="user", parts=parts)


async def stream_message(
    message: str,
    session_id: str,
    user_id: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """Yield SSE-formatted dicts as the agent processes a message.

    Yields dicts like:
      {"type": "status", "stage": "started"}
      {"type": "reasoning", "step": {...}}          # tool calls as they happen
      {"type": "delta", "text": "..."}              # partial response text
      {"type": "metadata", "data": {...}}           # final metadata (reasoning_steps etc.)
      {"type": "done", "message_id": ..., "success": True}
      {"type": "error", "error_message": "..."}
    """
    try:
        if not AGENT_AVAILABLE or _runner is None or _session_service is None:
            logger.error("[FAIL] Agent service not available")
            yield {"type": "error", "error_message": "Agent service is not available. Please try again later."}
            return

        logger.info(f"📨 Streaming message for session {session_id} (user {user_id})")

        yield {"type": "status", "stage": "started"}

        await _ensure_adk_session(user_id, session_id)
        user_content = _build_user_content(message, metadata)

        response_parts = []
        accumulated_len = 0
        extra_metadata = {"reasoning_steps": []}
        step_count = 0

        async for event in _run_stream_with_start_retry(
            _runner, user_id, session_id, user_content
        ):
            n_events = extra_metadata.setdefault("_debug_events", 0)
            extra_metadata["_debug_events"] = n_events + 1
            _fc = [getattr(p, "function_call", None) and getattr(p.function_call, "name", "?")
                   for p in (event.content.parts or [])] if event.content else []
            logger.info(f"[DEBUG] event {n_events + 1}: author={getattr(event,'author','?')} "
                        f"partial={getattr(event,'partial',None)} fc={_fc} "
                        f"rtc={_rtc_keys(getattr(event, 'actions', None))}")
            # Capture Tool Calls for Real-Time Reasoning Pipeline
            if hasattr(event, 'actions') and event.actions:
                if hasattr(event.actions, 'tool_calls') and event.actions.tool_calls:
                    for tc in event.actions.tool_calls:
                        step_count += 1
                        tool_name = getattr(tc, 'name', 'cloud_tool')
                        step = {
                            "step": step_count,
                            "title": f"Invoking {tool_name}",
                            "description": f"Querying telemetry and state via {tool_name}",
                            "status": "completed"
                        }
                        extra_metadata["reasoning_steps"].append(step)
                        yield {"type": "reasoning", "step": step}

                # Handle HITL / Model Armor Confirmation Requests.
                # NOTE: ADK emits the `adk_request_confirmation` wrapper call
                # (event N, rtc empty) BEFORE the rtc-bearing event (N+1). So
                # we must parse function-call parts on EVERY event — gating
                # on rtc alone misses the wrapper event entirely.
                if _get_rtc(event) or (
                    event.content and event.content.parts
                    and any(
                        getattr(p, "function_call", None) is not None
                        and getattr(p.function_call, "name", "") == "adk_request_confirmation"
                        for p in event.content.parts
                    )
                ):
                    # Parse the adk_request_confirmation wrapper to recover the
                    # real tool name + args so approval executes exactly what
                    # was requested.
                    from app.chat.pending_actions import create_pending
                    for conf in _extract_confirmations(event):
                        tool_name = conf["tool_name"]
                        extra_metadata["requires_confirmation"] = True
                        extra_metadata["pending_tool"] = tool_name
                        try:
                            extra_metadata["approval_token"] = create_pending(
                                session_id=session_id,
                                user_id=user_id,
                                tool_name=tool_name,
                                args=conf.get("args"),
                            )
                        except Exception as tok_err:
                            logger.error(f"[FAIL] Failed to register pending action: {tok_err}")
                        # NOTE: key name is a frontend contract (ApprovalCard.tsx). This block is
                        # KaiOps' own HITL destructive-action gate. Google Cloud Model Armor is
                        # provisioned separately as template `kaiops-governance-template`
                        # (docs/FEATURE_PROGRESS.md §4); the Agent Gateway exposes no model-armor
                        # binding field, so platform filters apply at the app/eval layer.
                        extra_metadata["model_armor"] = {
                            "status": "GUARDRAIL_INTERCEPTED",
                            "policy": "DESTRUCTIVE_ACTION_PROTECTION",
                            "target": tool_name,
                        }
                        confirmation_text = (
                            "\n\n⚠️ **Action Required**: The agent wants to execute a destructive action "
                            f"(`{tool_name}`).\nPlease confirm to proceed."
                        )
                        response_parts.append(confirmation_text)

            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_parts.append(part.text)
                        # Yield only NEW text beyond what has already been streamed
                        full_text = "".join(response_parts)
                        if len(full_text) > accumulated_len:
                            delta = full_text[accumulated_len:]
                            accumulated_len = len(full_text)
                            yield {"type": "delta", "text": delta}

        response_text = _dedupe_repeated_sections("".join(response_parts))

        # Truthful fallback when the run used NO tools: never fabricate
        # telemetry steps that did not happen.
        if not extra_metadata["reasoning_steps"]:
            extra_metadata["reasoning_steps"] = [{
                "step": 1,
                "title": "Direct response",
                "description": "Answered from session context without external tool calls",
                "status": "completed",
            }]

        if not response_text:
            logger.warning("[WARN] Agent returned empty response")
            response_text = "No response generated. Please try your query again."
            yield {"type": "delta", "text": response_text}

        resp_metadata = {"agent": "root_agent", "response_length": len(response_text)}
        resp_metadata.update(extra_metadata)

        yield {"type": "metadata", "data": resp_metadata}

        # Persist BOTH messages exactly like the non-streaming flow
        from app.chat.custom_session_service import VertexFirestoreSessionService as _S  # noqa: F401
        user_message = _session_service.add_message(
            user_id=user_id,
            session_id=session_id,
            sender="user",
            text=message,
            metadata=metadata
        )
        assistant_message = _session_service.add_message(
            user_id=user_id,
            session_id=session_id,
            sender="assistant",
            text=response_text,
            metadata=resp_metadata
        )

        yield {
            "type": "done",
            "success": True,
            "message_id": (assistant_message or {}).get("id") if isinstance(assistant_message, dict) else None,
            "user_message_id": (user_message or {}).get("id") if isinstance(user_message, dict) else None,
            "metadata": resp_metadata
        }

    except Exception as e:
        logger.error(f"[FAIL] Error streaming message: {str(e)}", exc_info=True)
        yield {"type": "error", "error_message": f"An error occurred while processing your request: {str(e)}"}


async def process_message(
    message: str, 
    session_id: str, 
    user_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process a user message through the SRE agent using ADK's runner pattern.
    
    Args:
        message: The user's input message
        session_id: The chat session ID
        user_id: The user's ID
        metadata: Optional message metadata (e.g., images for vision analysis)
        
    Returns:
        Dictionary with agent response and metadata
    """
    try:
        if not AGENT_AVAILABLE or _runner is None or _session_service is None:
            logger.error("[FAIL] Agent service not available")
            return {
                "response": "Agent service is not available. Please try again later.",
                "success": False,
                "metadata": {"error": "agent_unavailable"}
            }
        
        logger.info(f"📨 Processing message for session {session_id}")
        logger.info(f"👤 User ID: {user_id}")
        logger.info(f"💬 Message: {message}")
        
        # Ensure session exists in ADK memory
        session = await _session_service.get_session(
            app_name="kaiops", 
            user_id=user_id, 
            session_id=session_id
        )
        
        if not session:
            logger.info(f"[NEW] Creating new ADK session for {session_id}")
            await _session_service.create_session(
                app_name="kaiops", 
                user_id=user_id, 
                session_id=session_id
            )
        
        # Create Content object for the message with support for multimodal image inputs
        parts = [Part(text=message)]
        
        # Support Vision / Multimodal analysis by extracting attached images
        metadata = metadata or {}
        images = metadata.get("images", [])
        if images:
            logger.info(f"📸 Found {len(images)} images in message metadata for Vision Analysis")
            import base64
            from google.genai.types import Blob
            for img in images:
                try:
                    mime_type = img.get("mime_type", "image/jpeg")
                    b64_data = img.get("data")
                    if b64_data:
                        # Strip standard data URI prefix if present
                        if "," in b64_data:
                            b64_data = b64_data.split(",", 1)[1]
                        image_bytes = base64.b64decode(b64_data)
                        parts.append(Part(inline_data=Blob(data=image_bytes, mime_type=mime_type)))
                except Exception as img_err:
                    logger.warning(f"Failed to process image attachment: {img_err}")

        user_content = Content(role="user", parts=parts)
        
        logger.info(f"[RUN] Invoking root agent with {len(parts)} parts...")
        # Run the agent and collect responses
        response_text, extra_metadata = await _run_agent_session(_runner, user_id, session_id, user_content)
        
        if not response_text:
            logger.warning("[WARN] Agent returned empty response")
            response_text = "No response generated. Please try your query again."
        
        logger.info(f"[OK] Agent response received: {len(response_text)} characters")
        logger.info(f"📝 Response preview: {response_text[:200]}...")
        
        # Preserve formatting - DO NOT strip emojis or markdown
        resp_metadata = {"agent": "root_agent", "response_length": len(response_text)}
        resp_metadata.update(extra_metadata)
        
        return {
            "response": response_text,
            "success": True,
            "metadata": resp_metadata
        }
        
    except Exception as e:
        logger.error(f"[FAIL] Error processing message: {str(e)}", exc_info=True)
        return {
            "response": f"An error occurred while processing your request: {str(e)}",
            "success": False,
            "metadata": {"error": str(e)}
        }
