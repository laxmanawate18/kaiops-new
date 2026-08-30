"""
ArgoCD Agent

Domain expert for deployment management and continuous delivery operations.
Coordinates with ArgoCD MCP server for deployment status and synchronization.
"""

from agents.argocd_agent.tools import (
    get_application_status,
    sync_application,
    get_deployment_history,
    search_applications,
    list_repositories,
    list_projects
)

from agents.argocd_agent.prompt import argocd_expertise

# ArgoCD agent exports tools and prompt for root agent composition
argocd_tools = [
    get_application_status,
    sync_application,
    get_deployment_history,
    search_applications,
    list_repositories,
    list_projects
]

argocd_prompt = argocd_expertise

__all__ = [
    "argocd_tools",
    "argocd_prompt",
    "get_application_status",
    "sync_application",
    "get_deployment_history",
    "search_applications",
    "list_repositories",
    "list_projects"
]
