"""
Validation utilities for metadata fields and configurations.

Provides validation helpers for URLs, IDs, integration configurations, and required fields.
"""
import logging
import re
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised when metadata validation fails."""
    pass


class MetadataValidator:
    """Validates metadata fields and configurations."""
    
    # Regex patterns
    GITHUB_REPO_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+$')
    BRANCH_PATTERN = re.compile(r'^[a-zA-Z0-9._\-/]+$')
    ARGOCD_APP_NAME_PATTERN = re.compile(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$')
    KUBERNETES_NAMESPACE_PATTERN = re.compile(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$')
    DASHBOARD_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
    COST_CENTER_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
    
    @staticmethod
    def validate_url(url: str, field_name: str = "URL") -> None:
        """
        Validate URL format.
        
        Args:
            url: URL to validate
            field_name: Field name for error messages
            
        Raises:
            ValidationError: If URL is invalid
        """
        if not url:
            raise ValidationError(f"{field_name} cannot be empty")
        
        try:
            result = urlparse(url)
            if not all([result.scheme, result.netloc]):
                raise ValidationError(f"Invalid {field_name}: {url}")
            
            if result.scheme not in ['http', 'https']:
                raise ValidationError(f"{field_name} must use http or https: {url}")
                
        except Exception as e:
            raise ValidationError(f"Invalid {field_name}: {str(e)}")
    
    @staticmethod
    def validate_github_repo(repo_owner: str, repo_name: str) -> None:
        """
        Validate GitHub repository details.
        
        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            
        Raises:
            ValidationError: If validation fails
        """
        if not repo_owner or not repo_name:
            raise ValidationError("GitHub repo_owner and repo_name are required")
        
        if not MetadataValidator.GITHUB_REPO_PATTERN.match(f"{repo_owner}/{repo_name}"):
            raise ValidationError(
                f"Invalid GitHub repo format. Owner and name must contain only alphanumeric, "
                f"hyphens, and underscores: {repo_owner}/{repo_name}"
            )
    
    @staticmethod
    def validate_github_branch(branch: str) -> None:
        """
        Validate Git branch name.
        
        Args:
            branch: Branch name
            
        Raises:
            ValidationError: If validation fails
        """
        if not branch:
            raise ValidationError("Branch name cannot be empty")
        
        if not MetadataValidator.BRANCH_PATTERN.match(branch):
            raise ValidationError(
                f"Invalid branch name. Must contain only alphanumeric, dots, "
                f"hyphens, and slashes: {branch}"
            )
    
    @staticmethod
    def validate_argocd_app_name(app_name: str) -> None:
        """
        Validate ArgoCD application name (Kubernetes naming rules).
        
        Args:
            app_name: Application name
            
        Raises:
            ValidationError: If validation fails
        """
        if not app_name:
            raise ValidationError("ArgoCD app_name cannot be empty")
        
        if len(app_name) > 63:
            raise ValidationError("ArgoCD app_name must be 63 characters or less")
        
        if not MetadataValidator.ARGOCD_APP_NAME_PATTERN.match(app_name):
            raise ValidationError(
                f"Invalid ArgoCD app_name. Must start with lowercase letter or digit, "
                f"contain only lowercase letters, digits, and hyphens, and end with "
                f"lowercase letter or digit: {app_name}"
            )
    
    @staticmethod
    def validate_kubernetes_namespace(namespace: str) -> None:
        """
        Validate Kubernetes namespace (Kubernetes naming rules).
        
        Args:
            namespace: Namespace name
            
        Raises:
            ValidationError: If validation fails
        """
        if not namespace:
            raise ValidationError("Kubernetes namespace cannot be empty")
        
        if len(namespace) > 63:
            raise ValidationError("Kubernetes namespace must be 63 characters or less")
        
        if not MetadataValidator.KUBERNETES_NAMESPACE_PATTERN.match(namespace):
            raise ValidationError(
                f"Invalid Kubernetes namespace. Must start with lowercase letter or digit, "
                f"contain only lowercase letters, digits, and hyphens, and end with "
                f"lowercase letter or digit: {namespace}"
            )
    
    @staticmethod
    def validate_grafana_dashboard_id(dashboard_id: str) -> None:
        """
        Validate Grafana dashboard ID.
        
        Args:
            dashboard_id: Dashboard ID
            
        Raises:
            ValidationError: If validation fails
        """
        if not dashboard_id:
            raise ValidationError("Grafana dashboard_id cannot be empty")
        
        if len(dashboard_id) > 255:
            raise ValidationError("Grafana dashboard_id must be 255 characters or less")
        
        if not MetadataValidator.DASHBOARD_ID_PATTERN.match(dashboard_id):
            raise ValidationError(
                f"Invalid Grafana dashboard_id. Must contain only alphanumeric, "
                f"hyphens, and underscores: {dashboard_id}"
            )
    
    @staticmethod
    def validate_cost_center(cost_center: str) -> None:
        """
        Validate cost center name.
        
        Args:
            cost_center: Cost center name
            
        Raises:
            ValidationError: If validation fails
        """
        if not cost_center:
            raise ValidationError("Cost center cannot be empty")
        
        if len(cost_center) > 100:
            raise ValidationError("Cost center must be 100 characters or less")
        
        if not MetadataValidator.COST_CENTER_PATTERN.match(cost_center):
            raise ValidationError(
                f"Invalid cost center. Must contain only alphanumeric, "
                f"hyphens, and underscores: {cost_center}"
            )
    
    @staticmethod
    def validate_budget_threshold(threshold: float) -> None:
        """
        Validate budget alert threshold.
        
        Args:
            threshold: Threshold percentage
            
        Raises:
            ValidationError: If validation fails
        """
        if threshold is None:
            return  # Optional field
        
        if not isinstance(threshold, (int, float)):
            raise ValidationError("Budget threshold must be a number")
        
        if threshold <= 0 or threshold > 100:
            raise ValidationError("Budget threshold must be between 0 and 100 percent")
    
    @staticmethod
    def validate_app_name(app_name: str) -> None:
        """
        Validate application name (same as ArgoCD naming rules).
        
        Args:
            app_name: Application name
            
        Raises:
            ValidationError: If validation fails
        """
        if not app_name:
            raise ValidationError("Application name cannot be empty")
        
        if len(app_name) > 63:
            raise ValidationError("Application name must be 63 characters or less")
        
        if not MetadataValidator.ARGOCD_APP_NAME_PATTERN.match(app_name):
            raise ValidationError(
                f"Invalid application name. Must start with lowercase letter or digit, "
                f"contain only lowercase letters, digits, and hyphens, and end with "
                f"lowercase letter or digit: {app_name}"
            )
    
    @staticmethod
    def validate_environment(environment: str) -> None:
        """
        Validate environment name.
        
        Args:
            environment: Environment name
            
        Raises:
            ValidationError: If validation fails
        """
        if not environment:
            return  # Optional field
        
        valid_environments = ['production', 'staging', 'development', 'qa', 'test']
        
        if environment.lower() not in valid_environments:
            raise ValidationError(
                f"Invalid environment '{environment}'. Must be one of: {', '.join(valid_environments)}"
            )
    
    @staticmethod
    def validate_team(team: str) -> None:
        """
        Validate team name.
        
        Args:
            team: Team name
            
        Raises:
            ValidationError: If validation fails
        """
        if not team:
            return  # Optional field
        
        if len(team) > 100:
            raise ValidationError("Team name must be 100 characters or less")
        
        if not re.match(r'^[a-zA-Z0-9_\-\s]+$', team):
            raise ValidationError(
                f"Invalid team name. Must contain only alphanumeric, hyphens, "
                f"underscores, and spaces: {team}"
            )
    
    @staticmethod
    def validate_github_metadata(enabled: bool, github_dict: Dict[str, Any]) -> None:
        """
        Validate complete GitHub metadata.
        
        Args:
            enabled: Whether integration is enabled
            github_dict: GitHub metadata dictionary
            
        Raises:
            ValidationError: If validation fails
        """
        if not enabled:
            return  # Skip validation if disabled
        
        repo_owner = github_dict.get("repo_owner")
        repo_name = github_dict.get("repo_name")
        branch = github_dict.get("branch", "main")
        repo_url = github_dict.get("repo_url")
        
        if not repo_owner or not repo_name:
            raise ValidationError("GitHub: repo_owner and repo_name are required when enabled")
        
        MetadataValidator.validate_github_repo(repo_owner, repo_name)
        MetadataValidator.validate_github_branch(branch)
        
        if repo_url:
            MetadataValidator.validate_url(repo_url, "GitHub repo_url")
    
    @staticmethod
    def validate_argocd_metadata(enabled: bool, argocd_dict: Dict[str, Any]) -> None:
        """
        Validate complete ArgoCD metadata.
        
        Args:
            enabled: Whether integration is enabled
            argocd_dict: ArgoCD metadata dictionary
            
        Raises:
            ValidationError: If validation fails
        """
        if not enabled:
            return  # Skip validation if disabled
        
        app_name = argocd_dict.get("app_name")
        namespace = argocd_dict.get("namespace")
        
        if not app_name:
            raise ValidationError("ArgoCD: app_name is required when enabled")
        
        MetadataValidator.validate_argocd_app_name(app_name)
        
        if namespace:
            MetadataValidator.validate_kubernetes_namespace(namespace)
    
    @staticmethod
    def validate_grafana_metadata(enabled: bool, grafana_dict: Dict[str, Any]) -> None:
        """
        Validate complete Grafana metadata.
        
        Args:
            enabled: Whether integration is enabled
            grafana_dict: Grafana metadata dictionary
            
        Raises:
            ValidationError: If validation fails
        """
        if not enabled:
            return  # Skip validation if disabled
        
        dashboard_id = grafana_dict.get("dashboard_id")
        dashboard_url = grafana_dict.get("dashboard_url")
        
        if not dashboard_id and not dashboard_url:
            raise ValidationError("Grafana: dashboard_id or dashboard_url is required when enabled")
        
        if dashboard_id:
            MetadataValidator.validate_grafana_dashboard_id(dashboard_id)
        
        if dashboard_url:
            MetadataValidator.validate_url(dashboard_url, "Grafana dashboard_url")
    
    @staticmethod
    def validate_cost_metadata(enabled: bool, cost_dict: Dict[str, Any]) -> None:
        """
        Validate complete Cost metadata.
        
        Args:
            enabled: Whether integration is enabled
            cost_dict: Cost metadata dictionary
            
        Raises:
            ValidationError: If validation fails
        """
        if not enabled:
            return  # Skip validation if disabled
        
        cost_center = cost_dict.get("cost_center")
        budget_threshold = cost_dict.get("budget_alert_threshold")
        
        if cost_center:
            MetadataValidator.validate_cost_center(cost_center)
        
        if budget_threshold:
            MetadataValidator.validate_budget_threshold(budget_threshold)
