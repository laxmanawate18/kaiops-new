"""
ADK Route Authentication Middleware.

Enforces authentication on ADK endpoints (/list-apps, /run, /run_sse, /apps/*)
to prevent unauthenticated access to the underlying LLM agent execution plane.
"""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from fastapi import status

logger = logging.getLogger(__name__)

# List of ADK endpoints that must be protected with JWT authentication
ADK_EXACT_PATHS = {"/list-apps", "/run", "/run_sse"}
ADK_PATH_PREFIXES = ("/apps/", "/eval/")


class ADKAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that requires JWT authentication for ADK execution endpoints."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Check if the requested path is an ADK endpoint
        is_adk_route = path in ADK_EXACT_PATHS or any(path.startswith(prefix) for prefix in ADK_PATH_PREFIXES)

        if is_adk_route:
            # Allow CORS preflight requests
            if request.method == "OPTIONS":
                return await call_next(request)

            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                logger.warning(f"Unauthenticated attempt to access ADK endpoint: {request.method} {path}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Authentication required for ADK endpoints",
                        "error": "missing_or_invalid_authorization_header"
                    },
                    headers={"WWW-Authenticate": "Bearer"}
                )

            token = auth_header[7:].strip()
            try:
                # Lazy import to avoid circular dependency at startup
                from app.auth.utils import verify_token
                verify_token(token, expected_type="access")
            except Exception as e:
                logger.warning(f"Invalid token supplied to ADK endpoint {path}: {e}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Invalid or expired access token",
                        "error": "unauthorized"
                    },
                    headers={"WWW-Authenticate": "Bearer"}
                )

        return await call_next(request)
