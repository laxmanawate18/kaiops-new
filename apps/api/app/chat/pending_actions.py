"""Firestore-backed registry of actions awaiting human approval.

An action is stored when the agent requests a guarded tool (require_confirmation).
It can only be executed via consume_pending(), which removes the record exactly once.

Records expire after PENDING_TTL_SECONDS (default 300) so stale approvals can't
linger forever. Unlike the previous in-process dict (which was lost on Cloud Run
scale-to-zero / multi-instance recycles — breaking async HITL approvals that
arrive minutes later via Slack), this persists to Firestore so it survives any
instance churn.

The module exposes the exact same public API as before (create_pending,
get_pending, consume_pending, reject_pending) so existing callers
(chat agent_service, chat routes, runtime routes) do not change.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import secrets
import os

from app.database.firestore_config import FirestoreConfig

# Firestore collection that stores pending approval records.
_COLLECTION = "pending_actions"

PENDING_TTL_SECONDS = int(os.environ.get("PENDING_TTL_SECONDS", "300"))


def _pending_ref():
    return FirestoreConfig.get_client().collection(_COLLECTION)


def _now() -> datetime:
    """Timezone-aware UTC datetime for comparing TTLs.

    Firestore persists datetimes with timezone info, so we compare aware-to-aware
    to avoid the `TypeError: can't compare offset-naive and offset-aware datetimes`.
    """
    return datetime.now(timezone.utc)


def _as_aware(value: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (assume UTC if naive)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _is_expired(record: Dict[str, Any]) -> bool:
    created = record.get("created_at")
    expires = record.get("expires_at")
    now = _now()
    # Prefer explicit expires_at if stored; else fall back to created_at + TTL.
    if isinstance(expires, datetime):
        return now > _as_aware(expires)
    if isinstance(created, datetime):
        return now > (_as_aware(created) + timedelta(seconds=PENDING_TTL_SECONDS))
    return False


def _purge_expired() -> None:
    """Best-effort cleanup of expired records (call without holding a lock)."""
    try:
        docs = _pending_ref().stream()
        for doc in docs:
            data = doc.to_dict()
            if _is_expired(data):
                doc.reference.delete()
    except Exception:  # noqa: BLE001
        # Cleanup is best-effort; never block on it. Firestore may be briefly down.
        pass


def create_pending(session_id: str, user_id: str, tool_name: str, args: Optional[Dict[str, Any]] = None) -> str:
    """Store a pending action; returns an opaque approval token."""
    token = secrets.token_urlsafe(32)
    now = _now()
    record = {
        "token": token,
        "session_id": session_id,
        "user_id": user_id,
        "tool_name": tool_name,
        "args": dict(args) if args else None,
        "status": "pending",
        "created_at": now,
        "expires_at": now + timedelta(seconds=PENDING_TTL_SECONDS),
    }
    _pending_ref().document(token).set(record)
    # Best-effort TTL cleanup.
    _purge_expired()
    return token


def get_pending(token: str) -> Optional[Dict[str, Any]]:
    """Return the pending record for a valid, unexpired token, else None."""
    try:
        doc = _pending_ref().document(token).get()
    except Exception:  # noqa: BLE001
        return None
    if not doc.exists:
        return None
    record = doc.to_dict()
    if not record or _is_expired(record):
        return None
    return dict(record)


def consume_pending(token: str) -> Optional[Dict[str, Any]]:
    """Atomically remove and return the pending record (single-use).

    Deletes the Firestore doc and returns its contents. This prevents a
    (previously double-clicked) approve from executing the action twice.
    """
    try:
        doc = _pending_ref().document(token).get()
    except Exception:  # noqa: BLE001
        return None
    if not doc.exists:
        return None
    record = doc.to_dict()
    if not record or _is_expired(record):
        # Expired: clean it up and treat as absent.
        try:
            doc.reference.delete()
        except Exception:  # noqa: BLE001
            pass
        return None
    try:
        doc.reference.delete()
    except Exception:  # noqa: BLE001
        return None
    return dict(record)


def reject_pending(token: str) -> bool:
    """Cancel a pending action without executing anything."""
    try:
        doc = _pending_ref().document(token).get()
    except Exception:  # noqa: BLE001
        return False
    if not doc.exists:
        return False
    try:
        doc.reference.delete()
    except Exception:  # noqa: BLE001
        return False
    return True
