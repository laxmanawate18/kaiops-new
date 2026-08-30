"""Slack interactive actions handler.

Receives Slack button-interaction callbacks (Approve/Reject on an RCA message
posted by ``notify_slack``) and resolves the corresponding HITL pending action.

The Slack app is configured for HTTP mode: interactivity sends a POST to
``/api/v1/webhooks/slack/interactions`` with a signed, urlencoded payload.

Flow:
    1. Verify the Slack signing secret (prevents forged callbacks).
    2. Parse the action: ~button ``value`` = pending_action_id (= approval token);
       ``action_id`` = approve_action | reject_action.
    3. The posted message carried ``register_action_button(ts, pending_action_id)``
       so we can map incoming ``message.ts`` -> pending_action_id (Firestore mirror).
    4. Look up the pending action record; resolve its session + execute the guarded
       tool (approve) or cancel it (reject), mirroring the console /approve|/reject.

Because a Slack click is anonymous (no logged-in user), we resolve via the token
(approval_token) directly rather than a user-bound endpoint.
"""

import os
import json
import hashlib
import hmac
import logging
import time
import urllib.parse
import asyncio
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, Response, Body, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks/slack", tags=["slack"])

SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")


def _verify_signature(timestamp: str, body: bytes, signature: str) -> bool:
    """Verify the Slack X-Slack-Signature HMAC-SHA256 using the signing secret."""
    if not SLACK_SIGNING_SECRET:
        logger.warning("[SLACK] SLACK_SIGNING_SECRET not configured; rejecting interaction")
        return False
    # Slack sends "v0=<hex>"; check timestamp freshness (5 min).
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs(time.time() - ts) > 300:
        logger.warning("[SLACK] stale interaction timestamp")
        return False
    base = f"v0:{timestamp}:{body.decode('utf-8', errors='replace')}"
    digest = hmac.new(
        SLACK_SIGNING_SECRET.encode("utf-8"), base.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"v0={digest}", signature)


def _resolve_pending_id(message_ts: str) -> Optional[str]:
    """Look up the pending_action_id recorded for a message_ts (Firestore mirror)."""
    try:
        from app.chat.pending_actions import _pending_ref
        doc = _pending_ref().document(f"slackts_{message_ts}").get()
        if doc.exists:
            return doc.to_dict().get("pending_action_id")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[SLACK] could not resolve pending id for ts {message_ts}: {e}")
    # Fallback: in-process map (only works if same-instance).
    try:
        from agents.sre_agent import slack_notify
        return slack_notify._ts_to_action.get(message_ts)
    except Exception:  # noqa: BLE001
        return None


