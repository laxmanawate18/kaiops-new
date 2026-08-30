"""
HTTP status code constants for consistent response status codes.

Usage:
    @router.post("/apps", status_code=HTTPStatus.CREATED)
    async def create_app():
        pass
    
    @router.delete("/apps/{id}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_app():
        pass
"""


class HTTPStatus:
    """Standardized HTTP status codes for all endpoints."""
    
    # 2xx Success
    OK = 200  # GET, general success, synchronous operations
    CREATED = 201  # POST - new resource created
    ACCEPTED = 202  # POST/PUT - async operation queued
    NO_CONTENT = 204  # DELETE, no response body
    PARTIAL_CONTENT = 206  # GET with Range header for pagination
    
    # 4xx Client Errors
    BAD_REQUEST = 400  # Validation/syntax error
    UNAUTHORIZED = 401  # Authentication required/failed
    FORBIDDEN = 403  # Authorization/permission denied
    NOT_FOUND = 404  # Resource doesn't exist
    CONFLICT = 409  # Resource already exists/state conflict
    GONE = 410  # Resource permanently deleted
    UNPROCESSABLE_ENTITY = 422  # Semantic validation error
    TOO_MANY_REQUESTS = 429  # Rate limit exceeded
    
    # 5xx Server Errors
    INTERNAL_SERVER_ERROR = 500  # Unexpected server error
    BAD_GATEWAY = 502  # External service unavailable
    SERVICE_UNAVAILABLE = 503  # Server overloaded/maintenance
    GATEWAY_TIMEOUT = 504  # External service timeout
