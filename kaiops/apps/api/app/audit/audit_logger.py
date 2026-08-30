"""
Audit logging for sensitive operations.

Tracks all changes to applications, users, and integrations.
Non-intrusive: just logging wrapper, doesn't change behavior.
"""

import logging
from typing import Any, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AuditLogger:
    """Log all sensitive operations for compliance and debugging."""
    
    @staticmethod
    def log_application_created(
        app_id: str,
        app_name: str,
        created_by: str,
        cloud_provider: str = None,
        metadata: Dict[str, Any] = None
    ):
        """Log application creation."""
        logger.info(
            "application_created",
            extra={
                "entity_type": "application",
                "entity_id": app_id,
                "action": "created",
                "app_name": app_name,
                "cloud_provider": cloud_provider,
                "created_by": created_by,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata or {}
            }
        )
    
    @staticmethod
    def log_application_updated(
        app_id: str,
        app_name: str,
        updated_by: str,
        changes: Dict[str, tuple]  # {"field": (old_value, new_value)}
    ):
        """Log application update."""
        logger.info(
            "application_updated",
            extra={
                "entity_type": "application",
                "entity_id": app_id,
                "action": "updated",
                "app_name": app_name,
                "updated_by": updated_by,
                "timestamp": datetime.utcnow().isoformat(),
                "changes": changes
            }
        )
    
    @staticmethod
    def log_application_deleted(
        app_id: str,
        app_name: str,
        deleted_by: str
    ):
        """Log application deletion."""
        logger.warning(
            "application_deleted",
            extra={
                "entity_type": "application",
                "entity_id": app_id,
                "action": "deleted",
                "app_name": app_name,
                "deleted_by": deleted_by,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def log_user_created(
        user_id: str,
        username: str,
        created_by: str,
        role: str = None
    ):
        """Log user creation."""
        logger.info(
            "user_created",
            extra={
                "entity_type": "user",
                "entity_id": user_id,
                "action": "created",
                "username": username,
                "role": role,
                "created_by": created_by,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def log_user_updated(
        user_id: str,
        username: str,
        updated_by: str,
        changes: Dict[str, tuple]
    ):
        """Log user update."""
        logger.info(
            "user_updated",
            extra={
                "entity_type": "user",
                "entity_id": user_id,
                "action": "updated",
                "username": username,
                "updated_by": updated_by,
                "timestamp": datetime.utcnow().isoformat(),
                "changes": changes
            }
        )
    
    @staticmethod
    def log_user_deleted(
        user_id: str,
        username: str,
        deleted_by: str
    ):
        """Log user deletion."""
        logger.warning(
            "user_deleted",
            extra={
                "entity_type": "user",
                "entity_id": user_id,
                "action": "deleted",
                "username": username,
                "deleted_by": deleted_by,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def log_permission_denied(
        user_id: str,
        username: str,
        action: str,
        resource: str,
        reason: str
    ):
        """Log permission denied attempts."""
        logger.warning(
            "permission_denied",
            extra={
                "user_id": user_id,
                "username": username,
                "action": action,
                "resource": resource,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def log_login_attempt(
        username: str,
        success: bool,
        ip_address: str = None,
        reason: str = None
    ):
        """Log login attempt."""
        level = "info" if success else "warning"
        log_func = logger.info if success else logger.warning
        
        log_func(
            "login_attempt",
            extra={
                "username": username,
                "success": success,
                "ip_address": ip_address,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def log_integration_connected(
        app_id: str,
        app_name: str,
        integration_type: str,
        connected_by: str
    ):
        """Log integration connection."""
        logger.info(
            "integration_connected",
            extra={
                "entity_type": "integration",
                "action": "connected",
                "app_id": app_id,
                "app_name": app_name,
                "integration_type": integration_type,
                "connected_by": connected_by,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def log_integration_disconnected(
        app_id: str,
        app_name: str,
        integration_type: str,
        disconnected_by: str
    ):
        """Log integration disconnection."""
        logger.warning(
            "integration_disconnected",
            extra={
                "entity_type": "integration",
                "action": "disconnected",
                "app_id": app_id,
                "app_name": app_name,
                "integration_type": integration_type,
                "disconnected_by": disconnected_by,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def log_data_export(
        user_id: str,
        username: str,
        entity_type: str,
        entity_id: str,
        format: str
    ):
        """Log data export for compliance."""
        logger.info(
            "data_export",
            extra={
                "user_id": user_id,
                "username": username,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "format": format,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def log_data_deletion(
        user_id: str,
        entity_type: str,
        entity_id: str,
        reason: str = None
    ):
        """Log data deletion for GDPR/compliance."""
        logger.warning(
            "data_deletion",
            extra={
                "user_id": user_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
