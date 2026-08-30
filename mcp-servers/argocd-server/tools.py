"""
ArgoCD Tools

Tool functions that call the local ArgoCD MCP server.
These are exposed to the root SRE agent.
"""

import sys
import os
from typing import Dict, Any

# Add parent to path for mcp_client
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.mcp_client import call_mcp_tool, parse_mcp_response


async def get_application_status(app_name: str) -> str:
    """Get sync and health status of an ArgoCD application."""
    try:
        if not app_name or app_name.lower() == "n/a":
            return "[WARN] No ArgoCD application configured."
        
        result = await call_mcp_tool("argocd", "get_application_status", app_name=app_name)
        data = parse_mcp_response(result)

        if "error" in data:
            return f"[FAIL] {data['error']}"

        sync_status = data.get("sync_status", "Unknown")
        health_status = data.get("health_status", "Unknown")
        
        output = f"[RUN] **ArgoCD: {app_name}**\n"
        output += f"Sync: {'[OK]' if sync_status == 'Synced' else '[FAIL]'} {sync_status} | "
        output += f"Health: {'🟢' if health_status == 'Healthy' else '🔴'} {health_status}"
        
        return output
    except Exception as e:
        return f"[FAIL] Error: {str(e)}"


async def sync_application(app_name: str, force: bool = False, prune: bool = False) -> str:
    """Trigger manual sync of ArgoCD application."""
    try:
        result = await call_mcp_tool("argocd", "sync_application", app_name=app_name, force=force, prune=prune)
        data = parse_mcp_response(result)
        
        if "error" in data:
            return f"[FAIL] {data['error']}"
        
        return f"[OK] Sync initiated for {app_name}"
    except Exception as e:
        return f"[FAIL] Error: {str(e)}"


async def get_deployment_history(app_name: str, limit: int = 10) -> str:
    """Get deployment history."""
    try:
        result = await call_mcp_tool("argocd", "get_deployment_history", app_name=app_name, limit=limit)
        data = parse_mcp_response(result)
        
        if "error" in data:
            return f"[FAIL] {data['error']}"
        
        syncs = data.get("recent_syncs", [])
        if not syncs:
            return f"No deployment history for {app_name}"
        
        output = f"[STATS] **History: {app_name}**\n"
        for sync in syncs[:5]:
            output += f"- {sync.get('revision', '')[:8]}: {sync.get('status', 'Unknown')}\n"
        
        return output
    except Exception as e:
        return f"[FAIL] Error: {str(e)}"


async def search_applications(query: str, limit: int = 20) -> str:
    """Search ArgoCD applications."""
    try:
        result = await call_mcp_tool("argocd", "search_applications", query=query, limit=limit)
        data = parse_mcp_response(result)
        
        if "error" in data:
            return f"[FAIL] {data['error']}"
        
        apps = data.get("applications", [])
        if not apps:
            return f"No applications found matching '{query}'"
        
        output = f"[SEARCH] Found {len(apps)} applications:\n"
        for app in apps:
            output += f"- {app.get('name', '')}: {app.get('sync_status', '')} / {app.get('health_status', '')}\n"
        
        return output
    except Exception as e:
        return f"[FAIL] Error: {str(e)}"


async def list_repositories() -> str:
    """List Git repositories in ArgoCD."""
    try:
        result = await call_mcp_tool("argocd", "list_repositories")
        data = parse_mcp_response(result)
        
        if "error" in data:
            return f"[FAIL] {data['error']}"
        
        repos = data.get("repositories", [])
        output = f"📁 {len(repos)} repositories configured\n"
        for repo in repos:
            output += f"- {repo.get('url', '')}\n"
        
        return output
    except Exception as e:
        return f"[FAIL] Error: {str(e)}"


async def list_projects() -> str:
    """List ArgoCD projects."""
    try:
        result = await call_mcp_tool("argocd", "list_projects")
        data = parse_mcp_response(result)
        
        if "error" in data:
            return f"[FAIL] {data['error']}"
        
        projects = data.get("projects", [])
        output = f"📂 {len(projects)} projects\n"
        for proj in projects:
            output += f"- {proj.get('name', '')}\n"
        
        return output
    except Exception as e:
        return f"[FAIL] Error: {str(e)}"
