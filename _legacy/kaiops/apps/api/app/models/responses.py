"""
Standard response models for all API endpoints.

Ensures consistent response format across entire application.
"""

from typing import Optional, Dict, Any, List, Generic, TypeVar
from pydantic import BaseModel, Field
from datetime import datetime

T = TypeVar("T")


class ErrorResponse(BaseModel):
    """Standard error response for all endpoints."""
    success: bool = False
    error: str = Field(..., description="Error code (e.g., 'validation_error')")
    message: str = Field(..., description="User-friendly error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Field-specific error details")
    request_id: str = Field(..., description="Request correlation ID for tracing")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": "validation_error",
                "message": "Invalid request parameters",
                "details": {"email": "Invalid email format"},
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2025-11-24T10:30:00Z"
            }
        }


class SuccessResponse(BaseModel):
    """Standard success response wrapper for single resources."""
    success: bool = True
    message: Optional[str] = Field(None, description="Optional success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    request_id: str = Field(..., description="Request correlation ID")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"id": "123", "name": "Example"},
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2025-11-24T10:30:00Z"
            }
        }


class PaginationMeta(BaseModel):
    """Pagination metadata for offset-based pagination."""
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether next page exists")
    has_previous: bool = Field(..., description="Whether previous page exists")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response."""
    success: bool = True
    data: List[Dict[str, Any]] = Field(..., description="List of items")
    pagination: PaginationMeta = Field(..., description="Pagination information")
    request_id: str = Field(..., description="Request correlation ID")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": [{"id": "1", "name": "Item 1"}],
                "pagination": {
                    "total": 100,
                    "page": 1,
                    "page_size": 20,
                    "total_pages": 5,
                    "has_next": True,
                    "has_previous": False
                },
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2025-11-24T10:30:00Z"
            }
        }


class CursorPaginationMeta(BaseModel):
    """Pagination metadata for cursor-based pagination."""
    total: Optional[int] = Field(None, description="Total number of items (optional)")
    limit: int = Field(..., description="Items requested")
    next_cursor: Optional[str] = Field(None, description="Cursor for next page")
    prev_cursor: Optional[str] = Field(None, description="Cursor for previous page")
    has_next: bool = Field(..., description="Whether next page exists")
    has_previous: bool = Field(..., description="Whether previous page exists")


class CursorPaginatedResponse(BaseModel):
    """Standard cursor-paginated response (more efficient for large datasets)."""
    success: bool = True
    data: List[Dict[str, Any]] = Field(..., description="List of items")
    pagination: CursorPaginationMeta = Field(..., description="Pagination information")
    request_id: str = Field(..., description="Request correlation ID")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class BulkOperationResponse(BaseModel):
    """Response for bulk operations."""
    success: bool = True
    processed: int = Field(..., description="Number of successfully processed items")
    failed: int = Field(..., description="Number of failed items")
    total: int = Field(..., description="Total items in request")
    errors: Optional[List[Dict[str, Any]]] = Field(None, description="Detailed error information")
    request_id: str = Field(..., description="Request correlation ID")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class AsyncOperationResponse(BaseModel):
    """Response for async operations (202 Accepted)."""
    success: bool = True
    message: str = Field(..., description="Operation queued successfully")
    task_id: str = Field(..., description="Unique task identifier")
    status_url: Optional[str] = Field(None, description="URL to check task status")
    request_id: str = Field(..., description="Request correlation ID")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class HealthCheckResponse(BaseModel):
    """Health check response."""
    success: bool = Field(..., description="Overall health status")
    status: str = Field(..., description="Status: 'healthy', 'degraded', 'unhealthy'")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    components: Dict[str, Dict[str, Any]] = Field(..., description="Component health status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "status": "healthy",
                "timestamp": "2025-11-24T10:30:00Z",
                "components": {
                    "database": {"status": "healthy", "response_time_ms": 12},
                    "redis": {"status": "healthy", "response_time_ms": 5},
                    "argocd": {"status": "degraded", "error": "Connection timeout"}
                }
            }
        }


class PaginationParams(BaseModel):
    """Standard pagination input parameters."""
    page: int = Field(1, ge=1, description="Page number")
    page_size: int = Field(20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="Sort order")


class CursorPaginationParams(BaseModel):
    """Cursor-based pagination input parameters."""
    cursor: Optional[str] = Field(None, description="Pagination cursor from previous response")
    limit: int = Field(20, ge=1, le=100, description="Items to return")
    sort_by: Optional[str] = Field("created_at", description="Field to sort by")
    sort_order: str = Field("desc", pattern="^(asc|desc)$", description="Sort order")
