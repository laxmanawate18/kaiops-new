"""
GitHub Agent

Domain expert for source code management and repository operations.
Coordinates with GitHub MCP server for code search and commit history.
"""

from agents.github_agent.tools import (
    get_latest_commit,
    get_repository_info,
    search_repositories,
    search_code,
    list_issues,
    get_user_repositories
)

from agents.github_agent.prompt import github_expertise

# GitHub agent exports tools and prompt for root agent composition
github_tools = [
    get_latest_commit,
    get_repository_info,
    search_repositories,
    search_code,
    list_issues,
    get_user_repositories
]

github_prompt = github_expertise

__all__ = [
    "github_tools",
    "github_prompt",
    "get_latest_commit",
    "get_repository_info",
    "search_repositories",
    "search_code",
    "list_issues",
    "get_user_repositories"
]
