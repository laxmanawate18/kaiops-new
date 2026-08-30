"""Slack notification tool for the KaiOps SRE agent.

Gives the agent the ability to take REAL action after an autonomous RCA: post
the summary + remediation to a Slack channel via an incoming webhook. This is
the "agent tells the team" moment that makes the autonomous loop tangible.

Uses a single Slack **incoming webhook** URL (highest ROI, lowest risk — no bot
token, no scope, no OAuth). Configure SLACK_WEBHOOK_URL and optionally
SLACK_CHANNEL.

Never fabricates: if not configured or the call fails, returns an explicit
message rather than pretending it posted.
"""

import os
import logging
import requests

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "")


def _post_to_slack(text: str, channel: str = "", webhook_url: str = "") -> bool:
    """Post a message via the Slack incoming webhook. Returns True on success."""
    webhook = webhook_url or SLACK_WEBHOOK_URL
    if not webhook:
        logger.error("[SLACK] SLACK_WEBHOOK_URL not configured; cannot post")
        return False

    payload = {"text": text}
    if channel:
        payload["channel"] = channel

    try:
        resp = requests.post(webhook, json=payload, timeout=10)
        if resp.status_code == 200 and resp.text.lower().strip() in ("ok", ""):
            logger.info(f"[SLACK] Posted to Slack (channel={channel or 'default'})")
            return True
        logger.error(f"[SLACK] Webhook returned {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:
        logger.error(f"[SLACK] Post failed: {e}")
        return False


def notify_slack(channel: str, message: str) -> str:
    """Post a message to a Slack channel.

    Args:
        channel: Target Slack channel, e.g. '#incidents' (defaults to SLACK_CHANNEL).
        message: The message text to post (RCA summary, remediation, etc.).

    Returns:
        A confirmation string for the agent.
    """
    channel = channel or SLACK_CHANNEL
    if not message:
        return "Slack notification skipped: empty message."
    ok = _post_to_slack(message, channel=channel)
    if ok:
        return f"Posted to Slack channel '{channel or 'default'}'."
    return "Failed to post to Slack (check SLACK_WEBHOOK_URL configuration)."


__all__ = ["notify_slack"]
