"""
ArgoCD Agent Tools

Tool functions for deployment management via ArgoCD MCP Server.
"""

import json
import logging
from agents.mcp_client import call_mcp_tool

logger = logging.getLogger(__name__)

async def _call_and_format_argocd_mcp(tool_name: str, **kwargs) -> str:
    """Helper to call MCP and return the raw text content."""
    try:
        result = await call_mcp_tool('argocd', tool_name, **kwargs)
        if "error" in result:
            return f"[FAIL] **ArgoCD MCP Error**: {result['error']}"
            
        content = result.get("content", [])
        if content and len(content) > 0:
            first = content[0]
            return first.get("text", "No content returned.") if isinstance(first, dict) else str(first)
        return "No content in MCP response."
    except Exception as e:
        logger.error(f"ArgoCD MCP call failed: {e}")
        return f"[FAIL] **Error**: {str(e)}"


async def get_application_status(app_name: str) -> str:
    """Get comprehensive sync and health status of an ArgoCD application."""
    if not app_name or app_name.lower() == "n/a":
        return "[WARN] **No ArgoCD Configuration**\nThis application is not deployed via ArgoCD."
    return await _call_and_format_argocd_mcp("get_application_status", app_name=app_name)


async def sync_application(app_name: str, force: bool = False, prune: bool = False) -> str:
    """Trigger manual synchronization of an ArgoCD application."""
    return await _call_and_format_argocd_mcp("sync_application", app_name=app_name, force=force, prune=prune)


async def get_deployment_history(app_name: str, limit: int = 10) -> str:
    """Get deployment history and recent sync operations."""
    return await _call_and_format_argocd_mcp("get_deployment_history", app_name=app_name, limit=limit)


async def search_applications(query: str, limit: int = 20) -> str:
    """Search ArgoCD applications by query string."""
    return await _call_and_format_argocd_mcp("search_applications", query=query, limit=limit)


async def list_repositories() -> str:
    """List all Git repositories configured in ArgoCD."""
    return await _call_and_format_argocd_mcp("list_repositories")


async def list_projects() -> str:
    """List all ArgoCD projects."""
    return await _call_and_format_argocd_mcp("list_projects")


async def rollback_application(app_name: str, target_commit: str = "", prune: bool = False) -> str:
    """
    Roll back an ArgoCD application to a specific commit or previous deployment.
    This is a destructive action that requires user confirmation (HITL).
    Use get_deployment_history first to discover available revisions.
    """
    if not app_name or app_name.lower() == "n/a":
        return "[WARN] **No ArgoCD Configuration**\nThis application is not deployed via ArgoCD."

    kwargs: dict = {"app_name": app_name, "prune": prune}
    rev = (target_commit or "").strip()
    if rev and rev.lower() not in ("n/a", "none"):
        kwargs["target_revision"] = rev

    try:
        result = await call_mcp_tool("argocd", "rollback_application", **kwargs)
        if "error" in result:
            return f"[FAIL] **ArgoCD MCP Error**: {result['error']}"

        content = result.get("content", [])
        if content and isinstance(content[0], dict):
            raw = content[0].get("text", "{}")
        elif content:
            raw = str(content[0])
        else:
            raw = "{}"
        data = json.loads(raw) if raw else {}

        if "error" in data:
            return f"[FAIL] **Rollback failed**: {data['error']}"

        lines = [
            "[OK] **Rollback initiated**",
            f"- Application: {data.get('app_name', app_name)}",
        ]
        if data.get("target_revision"):
            lines.append(f"- Target revision: {data['target_revision']}")
        lines.append(f"- Deployment ID: {data.get('rolled_back_to_deployment_id', '?')}")
        lines.append(
            f"- Sync: {data.get('sync_status') or 'Unknown'} | "
            f"Health: {data.get('health_status') or 'Unknown'}"
        )
        if data.get("note"):
            lines.append(f"- Note: {data['note']}")
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"ArgoCD rollback failed: {e}")
        return f"[FAIL] **Error**: {str(e)}"


__all__ = [
    "get_application_status",
    "sync_application",
    "get_deployment_history",
    "search_applications",
    "list_repositories",
    "list_projects",
    "rollback_application"
]
