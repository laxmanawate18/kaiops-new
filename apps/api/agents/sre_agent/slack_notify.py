"""Slack notification tool for the KaiOps SRE agent.

Posts an RCA summary to a Slack channel with **Approve/Reject** action buttons
so a developer can approve a guarded (HITL) remediation action directly from
Slack. Works alongside the existing incoming-webhook path.

Two modes:
- If ``SLACK_BOT_TOKEN`` is set, posts via ``chat.postMessage`` with an
  interactive ``actions`` block (Approve/Reject). The buttons carry the
  ``pending_action_id`` so ``/webhooks/slack/interactions`` can resolve them.
- Else falls back to the incoming ``SLACK_WEBHOOK_URL`` (summary only, no
  buttons) — the high-ROI, lowest-risk path.

Never fabricates: if not configured or the call fails, returns an explicit
message rather than pretending it posted.
"""

import os
import json
import logging
import requests

logger = logging.getLogger(__name__)

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "")

# The synthetic user that owns autonomous (worker/runtime) sessions.
SYSTEM_USER_ID = os.environ.get("KAIOPS_RUNTIME_USER", "sre-agent-runtime")

# Map a posted message's slack_ts -> pending_action_id so a button click can be
# resolved. In-process (mirrors pending_actions pattern); a Slack interaction
# arrives in a fresh request, so we persist this in Firestore via pending_actions.
# See app.slack.interactions for the resolver.
_ts_to_action: dict = {}
_ts_lock = __import__("threading").Lock()


def _post_blocks_payload(payload: dict, channel: str = "") -> str:
    """Post a fully-formed chat.postMessage payload (supports ``thread_ts``).

    Returns the message ts on success, else "".
    """
    token = os.getenv("SLACK_BOT_TOKEN", "")
    if not token:
        return ""
    payload.setdefault("channel", channel or SLACK_CHANNEL or SLACK_CHANNEL_ID)
    if not payload.get("channel"):
        return ""
    try:
        resp = requests.post(
            "https://slack.com/api/chat.postMessage",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code == 200 and data.get("ok"):
            logger.info(f"[SLACK] Posted payload to channel={payload.get('channel')} thread={payload.get('thread_ts')}")
            return data.get("ts", "")
        logger.error(f"[SLACK] chat.postMessage failed {resp.status_code}: {data.get('error', data)[:200]}")
        return ""
    except Exception as e:  # noqa: BLE001
        logger.error(f"[SLACK] chat.postMessage error: {e}")
        return ""


def _post_blocks(blocks, channel: str = "", text: str = "") -> str:
    """Post a message with interactive blocks via chat.postMessage (bot token)."""
    token = os.getenv("SLACK_BOT_TOKEN", "")
    if not token:
        return ""
    channel = channel or SLACK_CHANNEL or SLACK_CHANNEL_ID
    if not channel:
        return ""
    payload = {"channel": channel, "text": text or "KaiOps RCA", "blocks": blocks}
    try:
        resp = requests.post(
            "https://slack.com/api/chat.postMessage",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code == 200 and data.get("ok"):
            logger.info(f"[SLACK] Posted blocks to channel={channel}")
            # Return the message ts so we can map it to the pending_action_id.
            return data.get("ts", "")
        logger.error(f"[SLACK] chat.postMessage failed {resp.status_code}: {data.get('error', data)[:200]}")
        return ""
    except Exception as e:  # noqa: BLE001
        logger.error(f"[SLACK] chat.postMessage error: {e}")
        return ""


def register_action_button(message_ts: str, pending_action_id: str) -> None:
    """Persist a slack ts -> pending_action_id mapping so interactions can resolve."""
    if not message_ts or not pending_action_id:
        return
    with _ts_lock:
        _ts_to_action[message_ts] = pending_action_id
    # Also mirror to Firestore so the interaction handler (fresh request) can see it.
    try:
        from app.chat.pending_actions import _pending_ref
        _pending_ref().document(f"slackts_{message_ts}").set({
            "kind": "slack_action_map",
            "pending_action_id": pending_action_id,
            "message_ts": message_ts,
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
        })
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[SLACK] could not persist slack ts map: {e}")


def _post_to_slack(text: str, channel: str = "", webhook_url: str = "", blocks: list = None) -> bool:
    """Post a message via the Slack incoming webhook (summary without buttons)."""
    webhook = webhook_url or SLACK_WEBHOOK_URL
    if not webhook:
        logger.error("[SLACK] SLACK_WEBHOOK_URL not configured; cannot post")
        return False

    payload = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    if channel:
        payload["channel"] = channel

    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        if resp.status_code == 200 and resp.text.lower().strip() in ("ok", ""):
            logger.info(f"[SLACK] Posted to Slack (channel={channel or 'default'})")
            return True
        logger.error(f"[SLACK] Webhook returned {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:  # noqa: BLE001
        logger.error(f"[SLACK] Post failed: {e}")
        return False


def notify_slack(channel: str, message: str, session_link: str = "", pending_action_id: str = "") -> str:
    """Post a message to a Slack channel with Approve/Reject buttons.

    Args:
        channel: Target Slack channel, e.g. '#incidents' (defaults to SLACK_CHANNEL).
        message: The message text to post (RCA summary, remediation, etc.).
        session_link: Optional deep-link URL to the console session.
        pending_action_id: If set, attach Approve/Reject buttons that resolve this
            HITL action when clicked in Slack.

    Returns:
        A confirmation string for the agent.
    """
    channel = channel or SLACK_CHANNEL or SLACK_CHANNEL_ID
    if not message:
        return "Slack notification skipped: empty message."
    if session_link:
        message = f"{message}\n\n<{session_link}|🔗 Open in KaiOps console>"

    # If we have a bot token AND a pending action, post interactive blocks.
    if SLACK_BOT_TOKEN and pending_action_id:
        blocks = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message},
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve"},
                        "style": "primary",
                        "value": pending_action_id,
                        "action_id": "approve_action",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Reject"},
                        "style": "danger",
                        "value": pending_action_id,
                        "action_id": "reject_action",
                    },
                ],
            },
        ]
        ts = _post_blocks(blocks, channel=channel, text=message)
        if ts:
            register_action_button(ts, pending_action_id)
            return f"Posted to Slack channel '{channel or 'default'}' with Approve/Reject buttons."
        return "Failed to post interactive Slack message (check SLACK_BOT_TOKEN configuration)."

    # Fallback: incoming webhook (summary only).
    ok = _post_to_slack(message, channel=channel)
    if ok:
        return f"Posted to Slack channel '{channel or 'default'}'."
    return "Failed to post to Slack (check SLACK_WEBHOOK_URL configuration)."


