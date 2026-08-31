"""
Middleware for request context management.

Injects request ID and context into all requests for tracing and logging.
Non-breaking: works alongside existing middleware.
"""

import uuid
import time
import logging

from ..exceptions import RequestContext

logger = logging.getLogger(__name__)


class RequestContextMiddleware:
    """
    ASGI Middleware to inject request ID and context into all requests.
    
    - Generates/extracts correlation ID
    - Tracks request duration
    - Adds tracing headers to responses
    - Stores context in request state for handlers
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        """
        ASGI middleware implementation.
        
        Args:
            scope: ASGI scope (connection info)
            receive: ASGI receive channel
            send: ASGI send channel
        """
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Generate or extract request ID from headers
        headers = dict(scope.get("headers", []))
        request_id = headers.get(b"x-request-id", b"").decode() or str(uuid.uuid4())
        
        # Create context
        context = RequestContext(
            request_id=request_id,
            endpoint=f"{scope['method']} {scope['path']}"
        )
        
        # Store in scope state for access in handlers
        if "state" not in scope:
            scope["state"] = {}
        scope["state"]["request_id"] = request_id
        scope["state"]["context"] = context
        
        # Start timer for request duration
        start_time = time.time()
        
        async def send_with_context(message):
            """Wrap send to add context headers to response."""
            if message["type"] == "http.response.start":
                # Add request ID and response time headers
                duration_ms = (time.time() - start_time) * 1000
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                headers.append((b"x-response-time-ms", str(round(duration_ms, 2)).encode()))
                message["headers"] = headers
                
                # Log request
                logger.info(
                    "http_request",
                    extra={
                        "request_id": request_id,
                        "method": scope["method"],
                        "path": scope["path"],
                        "status_code": message.get("status", 0),
                        "duration_ms": round(duration_ms, 2),
                    }
                )
            
            await send(message)
        
        try:
            await self.app(scope, receive, send_with_context)
        except Exception as e:
            # Log unexpected exceptions
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "request_exception",
                extra={
                    "request_id": request_id,
                    "method": scope["method"],
                    "path": scope["path"],
                    "duration_ms": round(duration_ms, 2),
                    "error": str(e),
                }
            )
            raise
