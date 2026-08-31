"""Thread-aware Slack reporter for app deployment status.

Implements the user's Slack spec:
- One Slack **thread per application** (keyed by Firestore ``application_name``).
- Every message is a block card: header ``[App_Name] Healthy | Failed``, RCA
  summary, and (if applicable) a session-link button.
- **Healthy** -> reply in thread: "✅ your app deployed successfully".
- **Failed** -> reply in thread: full RCA + troubleshooting. If **infra-related**,
  add a line tagging SRE team ("⚠️ SRE team needs to check this").
- Stores the parent ``thread_ts`` per app in Firestore (``slack_app_threads``)
  so all updates stay in one thread.

Uses the bot token (``SLACK_BOT_TOKEN``) via chat.postMessage / chat.update /
chat.postMessage(thread_ts=...).
"""
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from app.database.firestore_config import FirestoreConfig

logger = logging.getLogger(__name__)

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "")
FRONTEND_URL = os.getenv("KAI_OPS_FRONTEND_URL", "https://kaiops-sre.searceinc.net")
SRE_TAG = os.getenv("SLACK_SRE_TAG", "SRE team needs to check this")

_THREADS_COLLECTION = "slack_app_threads"


def _thread_ref():
    return FirestoreConfig.get_client().collection(_THREADS_COLLECTION)


def _channel() -> str:
    return SLACK_CHANNEL_ID or SLACK_CHANNEL or ""


def _get_thread_ts(key: str) -> Optional[str]:
    try:
        doc = _thread_ref().document(key).get()
        return doc.to_dict().get("thread_ts") if doc.exists else None
    except Exception:  # noqa: BLE001
        return None


def _save_thread_ts(key: str, ts: str) -> None:
    try:
        _thread_ref().document(key).set({"thread_ts": ts, "app_name": key})
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[SLACK] save thread ts failed: {e}")


_SLACK_TEXT_CHUNK = 2900


def _chunk_block_text(text: str, limit: int = _SLACK_TEXT_CHUNK) -> list:
    """Split a long string into multiple Slack section blocks.

    Slack rejects any single ``section`` block whose ``mrkdwn`` text exceeds
    3000 chars with "invalid_blocks". The RCA report (or any long detail) is
    chunked here so the post succeeds while keeping the message readable.
    """
    if len(text) <= limit:
        return [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]
    chunks = []
    remaining = text
    while len(remaining) > limit:
        # Prefer to break near a newline so we don't split a word awkwardly.
        split_at = remaining.rfind("\n", 0, limit)
        if split_at <= 0:
            split_at = limit
        chunk = remaining[:split_at].rstrip()
        if chunk:
            chunks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append({"type": "section", "text": {"type": "mrkdwn", "text": remaining}})
    return chunks


def _blocks(status: str, detail: str, session_link: str = "", is_infra: bool = False,
            hitl_action_id: str = "") -> list:
    """Build a rich block card for a status message.

    - status: "Healthy" | "Failed"
    - detail: the RCA / troubleshooting text.
    - session_link: console deep-link button.
    - is_infra: append SRE-team tag.
    - hitl_action_id: if set, append Approve/Reject buttons bound to a pending HITL action.
    """
    header = f"[{'✅ Healthy' if status == 'Healthy' else '❌ Failed'}]"
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": header, "emoji": True}},
    ]
    # Chunk long text into multiple section blocks. Slack limits a single
    # section/mrkdwn block's text to 3000 chars; a long RCA would exceed it and
    # cause "invalid_blocks". We split on a safe 2900-char boundary (preferring
    # to break at a newline) so the whole report posts successfully.
    blocks.extend(_chunk_block_text(detail or "_No detail_"))
    if is_infra:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"⚠️ *{SRE_TAG}*"}})
    if session_link:
        blocks.append({
            "type": "actions",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "🔗 Open KaiOps console"},
                 "url": session_link, "action_id": "open_console"},
            ],
        })
    if hitl_action_id:
        blocks.append({
            "type": "actions",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "✅ Approve"},
                 "style": "primary", "value": hitl_action_id, "action_id": "approve_action"},
                {"type": "button", "text": {"type": "plain_text", "text": "❌ Reject"},
                 "style": "danger", "value": hitl_action_id, "action_id": "reject_action"},
            ],
        })
    return blocks


def _send(msg_payload: dict) -> Optional[str]:
    """Post to Slack; returns message ts on success."""
    import requests
    try:
        resp = requests.post(
            "https://slack.com/api/chat.postMessage", json=msg_payload,
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}, timeout=15,
        )
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code == 200 and data.get("ok"):
            return data.get("ts")
        logger.error(f"[SLACK] chat.postMessage failed: {data.get('error', data)}")
        return None
    except Exception as e:  # noqa: BLE001
        logger.error(f"[SLACK] post error: {e}")
        return None


