"""
Custom exception hierarchy for KaiOps application.

Provides:
- RequestContext for correlation IDs and request tracing
- Custom exceptions with context propagation
- Safe error messages (no internal details exposed)
- Structured error information for logging
"""

import uuid
from typing import Optional, Dict, Any
from datetime import datetime


class RequestContext:
    """Context for tracking request metadata across error handling."""
    
    def __init__(self, request_id: str = None, user_id: str = None, endpoint: str = None):
        self.request_id = request_id or str(uuid.uuid4())
        self.user_id = user_id
        self.endpoint = endpoint
        self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "endpoint": self.endpoint,
            "timestamp": self.timestamp
        }


class KaiOpsException(Exception):
    """Base exception for all KaiOps errors."""
    
    def __init__(
        self, 
        message: str,
        status_code: int = 500,
        error_code: str = None,
        details: Dict[str, Any] = None,
        context: RequestContext = None,
        cause: Exception = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.context = context or RequestContext()
        self.cause = cause
        self.internal_message = None  # For detailed logging
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to safe API response format (no internal details)."""
        return {
            "success": False,
            "error": self.error_code,
            "message": self.message,
            "details": self.details if self.details else None,
            "request_id": self.context.request_id,
            "timestamp": self.context.timestamp
        }
    
    def to_log_dict(self) -> Dict[str, Any]:
        """Convert exception to detailed logging format (includes internal details)."""
        return {
            "success": False,
            "error": self.error_code,
            "message": self.message,
            "internal_message": self.internal_message,
            "status_code": self.status_code,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None,
            "context": self.context.to_dict()
        }


# ==================== 400 Errors ====================

class ValidationError(KaiOpsException):
    """Raised when input validation fails (400)."""
    
    def __init__(self, message: str, details: Dict = None, context: RequestContext = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="validation_error",
            details=details,
            context=context
        )


class BadRequestError(KaiOpsException):
    """Raised for malformed requests (400)."""
    
    def __init__(self, message: str, context: RequestContext = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="bad_request",
            context=context
        )


# ==================== 401 Errors ====================

class AuthenticationError(KaiOpsException):
    """Raised when authentication fails (401)."""
    
    def __init__(self, message: str, context: RequestContext = None):
        super().__init__(
            message=message,
            status_code=401,
            error_code="authentication_error",
            context=context
        )


class InvalidTokenError(AuthenticationError):
    """Raised when JWT token is invalid or expired (401)."""
    
    def __init__(self, message: str = "Invalid or expired token", context: RequestContext = None):
        super().__init__(message, context)
        self.error_code = "invalid_token"


class CredentialsError(AuthenticationError):
    """Raised when login credentials are incorrect (401)."""
    
    def __init__(self, context: RequestContext = None):
        super().__init__("Invalid username or password", context)
        self.error_code = "invalid_credentials"


# ==================== 403 Errors ====================

class AuthorizationError(KaiOpsException):
    """Raised when user lacks permissions (403)."""
    
    def __init__(self, message: str = "Insufficient permissions", context: RequestContext = None):
        super().__init__(
            message=message,
            status_code=403,
            error_code="authorization_error",
            context=context
        )


class InsufficientRoleError(AuthorizationError):
    """Raised when user role is insufficient (403)."""
    
    def __init__(self, required_role: str, context: RequestContext = None):
        message = f"This operation requires {required_role} role"
        super().__init__(message, context)
        self.details = {"required_role": required_role}
        self.error_code = "insufficient_role"


# ==================== 404 Errors ====================

class ResourceNotFoundError(KaiOpsException):
    """Raised when resource doesn't exist (404)."""
    
    def __init__(self, resource_type: str, resource_id: str, context: RequestContext = None):
        super().__init__(
            message=f"{resource_type} '{resource_id}' not found",
            status_code=404,
            error_code="resource_not_found",
            details={"resource_type": resource_type, "resource_id": resource_id},
            context=context
        )


# ==================== 409 Errors ====================

class ConflictError(KaiOpsException):
    """Raised when resource already exists or state conflict (409)."""
    
    def __init__(self, message: str, resource_type: str = None, context: RequestContext = None):
        super().__init__(
            message=message,
            status_code=409,
            error_code="conflict",
            details={"resource_type": resource_type} if resource_type else {},
            context=context
        )


class DuplicateResourceError(ConflictError):
    """Raised when trying to create duplicate resource (409)."""
    
    def __init__(self, resource_type: str, identifier: str, context: RequestContext = None):
        message = f"{resource_type} '{identifier}' already exists"
        super().__init__(message, resource_type, context)
        self.error_code = "duplicate_resource"


# ==================== 429 Errors ====================

class RateLimitError(KaiOpsException):
    """Raised when rate limit is exceeded (429)."""
    
    def __init__(self, retry_after_seconds: int = 60, context: RequestContext = None):
        super().__init__(
            message="Too many requests",
            status_code=429,
            error_code="rate_limit_exceeded",
            details={"retry_after_seconds": retry_after_seconds},
            context=context
        )


# ==================== 500 Errors ====================

class DatabaseError(KaiOpsException):
    """Raised when database operation fails (500)."""
    
    def __init__(self, message: str = None, cause: Exception = None, context: RequestContext = None):
        safe_message = "Database operation failed"
        super().__init__(
            message=safe_message,
            status_code=500,
            error_code="database_error",
            context=context,
            cause=cause
        )
        self.internal_message = message


class IntegrationError(KaiOpsException):
    """Raised when external service integration fails (502)."""
    
    def __init__(
        self, 
        service_name: str, 
        message: str = None, 
        cause: Exception = None,
        context: RequestContext = None
    ):
        super().__init__(
            message=f"Failed to connect to {service_name}",
            status_code=502,
            error_code="integration_error",
            details={"service": service_name},
            context=context,
            cause=cause
        )
        self.internal_message = message


class TimeoutError(KaiOpsException):
    """Raised when operation times out (504)."""
    
    def __init__(self, operation: str, timeout_seconds: int, context: RequestContext = None):
        super().__init__(
            message=f"{operation} took too long",
            status_code=504,
            error_code="timeout",
            details={"operation": operation, "timeout_seconds": timeout_seconds},
            context=context
        )


class ServiceUnavailableError(KaiOpsException):
    """Raised when service is unavailable (503)."""
    
    def __init__(self, service_name: str, message: str = None, context: RequestContext = None):
        super().__init__(
            message=f"{service_name} is currently unavailable",
            status_code=503,
            error_code="service_unavailable",
            details={"service": service_name},
            context=context
        )
        self.internal_message = message
