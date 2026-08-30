"""Server-side registry of actions awaiting human approval.

An action is stored when the agent requests a guarded tool; it can only be
executed via consume_pending(), which removes the record exactly once.
Records expire after PENDING_TTL_SECONDS (default 300) so stale approvals
can't linger forever.
"""

import os
import secrets
import threading
import time
from typing import Any, Dict, Optional

PENDING_TTL_SECONDS = int(os.environ.get("PENDING_TTL_SECONDS", "300"))

_pending: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def _purge_expired_locked() -> None:
    """Remove expired records. Caller must hold _lock."""
    now = time.time()
    expired = [t for t, rec in _pending.items() if now - rec["created_at"] > PENDING_TTL_SECONDS]
    for t in expired:
        del _pending[t]


def create_pending(session_id: str, user_id: str, tool_name: str, args: Optional[Dict[str, Any]] = None) -> str:
    """Store a pending action; returns an opaque approval token."""
    token = secrets.token_urlsafe(32)
    with _lock:
        _purge_expired_locked()
        _pending[token] = {
            "session_id": session_id,
            "user_id": user_id,
            "tool_name": tool_name,
            "args": dict(args) if args else None,
            "created_at": time.time(),
        }
    return token


def get_pending(token: str) -> Optional[Dict[str, Any]]:
    """Return the pending record for a valid, unexpired token, else None."""
    with _lock:
        _purge_expired_locked()
        record = _pending.get(token)
        return dict(record) if record else None


def consume_pending(token: str) -> Optional[Dict[str, Any]]:
    """Atomically remove and return the pending record (single-use)."""
    with _lock:
        _purge_expired_locked()
        record = _pending.pop(token, None)
        return dict(record) if record else None


def reject_pending(token: str) -> bool:
    """Cancel a pending action without executing anything."""
    with _lock:
        _purge_expired_locked()
        return _pending.pop(token, None) is not None
