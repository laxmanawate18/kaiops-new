"""
Authentication Endpoint Rate Limiter Middleware.

Implements an in-memory sliding-window rate limiter on sensitive authentication
endpoints (/api/v1/auth/login, /api/v1/auth/register, /api/v1/auth/refresh)
to mitigate brute-force and credential-stuffing attacks.
"""

import time
import asyncio
import logging
from collections import defaultdict, deque
from typing import Dict, Deque, Set
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import status

logger = logging.getLogger(__name__)

# Endpoints subject to strict rate limiting
RATE_LIMITED_PATHS: Set[str] = {
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/refresh",
    "/api/v1/auth/password",
}

# Rate limit configuration: 10 requests per 60 seconds per IP
DEFAULT_MAX_REQUESTS = 10
DEFAULT_WINDOW_SECONDS = 60


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter for sensitive authentication endpoints."""

    def __init__(
        self,
        app,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # In-memory storage: IP -> deque of request timestamps
        self.request_history: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()
        self._last_cleanup = time.time()

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from X-Forwarded-For header or direct client."""
        x_forwarded_for = request.headers.get("x-forwarded-for")
        if x_forwarded_for:
            # First IP in the list is the original client
            return x_forwarded_for.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown_client"

    async def _cleanup_stale_entries(self, current_time: float):
        """Prune IP records that have no requests within the sliding window."""
        # Clean up at most once every 5 minutes
        if current_time - self._last_cleanup < 300:
            return
        self._last_cleanup = current_time
        stale_ips = []
        for ip, timestamps in self.request_history.items():
            while timestamps and timestamps[0] <= current_time - self.window_seconds:
                timestamps.popleft()
            if not timestamps:
                stale_ips.append(ip)
        for ip in stale_ips:
            self.request_history.pop(ip, None)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Only apply rate limiting to targeted auth endpoints
        if path not in RATE_LIMITED_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = time.time()
        cutoff = now - self.window_seconds

        async with self._lock:
            await self._cleanup_stale_entries(now)
            timestamps = self.request_history[client_ip]

            # Remove timestamps outside the sliding window
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()

            # Check if limit exceeded
            if len(timestamps) >= self.max_requests:
                oldest = timestamps[0]
                retry_after = max(1, int(oldest + self.window_seconds - now))
                logger.warning(
                    f"Rate limit exceeded for IP {client_ip} on {path}. "
                    f"Count={len(timestamps)}/{self.max_requests}, retry_after={retry_after}s"
                )
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Too many requests. Please try again later.",
                        "error": "rate_limit_exceeded",
                        "retry_after_seconds": retry_after
                    },
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(self.max_requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(oldest + self.window_seconds)),
                    }
                )

            # Record this request
            timestamps.append(now)
            remaining = self.max_requests - len(timestamps)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