def post_hitl_approval(session_id: str, user_id: str, tool_name: str, approval_token: str,
                       session_link: str = "", channel: str = "") -> str:
    """Deterministically post a Slack message with Approve/Reject buttons for a
    specific HITL pending action (called from agent_service when the gate fires).

    This guarantees the buttons carry the exact approval_token, so clicking a
    button resolves the real pending action — regardless of what the LLM said.
    """
    channel = channel or SLACK_CHANNEL or SLACK_CHANNEL_ID
    if not (SLACK_BOT_TOKEN and approval_token):
        return ""

    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text":
                f"⚠️ *KaiOps HITL Approval Required*\n"
                f"Session: `{session_id}`\n\n"
                f"The agent wants to run the destructive action *`{tool_name}`*.\n"
                f"{('<'+session_link+'|🔗 Open in KaiOps console>') if session_link else ''}"},
        },
        {
            "type": "actions",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "✅ Approve"},
                 "style": "primary", "value": approval_token, "action_id": "approve_action"},
                {"type": "button", "text": {"type": "plain_text", "text": "❌ Reject"},
                 "style": "danger", "value": approval_token, "action_id": "reject_action"},
            ],
        },
    ]

    # Post the HITL card INSIDE the app's thread (under the `[App_Name] Failed`
    # parent) when the session resolves to a known application. This prevents the
    # approve/reject card from appearing as a scattered standalone message and
    # keeps the whole incident in one thread.
    payload = {"channel": channel, "text": f"KaiOps HITL: {tool_name}", "blocks": blocks}
    try:
        from app.slack.reporter import _get_thread_ts
        parent_ts = _get_thread_ts(session_id) or _resolve_app_thread(session_id)
        if parent_ts:
            payload["thread_ts"] = parent_ts
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[SLACK] thread lookup failed for {session_id}: {e}")

    ts = _post_blocks_payload(payload, channel=channel)
    if ts:
        register_action_button(ts, approval_token)
        return ts
    return ""


def _resolve_app_thread(session_id: str) -> str:
    """Best-effort: resolve a session_id to its app_name -> Slack thread_ts.

    The worker's runtime sessions carry an ``application_name`` stamp; autonomous
    job sessions use the ``runtime-kaiops-{app}`` canonical id. We map the
    session to the app so the HITL card threads under the app's parent message.
    """
    try:
        from app.chat.agent_service import get_session_service
        svc = get_session_service()
        app_name = None
        # Canonical app session id: runtime-kaiops-{app_name}
        if session_id.startswith("runtime-kaiops-"):
            app_name = session_id[len("runtime-kaiops-"):]
        else:
            data = svc.get_api_session(SYSTEM_USER_ID, session_id, allow_runtime=True)
            app_name = (data or {}).get("application_name") or ""
        if not app_name:
            return ""
        from app.slack.reporter import _get_thread_ts
        return _get_thread_ts(app_name) or ""
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[SLACK] _resolve_app_thread failed: {e}")
        return ""


__all__ = ["notify_slack", "register_action_button", "post_hitl_approval"]
