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


def _get_thread_ts(app_name: str) -> Optional[str]:
    try:
        doc = _thread_ref().document(app_name).get()
        return doc.to_dict().get("thread_ts") if doc.exists else None
    except Exception:  # noqa: BLE001
        return None


def _save_thread_ts(app_name: str, ts: str) -> None:
    try:
        _thread_ref().document(app_name).set({"thread_ts": ts, "app_name": app_name})
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[SLACK] save thread ts failed: {e}")


def _blocks(status: str, detail: str, session_link: str = "", is_infra: bool = False) -> list:
    """Build a rich block card for the app status thread."""
    color = "good" if status == "Healthy" else "danger"
    header = f"[{'✅ Healthy' if status == 'Healthy' else '❌ Failed'}]"
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": header, "emoji": True},
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": detail or "_No detail_"}},
    ]
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


async def report_app_status(app_name: str, status: str, detail: str = "",
                            cloud_provider: str = "gcp", is_infra: bool = False,
                            session_link: str = "") -> str:
    """Create or reply to the per-application Slack thread with a status card.

    Returns the message ts (parent or reply). Threadable/idempotent per app.
    """
    if not SLACK_BOT_TOKEN:
        logger.warning("[SLACK] SLACK_BOT_TOKEN not configured; cannot report")
        return ""

    blocks = _blocks(status, detail, session_link, is_infra)
    text = f"[{'Healthy' if status == 'Healthy' else 'Failed'}] {app_name}"
    channel = _channel()
    if not channel:
        logger.warning("[SLACK] no channel configured")
        return ""

    existing_ts = _get_thread_ts(app_name)
    try:
        if existing_ts:
            # Reply in the existing thread.
            resp = _send({"channel": channel, "thread_ts": existing_ts,
                          "text": text, "blocks": blocks})
            if resp:
                logger.info(f"[SLACK] replied to thread for {app_name} @ {resp}")
                return resp
        # No thread yet -> create the parent message.
        resp = _send({"channel": channel, "text": text, "blocks": blocks})
        if resp:
            _save_thread_ts(app_name, resp)
            logger.info(f"[SLACK] created thread for {app_name} @ {resp}")
            return resp
    except Exception as e:  # noqa: BLE001
        logger.error(f"[SLACK] report_app_status error: {e}")
    return ""