def _details_blocks(details: dict) -> list:
    """Build a details section (cluster, cloud provider, namespace, etc.)."""
    if not details:
        return []
    lines = []
    labels = {
        "cluster": "🌐 Cluster", "cloud_provider": "☁️ Cloud", "namespace": "📦 Namespace",
        "env": "🌍 Env", "app": "📱 App", "sync": "🔄 Sync", "health": "❤️ Health",
        "repo": "📌 Repo", "revision": "🔖 Revision", "owner": "👤 Owner",
    }
    for k, v in details.items():
        if v is None or str(v).strip() == "":
            continue
        label = labels.get(k, k.replace("_", " ").title())
        lines.append(f"*{label}:* {v}")
    if not lines:
        return []
    return [{"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}]


def _send_update(channel: str, ts: str, blocks: list) -> bool:
    """Edit an existing Slack message (chat.update). Returns success."""
    import requests
    try:
        resp = requests.post(
            "https://slack.com/api/chat.update",
            json={"channel": channel, "ts": ts, "blocks": blocks},
            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}, timeout=15,
        )
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code == 200 and data.get("ok"):
            return True
        logger.error(f"[SLACK] chat.update failed: {data.get('error', data)}")
        return False
    except Exception as e:  # noqa: BLE001
        logger.error(f"[SLACK] update error: {e}")
        return False


def _ensure_thread(app_name: str, status: str, channel: str, details: dict = None,
                   thread_key: str = "") -> str:
    """Create/repair the parent thread message; return the parent thread_ts.

    ``thread_key`` (defaults to ``app_name``) identifies the thread. Pass a
    unique key (e.g. ``{app_name}::{incident_id}``) to force a NEW parent thread
    per incident run so each RCA is its own clean thread. If omitted, the app's
    single thread is reused (legacy behaviour).
    """
    key = thread_key or app_name
    existing_ts = _get_thread_ts(key)
    if existing_ts:
        # Best-effort repair of a stale parent header to the correct `[App_Name]` format.
        try:
            blocks = [
                {"type": "header", "text": {"type": "plain_text",
                                            "text": f"[{app_name}] {'✅ Healthy' if status == 'Healthy' else '❌ Failed'}",
                                            "emoji": True}},
                {"type": "section", "text": {"type": "mrkdwn",
                                             "text": f"*{app_name}* deployment status"}},
            ]
            blocks.extend(_details_blocks(details or {}))
            _send_update(channel, existing_ts, blocks)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[SLACK] thread repair failed: {e}")
        return existing_ts
    blocks = [
        {"type": "header", "text": {"type": "plain_text",
                                    "text": f"[{app_name}] {'✅ Healthy' if status == 'Healthy' else '❌ Failed'}",
                                    "emoji": True}},
        {"type": "section", "text": {"type": "mrkdwn",
                                     "text": f"*{app_name}* deployment status"}},
    ]
    blocks.extend(_details_blocks(details or {}))
    parent_ts = _send({"channel": channel, "text": f"[{app_name}] {status}", "blocks": blocks})
    if parent_ts:
        _save_thread_ts(key, parent_ts)
    return parent_ts or ""


async def report_app_status(app_name: str, status: str, detail: str = "",
                            cloud_provider: str = "gcp", is_infra: bool = False,
                            session_link: str = "", hitl_action_id: str = "",
                            details: dict = None, thread_key: str = "") -> str:
    """Report app deployment status to a Slack thread.

    - Creates the **parent thread** with the ``[App_Name] Healthy|Failed`` header
      + a details section (cluster, cloud provider, namespace...).
    - Posts the **RCA detail as a subthread reply**, with the session link + SRE tag
      + Approve/Reject buttons (if ``hitl_action_id`` set).
    - ``thread_key`` (defaults to app_name) lets you force a fresh thread per run.

    Returns the reply message ts (or parent ts on first creation).
    """
    if not SLACK_BOT_TOKEN:
        logger.warning("[SLACK] SLACK_BOT_TOKEN not configured; cannot report")
        return ""

    channel = _channel()
    if not channel:
        logger.warning("[SLACK] no channel configured")
        return ""

    parent_ts = _ensure_thread(app_name, status, channel, details or {}, thread_key=thread_key)
    # Detail goes in a subthread reply so the parent stays as the clean status header.
    blocks = _blocks(status, detail, session_link, is_infra, hitl_action_id)
    text = f"{app_name}: {status}"
    if not detail:
        detail = "✅ Application deployed successfully." if status == "Healthy" else "RCA report below."
        blocks = _blocks(status, detail, session_link, is_infra, hitl_action_id)

    try:
        resp = _send({"channel": channel, "text": f"[{app_name}] {status} — RCA",
                      "blocks": blocks, **({"thread_ts": parent_ts} if parent_ts else {})})
        if resp:
            logger.info(f"[SLACK] posted {status} report for {app_name} @ {resp} (thread={parent_ts})")
            return resp
    except Exception as e:  # noqa: BLE001
        logger.error(f"[SLACK] report_app_status error: {e}")
    return ""


async def post_rca_report(app_name: str, rca_text: str, status: str = "Failed",
                          session_link: str = "", hitl_action_id: str = "",
                          is_infra: bool = False, thread_key: str = "") -> str:
    """Post the full RCA report as a (sub)thread reply.

    Called after the worker completes an RCA. If ``thread_key`` is provided (a
    unique per-incident id) this creates/uses a fresh parent thread for THAT run;
    otherwise it reuses the app's single thread (legacy behaviour).
    """
    if not SLACK_BOT_TOKEN:
        return ""
    channel = _channel()
    if not channel:
        return ""
    parent_ts = ""
    if thread_key:
        # Force a NEW parent thread per incident run — no reuse of a stale app thread.
        parent_ts = _ensure_thread(app_name, status, channel, None, thread_key=thread_key)
    else:
        parent_ts = _get_thread_ts(app_name)
    blocks = _blocks(status, rca_text, session_link, is_infra, hitl_action_id)
    payload = {"channel": channel, "text": f"{app_name} RCA", "blocks": blocks}
    if parent_ts:
        payload["thread_ts"] = parent_ts
    resp = _send(payload)
    if resp:
        logger.info(f"[SLACK] posted RCA report for {app_name} @ {resp} (thread={parent_ts})")
    return resp or ""
