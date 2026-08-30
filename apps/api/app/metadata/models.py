"""
Pydantic models for application metadata storage.

Defines data structures for storing GitHub, ArgoCD, Grafana, and Cost integration metadata.
"""
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Dict, Any, List
from datetime import datetime


class GitHubMetadata(BaseModel):
    """GitHub integration metadata for an application."""
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


class ArgoCDMetadata(BaseModel):
    """ArgoCD integration metadata for an application."""
    enabled: bool = False
    app_name: Optional[str] = None
    project: Optional[str] = "default"
    namespace: Optional[str] = None
    server: Optional[str] = None  # ArgoCD server URL
    
    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "app_name": "guestbook",
                "project": "default",
                "namespace": "argocd",
                "server": "https://argocd.example.com"
            }
        }


class GrafanaMetadata(BaseModel):
    """Grafana integration metadata for an application."""
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
                "dashboard_url": "https://grafana.example.com/d/12345",
                "datasource": "Prometheus",
                "alert_uid": "alert_123"
            }
        }


class CostMetadata(BaseModel):
    """Cost tracking integration metadata for an application."""
    enabled: bool = False
    cost_center: Optional[str] = None
    budget_alert_threshold: Optional[float] = None  # in percentage
    tags: Optional[Dict[str, str]] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "cost_center": "engineering",
                "budget_alert_threshold": 80.0,
                "tags": {"environment": "production", "team": "platform"}
            }
        }


class ApplicationMetadata(BaseModel):
    """Complete application metadata storing all integration configurations."""
    app_name: str = Field(..., description="Unique application name")
    description: Optional[str] = None
    environment: Optional[str] = None  # production, staging, development
    team: Optional[str] = None
    
    # Integration configurations
    github: GitHubMetadata = Field(default_factory=GitHubMetadata)
    argocd: ArgoCDMetadata = Field(default_factory=ArgoCDMetadata)
    grafana: GrafanaMetadata = Field(default_factory=GrafanaMetadata)
    cost: CostMetadata = Field(default_factory=CostMetadata)
    
    # Metadata tracking
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    
    # Additional fields
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None
    
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
                    "branch": "main",
                    "repo_url": "https://github.com/argoproj/argocd-example-apps"
                },
                "argocd": {
                    "enabled": True,
                    "app_name": "guestbook",
                    "project": "default",
                    "namespace": "argocd",
                    "server": "https://argocd.example.com"
                },
                "grafana": {
                    "enabled": True,
                    "dashboard_id": "guestbook-dash",
                    "dashboard_url": "https://grafana.example.com/d/guestbook",
                    "datasource": "Prometheus"
                },
                "cost": {
                    "enabled": False,
                    "cost_center": "engineering"
                },
                "tags": ["demo", "argocd"],
                "created_by": "admin",
                "updated_by": "admin"
            }
        }
