"""
GitHub Agent Tools

Tool functions for source code management via GitHub MCP Server.
"""

import json
import logging
from typing import Dict, Any, Optional
from agents.mcp_client import call_mcp_tool

logger = logging.getLogger(__name__)

async def _call_and_format_github_mcp(tool_name: str, **kwargs) -> str:
    """Helper to call MCP and return the raw text content."""
    try:
        result = await call_mcp_tool('github', tool_name, **kwargs)
        if "error" in result:
            return f"[FAIL] **GitHub MCP Error**: {result['error']}"
            
        content = result.get("content", [])
        if content and len(content) > 0:
            return content[0].get("text", "No content returned.")
        return "No content in MCP response."
    except Exception as e:
        logger.error(f"GitHub MCP call failed: {e}")
        return f"[FAIL] **Error**: {str(e)}"


async def get_latest_commit(owner: str, repo: str) -> str:
    """Get the latest commit from a GitHub repository with comprehensive details."""
    if not owner or not repo or owner.lower() == "n/a" or repo.lower() == "n/a":
        return "[WARN] **No GitHub Repository**\nGitHub repository not configured for this application."
    return await _call_and_format_github_mcp("get_latest_commit", owner=owner, repo=repo)


async def get_repository_info(owner: str, repo: str) -> str:
    """Get detailed information about a GitHub repository."""
    return await _call_and_format_github_mcp("get_repository_info", owner=owner, repo=repo)


async def search_repositories(query: str, limit: int = 10) -> str:
    """Search GitHub repositories by query string."""
    return await _call_and_format_github_mcp("search_repositories", query=query, limit=limit)


async def search_code(query: str, owner: str = "", repo: str = "", limit: int = 5) -> str:
    """Search code in a repository or across GitHub."""
    return await _call_and_format_github_mcp("search_code", query=query, owner=owner, repo=repo, limit=limit)


async def list_issues(owner: str, repo: str, state: str = "open", limit: int = 5) -> str:
    """List issues in a repository."""
    return await _call_and_format_github_mcp("list_issues", owner=owner, repo=repo, state=state, limit=limit)


async def get_user_repositories(limit: int = 10) -> str:
    """List repositories accessible by authenticated GitHub user."""
    return await _call_and_format_github_mcp("get_user_repositories", limit=limit)


__all__ = [
    "get_latest_commit",
    "get_repository_info",
    "search_repositories",
    "search_code",
    "list_issues",
    "get_user_repositories"
]
