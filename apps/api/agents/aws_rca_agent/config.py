"""
AWS RCA Agent Configuration - Load AWS credentials and defaults from .env
"""

import os
from typing import Optional


class AWSConfig:
    """AWS Configuration loader from environment variables"""
    
    # AWS Credentials
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "ap-southeast-2")
    
    # AWS Account & Cluster
    AWS_ACCOUNT_ID: str = os.getenv("AWS_ACCOUNT_ID", "")
    AWS_CLUSTER_NAME: str = os.getenv("AWS_CLUSTER_NAME", "log-agent-eks")
    AWS_CLUSTER_TYPE: str = os.getenv("AWS_CLUSTER_TYPE", "eks")
    
    # CloudWatch Configuration
    AWS_CLOUDWATCH_LOG_GROUP: str = os.getenv(
        "AWS_CLOUDWATCH_LOG_GROUP",
        "/aws/containerinsights/log-agent-eks/application"
    )
    AWS_CLOUDWATCH_NAMESPACE: str = os.getenv("AWS_CLOUDWATCH_NAMESPACE", "ContainerInsights")
    AWS_LOGS_RETENTION_DAYS: int = int(os.getenv("AWS_LOGS_RETENTION_DAYS", "30"))
    
    # ALB/NLB Configuration
    AWS_ALB_LOG_GROUP: str = os.getenv("AWS_ALB_LOG_GROUP", "/aws/elasticloadbalancing/app")
    AWS_ALB_LOG_STREAM_PREFIX: str = os.getenv("AWS_ALB_LOG_STREAM_PREFIX", "AWSLogs")
    
    # MCP Server Configuration
    AWS_MCP_ENABLED: bool = os.getenv("AWS_MCP_ENABLED", "true").lower() == "true"
    AWS_MCP_SERVER_PATH: str = os.getenv(
        "AWS_MCP_SERVER_PATH",
        "awslabs.cloudwatch-mcp-server@latest"
    )
    
    @classmethod
    def validate(cls) -> tuple[bool, Optional[str]]:
        """
        Validate AWS configuration.
        
        Returns:
            Tuple of (is_valid: bool, error_message: str or None)
        """
        if not cls.AWS_ACCESS_KEY_ID or cls.AWS_ACCESS_KEY_ID == "your_aws_access_key_here":
            return False, "AWS_ACCESS_KEY_ID not configured in .env"
        
        if not cls.AWS_SECRET_ACCESS_KEY or cls.AWS_SECRET_ACCESS_KEY == "your_aws_secret_key_here":
            return False, "AWS_SECRET_ACCESS_KEY not configured in .env"
        
        if not cls.AWS_REGION:
            return False, "AWS_REGION not configured in .env"
        
        return True, None
    
    @classmethod
    def get_defaults(cls) -> dict:
        """Get all AWS configuration as dictionary"""
        return {
            "region": cls.AWS_REGION,
            "account_id": cls.AWS_ACCOUNT_ID,
            "cluster_name": cls.AWS_CLUSTER_NAME,
            "cluster_type": cls.AWS_CLUSTER_TYPE,
            "log_group": cls.AWS_CLOUDWATCH_LOG_GROUP,
            "namespace": cls.AWS_CLOUDWATCH_NAMESPACE,
            "mcp_enabled": cls.AWS_MCP_ENABLED
        }