async def _execute_approved(pending_action_id: str) -> Dict[str, Any]:
    """Execute the guarded tool for an approved pending action (anonymous path)."""
    from app.chat.pending_actions import get_pending, consume_pending
    record = get_pending(pending_action_id)
    if not record:
        return {"ok": False, "error": "No pending action (expired or already used)"}

    tool_name = record.get("tool_name")
    session_id = record.get("session_id")
    user_id = record.get("user_id")

    # Resolve the guarded tool callable (same registry as console /approve).
    from app.chat.routes import _get_tool_registry
    registry = _get_tool_registry()
    func = registry.get(tool_name)
    if func is None:
        return {"ok": False, "error": f"Tool '{tool_name}' is not approvable"}

    consumed = consume_pending(pending_action_id)
    if not consumed:
        return {"ok": False, "error": "Pending action already consumed"}

    # Ground the outcome in the ADK session so follow-ups don't re-request.
    try:
        from app.chat.agent_service import get_session_service
        db = get_session_service()
        db.resolve_gate_message(session_id, pending_action_id, "approved")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[SLACK] resolve_gate_message failed: {e}")

    args = dict(record.get("args") or {})
    try:
        if args:
            result = await func(**args)
        else:
            result = await func()
    except TypeError as te:
        return {"ok": False, "error": f"Missing args for {tool_name}: {te}"}
    except Exception as e:  # noqa: BLE001
        result = f"Execution failed: {e}"

    # Persist the outcome message to the session history.
    try:
        db = get_session_service()
        db.add_message(
            user_id=user_id, session_id=session_id, sender="user",
            text=f"[SLACK APPROVED] {tool_name}"
        )
        db.add_message(
            user_id=user_id, session_id=session_id, sender="agent",
            text=f"✅ **{tool_name} executed** (approved via Slack).\n\n```\n{result}\n```",
            metadata={"hitl_approved": True, "tool_name": tool_name, "args": args},
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[SLACK] could not persist approval message: {e}")

    return {"ok": True, "tool_name": tool_name, "result": result}


async def _reject_pending(pending_action_id: str) -> Dict[str, Any]:
    from app.chat.pending_actions import get_pending, reject_pending
    record = get_pending(pending_action_id)
    if not record:
        return {"ok": False, "error": "No pending action"}
    session_id = record.get("session_id")
    tool_name = record.get("tool_name", "unknown")
    if not reject_pending(pending_action_id):
        return {"ok": False, "error": "Already handled"}
    try:
        from app.chat.agent_service import get_session_service
        db = get_session_service()
        db.resolve_gate_message(session_id, pending_action_id, "rejected")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[SLACK] reject resolve_gate_message failed: {e}")
    return {"ok": True, "tool_name": tool_name}


@router.post("/interactions", include_in_schema=False)
async def slack_interactions(request: Request):
    """Handle Slack button-action callbacks (Approve/Reject)."""
    body = await request.body()
    sig = request.headers.get("X-Slack-Signature", "")
    ts = request.headers.get("X-Slack-Request-Timestamp", "")

    if not _verify_signature(ts, body, sig):
        logger.warning("[SLACK] interaction signature verification failed")
        return Response(content="signature mismatch", status_code=403)

    # Slack sends application/x-www-form-urlencoded with a 'payload' JSON field.
    form = urllib.parse.parse_qs(body.decode("utf-8", errors="replace"))
    payload_str = form.get("payload", [""])[0]
    if not payload_str:
        return Response(content="no payload", status_code=400)

    try:
        payload = json.loads(payload_str)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[SLACK] bad payload: {e}")
        return Response(content="bad payload", status_code=400)

    actions = payload.get("actions", [])
    if not actions:
        # Slash command / interactive health-ping: acknowledge.
        return Response(content="no actions", status_code=200)
    action = actions[0]
    action_id = action.get("action_id", "")
    pending_action_id = action.get("value", "")

    if not pending_action_id:
        # Fall back to the message_ts -> pending_action_id map.
        message_ts = payload.get("message", {}).get("ts", "")
        pending_action_id = _resolve_pending_id(message_ts) or ""

    if not pending_action_id:
        return Response(content="missing pending action", status_code=400)

    if action_id == "approve_action":
        result = await _execute_approved(pending_action_id)
    elif action_id == "reject_action":
        result = await _reject_pending(pending_action_id)
    else:
        logger.warning(f"[SLACK] unknown action_id: {action_id}")
        return Response(content="unknown action", status_code=400)

    # Update the posted message to show the resolution (best-effort).
    try:
        _update_message_blocks(payload, action_id, result)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[SLACK] could not update message: {e}")

    if not result.get("ok"):
        return Response(content=f"resolution failed: {result.get('error')}", status_code=200)
    return Response(content="ok", status_code=200)


def _update_message_blocks(payload: Dict[str, Any], action_id: str, result: Dict[str, Any]) -> None:
    """Replace the action buttons with a resolution note (chat.update)."""
    if not SLACK_BOT_TOKEN:
        return
    channel = payload.get("channel", {}).get("id", "")
    message_ts = payload.get("message", {}).get("ts", "")
    if not (channel and message_ts):
        return
    resolved = "✅ Approved" if action_id == "approve_action" else "❌ Rejected"
    import requests as _req
    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"_{resolved} via Slack._"}},
    ]
    try:
        _req.post(
            "https://slack.com/api/chat.update",
            json={"channel": channel, "ts": message_ts, "blocks": blocks},
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
            timeout=12,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[SLACK] chat.update failed: {e}")
