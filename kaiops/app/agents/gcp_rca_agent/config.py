"""
GCP RCA Agent Configuration - Load GCP credentials and defaults from .env

Provides configuration management for:
- GCP Project ID and credentials
- GKE cluster details
- Cloud Logging settings
- Cloud Monitoring settings
"""

import os
from typing import Optional, Dict, Any
from google.oauth2 import service_account


class GCPConfig:
    """GCP Configuration loader from environment variables."""
    
    # GCP Project Configuration
    GCP_PROJECT_ID: str = os.getenv("GOOGLE_PROJECT_ID", "")
    GCP_CREDENTIALS_PATH: str = os.getenv("GOOGLE_CREDENTIALS_PATH", "")
    
    # GKE Cluster Configuration
    GCP_CLUSTER_NAME: str = os.getenv("GCP_CLUSTER_NAME", "kai-ops")
    GCP_CLUSTER_ZONE: str = os.getenv("GCP_CLUSTER_ZONE", "us-central1-a")
    
    # Cloud Logging Configuration
    GCP_LOG_RESOURCE_TYPE: str = os.getenv("GCP_LOG_RESOURCE_TYPE", "k8s_container")
    GCP_DEFAULT_NAMESPACE: str = os.getenv("GCP_DEFAULT_NAMESPACE", "default")
    GCP_LOG_RETENTION_DAYS: int = int(os.getenv("GCP_LOG_RETENTION_DAYS", "30"))
    
    # Cloud Monitoring Configuration
    GCP_MONITORING_ENABLED: bool = os.getenv("GCP_MONITORING_ENABLED", "true").lower() == "true"
    GCP_METRICS_NAMESPACE: str = os.getenv("GCP_METRICS_NAMESPACE", "kubernetes.io")
    
    # Load Balancer Configuration (optional)
    GCP_LB_LOGS_ENABLED: bool = os.getenv("GCP_LB_LOGS_ENABLED", "false").lower() == "true"
    
    # MCP Configuration (not used - direct API calls)
    GCP_MCP_ENABLED: bool = os.getenv("GCP_MCP_ENABLED", "false").lower() == "true"
    
    # Cached credentials
    _credentials = None
    
    @classmethod
    def validate(cls) -> tuple[bool, Optional[str]]:
        """
        Validate GCP configuration.
        
        Returns:
            Tuple of (is_valid: bool, error_message: str or None)
        """
        if not cls.GCP_PROJECT_ID:
            return False, "GOOGLE_PROJECT_ID not configured in .env"
        
        if not cls.GCP_CREDENTIALS_PATH:
            return False, "GOOGLE_CREDENTIALS_PATH not configured in .env"
        
        if not os.path.exists(cls.GCP_CREDENTIALS_PATH):
            return False, f"GCP credentials file not found: {cls.GCP_CREDENTIALS_PATH}"
        
        if not cls.GCP_CLUSTER_NAME:
            return False, "GCP_CLUSTER_NAME not configured in .env"
        
        return True, None
    
    @classmethod
    def get_credentials(cls):
        """
        Get GCP service account credentials.
        
        Returns:
            google.oauth2.service_account.Credentials object
        """
        if cls._credentials is None:
            try:
                cls._credentials = service_account.Credentials.from_service_account_file(
                    cls.GCP_CREDENTIALS_PATH,
                    scopes=[
                        "https://www.googleapis.com/auth/cloud-platform",
                        "https://www.googleapis.com/auth/logging.read",
                        "https://www.googleapis.com/auth/monitoring.read"
                    ]
                )
            except Exception as e:
                raise ValueError(f"Failed to load GCP credentials: {e}")
        
        return cls._credentials
    
    @classmethod
    def get_project_id(cls) -> str:
        """Get the GCP project ID."""
        return cls.GCP_PROJECT_ID
    
    @classmethod
    def get_cluster_name(cls) -> str:
        """Get the GKE cluster name."""
        return cls.GCP_CLUSTER_NAME
    
    @classmethod
    def get_cluster_zone(cls) -> str:
        """Get the GKE cluster zone."""
        return cls.GCP_CLUSTER_ZONE
    
    @classmethod
    def get_defaults(cls) -> Dict[str, Any]:
        """Get all GCP configuration as dictionary."""
        return {
            "gcp_project_id": cls.GCP_PROJECT_ID,
            "gcp_cluster_name": cls.GCP_CLUSTER_NAME,
            "gcp_cluster_zone": cls.GCP_CLUSTER_ZONE,
            "gcp_log_resource_type": cls.GCP_LOG_RESOURCE_TYPE,
            "gcp_monitoring_enabled": cls.GCP_MONITORING_ENABLED,
            "gcp_lb_logs_enabled": cls.GCP_LB_LOGS_ENABLED,
            "gcp_mcp_enabled": cls.GCP_MCP_ENABLED
        }
    
    @classmethod
    def is_configured(cls) -> bool:
        """Check if GCP is properly configured."""
        is_valid, _ = cls.validate()
        return is_valid


# Validate on module load (optional - can be disabled for testing)
if __name__ == "__main__":
    is_valid, error = GCPConfig.validate()
    if is_valid:
        print(" GCP Configuration is valid")
        print(f"   Project ID: {GCPConfig.GCP_PROJECT_ID}")
        print(f"   Cluster: {GCPConfig.GCP_CLUSTER_NAME}")
        print(f"   Zone: {GCPConfig.GCP_CLUSTER_ZONE}")
    else:
        print(f" GCP Configuration error: {error}")
