"""
Request and response models for metadata API endpoints.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class GitHubMetadataRequest(BaseModel):
    """GitHub metadata for API requests."""
    enabled: bool = False
    repo_owner: Optional[str] = None
    repo_name: Optional[str] = None
    branch: Optional[str] = "main"
    repo_url: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "repo_owner": "mycompany",
                "repo_name": "app-repo",
                "branch": "main",
                "repo_url": "https://github.com/mycompany/app-repo"
            }
        }


class ArgoCDMetadataRequest(BaseModel):
    """ArgoCD metadata for API requests."""
    enabled: bool = False
    app_name: Optional[str] = None
    project: Optional[str] = "default"
    namespace: Optional[str] = None
    server: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "app_name": "guestbook",
                "project": "default",
                "namespace": "argocd"
            }
        }


class GrafanaMetadataRequest(BaseModel):
    """Grafana metadata for API requests."""
    enabled: bool = False
    dashboard_id: Optional[str] = None
    dashboard_url: Optional[str] = None
    datasource: Optional[str] = None
    alert_uid: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "dashboard_id": "12345",
                "dashboard_url": "https://grafana.example.com/d/12345"
            }
        }


class CostMetadataRequest(BaseModel):
    """Cost metadata for API requests."""
    enabled: bool = False
    cost_center: Optional[str] = None
    budget_alert_threshold: Optional[float] = None
    tags: Optional[Dict[str, str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "cost_center": "engineering",
                "budget_alert_threshold": 80.0
            }
        }


class CreateMetadataRequest(BaseModel):
    """Request model for creating application metadata."""
    app_name: str = Field(..., description="Application name")
    description: Optional[str] = None
    environment: Optional[str] = None
    team: Optional[str] = None
    github: Optional[GitHubMetadataRequest] = None
    argocd: Optional[ArgoCDMetadataRequest] = None
    grafana: Optional[GrafanaMetadataRequest] = None
    cost: Optional[CostMetadataRequest] = None
    tags: Optional[List[str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "app_name": "guestbook",
                "description": "Sample guestbook application",
                "environment": "production",
                "team": "platform",
                "github": {
                    "enabled": True,
                    "repo_owner": "argoproj",
                    "repo_name": "argocd-example-apps",
                    "branch": "main"
                },
                "argocd": {
                    "enabled": True,
                    "app_name": "guestbook",
                    "project": "default"
                }
            }
        }


class UpdateMetadataRequest(BaseModel):
    """Request model for updating application metadata."""
    description: Optional[str] = None
    environment: Optional[str] = None
    team: Optional[str] = None
    github: Optional[GitHubMetadataRequest] = None
    argocd: Optional[ArgoCDMetadataRequest] = None
    grafana: Optional[GrafanaMetadataRequest] = None
    cost: Optional[CostMetadataRequest] = None
    tags: Optional[List[str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "description": "Updated description",
                "environment": "staging"
            }
        }


class GitHubMetadataResponse(BaseModel):
    """GitHub metadata for API responses."""
    enabled: bool
    repo_owner: Optional[str]
    repo_name: Optional[str]
    branch: Optional[str]
    repo_url: Optional[str]


class ArgoCDMetadataResponse(BaseModel):
    """ArgoCD metadata for API responses."""
    enabled: bool
    app_name: Optional[str]
    project: Optional[str]
    namespace: Optional[str]
    server: Optional[str]


class GrafanaMetadataResponse(BaseModel):
    """Grafana metadata for API responses."""
    enabled: bool
    dashboard_id: Optional[str]
    dashboard_url: Optional[str]
    datasource: Optional[str]
    alert_uid: Optional[str]


class CostMetadataResponse(BaseModel):
    """Cost metadata for API responses."""
    enabled: bool
    cost_center: Optional[str]
    budget_alert_threshold: Optional[float]
    tags: Optional[Dict[str, str]]


class MetadataResponse(BaseModel):
    """Response model for application metadata."""
    app_name: str
    description: Optional[str]
    environment: Optional[str]
    team: Optional[str]
    github: GitHubMetadataResponse
    argocd: ArgoCDMetadataResponse
    grafana: GrafanaMetadataResponse
    cost: CostMetadataResponse
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str]
    updated_by: Optional[str]
    tags: Optional[List[str]]


class ConfiguredIntegrationsResponse(BaseModel):
    """Response model for configured integrations."""
    app_name: str
    github: bool
    argocd: bool
    grafana: bool
    cost: bool


class SearchResultResponse(BaseModel):
    """Response model for search results."""
    app_name: str
    description: Optional[str]
    team: Optional[str]
    environment: Optional[str]


class ErrorResponse(BaseModel):
    """Standard error response model."""
    error: str
    message: str
    status_code: int = 400
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Application name is required",
                "status_code": 400
            }
        }


class SuccessResponse(BaseModel):
    """Standard success response model."""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Metadata created successfully",
                "data": {"app_name": "guestbook"}
            }
        }
