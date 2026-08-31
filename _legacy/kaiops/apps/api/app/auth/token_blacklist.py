"""In-memory JWT blacklist for logout/revocation.

Tokens are stored until their natural expiry — after that they're invalid anyway.
Suitable for single-instance deployments; swap for Redis/Firestore for multi-instance.
"""
import time
import threading

_blacklist: dict[str, float] = {}  # jti -> exp timestamp
_lock = threading.Lock()


def revoke(jti: str, exp: float) -> None:
    """Add a token ID to the blacklist until its natural expiry."""
    with _lock:
        _cleanup()
        _blacklist[jti] = exp


def is_revoked(jti: str) -> bool:
    """Check whether a token ID has been revoked."""
    with _lock:
        _cleanup()
        return jti in _blacklist


def _cleanup() -> None:
    """Drop expired entries. Must be called while holding _lock."""
    now = time.time()
    expired = [jti for jti, exp in _blacklist.items() if exp <= now]
    for jti in expired:
        del _blacklist[jti]
