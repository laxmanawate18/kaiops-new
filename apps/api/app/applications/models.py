from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
import re

class ApplicationStatus(str, Enum):
    """Application status enumeration."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    SUSPENDED = "suspended"

class CloudProvider(str, Enum):
    """Cloud provider enumeration."""
    GCP = "gcp"
    AZURE = "azure"
    AWS = "aws"

class ApplicationCreate(BaseModel):
    """Model for creating a new application with cloud-provider support."""
    # Common fields
    application_name: str = Field(..., min_length=2, max_length=100, description="Name of the application")
    application_owner: str = Field(..., description="Application owner (username or team)")
    status: Optional[ApplicationStatus] = ApplicationStatus.ACTIVE
    github_repo: Optional[str] = Field(None, description="GitHub repository URL")
    argocd_app_name: Optional[str] = Field(None, min_length=2, max_length=100, description="ArgoCD application name")
    grafana_dashboard: Optional[str] = Field(None, description="Grafana dashboard name or URL")
    grafana_alert_name: Optional[str] = Field(None, description="Grafana alert name")
    description: Optional[str] = Field(None, max_length=500, description="Application description")
    application_criticality: Optional[str] = Field("medium", description="Application criticality level")
    custom_metadata: Optional[List[Dict[str, str]]] = Field(default_factory=list, description="Custom metadata key-value pairs")
    
    # Cloud provider selection
    cloud_provider: Optional[CloudProvider] = CloudProvider.GCP
    
    # Legacy GCP fields (optional for backward compatibility)
    gcp_project_id: Optional[str] = Field(None, min_length=3, max_length=100, description="GCP Project ID")
    gke_cluster_name: Optional[str] = Field(None, min_length=2, max_length=100, description="GKE cluster name")
    namespace: Optional[str] = Field(None, min_length=2, max_length=100, description="Kubernetes namespace")
    
    # GCP specific fields
    gcp_log_resource: Optional[str] = Field(None, description="GCP log resource type")
    deployment_name: Optional[str] = Field(None, description="Deployment name")
    pod_name: Optional[str] = Field(None, description="Pod name pattern")
    
    # Azure specific fields
    azure_subscription_id: Optional[str] = Field(None, description="Azure Subscription ID")
    aks_cluster_name: Optional[str] = Field(None, description="AKS cluster name")
    azure_deployment_name: Optional[str] = Field(None, description="Azure deployment name")
    azure_pod_name: Optional[str] = Field(None, description="Azure pod name pattern")
    azure_namespace: Optional[str] = Field(None, description="Azure namespace")
    resource_group: Optional[str] = Field(None, description="Azure resource group")
    workspace: Optional[str] = Field(None, description="Azure workspace")
    workspace_resource_group: Optional[str] = Field(None, description="Azure workspace resource group")
    ingress_name: Optional[str] = Field(None, description="Ingress name")
    ingress_public_ip: Optional[str] = Field(None, description="Ingress public IP")
    ingress_namespace: Optional[str] = Field(None, description="Ingress namespace")
    
    # AWS specific fields
    aws_account_id: Optional[str] = Field(None, description="AWS Account ID")
    eks_cluster_name: Optional[str] = Field(None, description="EKS cluster name")
    cloudwatch_log_group_path: Optional[str] = Field(None, description="CloudWatch log group path")
    aws_deployment_name: Optional[str] = Field(None, description="AWS deployment name")
    aws_pod_name: Optional[str] = Field(None, description="AWS pod name pattern")
    aws_namespace: Optional[str] = Field(None, description="AWS namespace")
    
    @validator('application_name')
    def validate_application_name(cls, v):
        """Validate application name format."""
        if not re.match(r'^[a-zA-Z0-9\s_-]+$', v):
            raise ValueError('Application name can only contain letters, numbers, spaces, hyphens, and underscores')
        return v.strip()
    
    @validator('github_repo')
    def validate_github_repo(cls, v):
        """Validate GitHub repository URL format."""
        if v is None:
            return v
        # Support both full URLs and org/repo format
        github_patterns = [
            r'^https?://github\.com/[\w-]+/[\w.-]+/?$',  # Full URL
            r'^[\w-]+/[\w.-]+$'  # org/repo format
        ]
        if not any(re.match(pattern, v) for pattern in github_patterns):
            raise ValueError('Invalid GitHub repository format. Use "org/repo" or full URL')
        return v.strip()
    
    @validator('gcp_project_id', always=True)
    def validate_gcp_project_id(cls, v, values):
        """Validate GCP Project ID only if GCP provider is selected."""
        if values.get('cloud_provider') == CloudProvider.GCP and not v:
            raise ValueError('GCP Project ID is required when GCP is selected')
        if v and not re.match(r'^[a-z][a-z0-9-]{4,28}[a-z0-9]$', v):
            raise ValueError('Invalid GCP project ID format (6-30 chars, lowercase, start with letter)')
        return v.strip() if v else None
    
    @validator('gke_cluster_name', always=True)
    def validate_gke_cluster_name(cls, v, values):
        """Validate GKE cluster name only if GCP provider is selected."""
        if values.get('cloud_provider') == CloudProvider.GCP and not v:
            raise ValueError('GKE cluster name is required when GCP is selected')
        if v and not re.match(r'^[a-z][a-z0-9-]*[a-z0-9]$', v):
            raise ValueError('GKE cluster name must start with letter, contain only lowercase letters, numbers, and hyphens')
        return v.strip() if v else None
    
    @validator('namespace', always=True)
    def validate_namespace(cls, v, values):
        """Validate namespace only if GCP provider is selected."""
        if values.get('cloud_provider') == CloudProvider.GCP and not v:
            raise ValueError('Namespace is required when GCP is selected')
        if v and not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', v):
            raise ValueError('Namespace must be lowercase alphanumeric with hyphens')
        return v.strip() if v else None
    
    @validator('azure_subscription_id', always=True)
    def validate_azure_subscription_id(cls, v, values):
        """Validate Azure Subscription ID only if Azure provider is selected."""
        if values.get('cloud_provider') == CloudProvider.AZURE and not v:
            raise ValueError('Azure Subscription ID is required when Azure is selected')
        if v and not re.match(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$', v):
            raise ValueError('Invalid Azure Subscription ID format (must be UUID)')
        return v.strip() if v else None
    
    @validator('aws_account_id', always=True)
    def validate_aws_account_id(cls, v, values):
        """Validate AWS Account ID only if AWS provider is selected."""
        if values.get('cloud_provider') == CloudProvider.AWS and not v:
            raise ValueError('AWS Account ID is required when AWS is selected')
        if v and not re.match(r'^\d{12}$', v):
            raise ValueError('Invalid AWS Account ID format (must be 12 digits)')
        return v.strip() if v else None

class ApplicationUpdate(BaseModel):
    """Model for updating an existing application."""
    # Common fields
    application_name: Optional[str] = Field(None, min_length=2, max_length=100)
    application_owner: Optional[str] = None
    status: Optional[ApplicationStatus] = None
    github_repo: Optional[str] = None
    argocd_app_name: Optional[str] = Field(None, min_length=2, max_length=100)
    grafana_dashboard: Optional[str] = None
    grafana_alert_name: Optional[str] = None
    description: Optional[str] = Field(None, max_length=500)
    application_criticality: Optional[str] = None
    custom_metadata: Optional[List[Dict[str, str]]] = None
    
    # Cloud provider
    cloud_provider: Optional[CloudProvider] = None
    
    # Legacy GCP fields
    gcp_project_id: Optional[str] = Field(None, min_length=3, max_length=100)
    gke_cluster_name: Optional[str] = Field(None, min_length=2, max_length=100)
    namespace: Optional[str] = Field(None, min_length=2, max_length=100)
    
    # GCP specific fields
    gcp_log_resource: Optional[str] = None
    deployment_name: Optional[str] = None
    pod_name: Optional[str] = None
    
    # Azure specific fields
    azure_subscription_id: Optional[str] = None
    aks_cluster_name: Optional[str] = None
    azure_deployment_name: Optional[str] = None
    azure_pod_name: Optional[str] = None
    azure_namespace: Optional[str] = None
    resource_group: Optional[str] = None
    workspace: Optional[str] = None
    workspace_resource_group: Optional[str] = None
    ingress_name: Optional[str] = None
    ingress_public_ip: Optional[str] = None
    ingress_namespace: Optional[str] = None
    
    # AWS specific fields
    aws_account_id: Optional[str] = None
    eks_cluster_name: Optional[str] = None
    cloudwatch_log_group_path: Optional[str] = None
    aws_deployment_name: Optional[str] = None
    aws_pod_name: Optional[str] = None
    aws_namespace: Optional[str] = None
    
    @validator('application_name')
    def validate_application_name(cls, v):
        if v is not None:
            if not re.match(r'^[a-zA-Z0-9\s_-]+$', v):
                raise ValueError('Application name can only contain letters, numbers, spaces, hyphens, and underscores')
            return v.strip()
        return v
    
    @validator('github_repo')
    def validate_github_repo(cls, v):
        if v is not None:
            github_patterns = [
                r'^https?://github\.com/[\w-]+/[\w.-]+/?$',
                r'^[\w-]+/[\w.-]+$'
            ]
            if not any(re.match(pattern, v) for pattern in github_patterns):
                raise ValueError('Invalid GitHub repository format')
            return v.strip()
        return v
    
    @validator('gcp_project_id')
    def validate_gcp_project_id(cls, v):
        if v is not None:
            if not re.match(r'^[a-z][a-z0-9-]{4,28}[a-z0-9]$', v):
                raise ValueError('Invalid GCP project ID format')
            return v.strip()
        return v

class ApplicationResponse(BaseModel):
    """Model for application response."""
    id: Optional[str] = None
    # Common fields
    application_name: Optional[str] = None
    application_owner: Optional[str] = None
    status: Optional[ApplicationStatus] = ApplicationStatus.ACTIVE
    github_repo: Optional[str] = None
    argocd_app_name: Optional[str] = None
    grafana_dashboard: Optional[str] = None
    grafana_alert_name: Optional[str] = None
    grafana_dashboard_url: Optional[str] = None
    grafana_alert: Optional[str] = None
    description: Optional[str] = None
    application_criticality: Optional[str] = None
    custom_metadata: Optional[List[Dict[str, str]]] = None
    
    # Cloud provider
    cloud_provider: Optional[CloudProvider] = CloudProvider.GCP
    
    # Legacy GCP fields (optional for backward compatibility)
    gcp_project_id: Optional[str] = None
    gke_cluster_name: Optional[str] = None
    namespace: Optional[str] = "default"
    
    # GCP specific
    gcp_log_resource: Optional[str] = None
    deployment_name: Optional[str] = None
    pod_name: Optional[str] = None
    
    # Azure specific
    azure_subscription_id: Optional[str] = None
    aks_cluster_name: Optional[str] = None
    azure_deployment_name: Optional[str] = None
    azure_pod_name: Optional[str] = None
    azure_namespace: Optional[str] = None
    resource_group: Optional[str] = None
    workspace: Optional[str] = None
    workspace_resource_group: Optional[str] = None
    ingress_name: Optional[str] = None
    ingress_public_ip: Optional[str] = None
    ingress_namespace: Optional[str] = None
    
    # AWS specific
    aws_account_id: Optional[str] = None
    eks_cluster_name: Optional[str] = None
    cloudwatch_log_group_path: Optional[str] = None
    aws_deployment_name: Optional[str] = None
    aws_pod_name: Optional[str] = None
    aws_namespace: Optional[str] = None
    
    # Metadata
    created_by: Optional[str] = None
    created_by_username: Optional[str] = None
    updated_by: Optional[str] = None
    updated_by_username: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
class ApplicationListResponse(BaseModel):
    """Model for paginated application list."""
    total: int
    applications: List[ApplicationResponse]
    page: int
    page_size: int
    total_pages: int

class ApplicationStats(BaseModel):
    """Model for application statistics."""
    total_applications: int
    active_applications: int
    inactive_applications: int
    pending_applications: int
    suspended_applications: int
    applications_by_owner: dict  # {owner: count}
    applications_by_cluster: dict  # {cluster: count}
    recent_applications: int  # Added in last 7 days

class ApplicationSearchQuery(BaseModel):
    """Model for application search."""
    query: Optional[str] = None
    status: Optional[ApplicationStatus] = None
    owner: Optional[str] = None
    cluster: Optional[str] = None
    tags: Optional[List[str]] = None

class ApplicationHealthCheck(BaseModel):
    """Model for application health status."""
    application_id: str
    application_name: str
    is_healthy: bool
    last_deployment: Optional[str] = None
    deployment_status: Optional[str] = None
    issues: List[str] = []
    checked_at: str
