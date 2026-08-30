"""
GitHub Tools

Tool functions that call the local GitHub MCP server.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.mcp_client import call_mcp_tool, parse_mcp_response


async def search_repositories(query: str, sort: str = "stars", per_page: int = 10) -> str:
    """Search GitHub repositories."""
    try:
        result = await call_mcp_tool("github", "search_repositories", query=query, sort=sort, per_page=per_page)
        data = parse_mcp_response(result)
        
        if "error" in data:
            return f"[FAIL] {data['error']}"
        
        repos = data.get("repositories", [])
        output = f"[SEARCH] Found {data.get('total_count', 0)} repositories\n"
        for repo in repos[:5]:
            output += f"- {repo.get('full_name', '')}: ⭐ {repo.get('stars', 0)}\n"
        
        return output
    except Exception as e:
        return f"[FAIL] Error: {str(e)}"


async def get_repository_info(owner: str, repo: str) -> str:
    """Get repository details."""
    try:
        result = await call_mcp_tool("github", "get_repository_info", owner=owner, repo=repo)
        data = parse_mcp_response(result)
        
        if "error" in data:
            return f"[FAIL] {data['error']}"
        
        output = f"📦 **{data.get('full_name', '')}**\n"
        output += f"{data.get('description', 'No description')}\n"
        output += f"⭐ {data.get('stars', 0)} | 🍴 {data.get('forks', 0)} | 📝 {data.get('language', 'N/A')}\n"
        
        return output
    except Exception as e:
        return f"[FAIL] Error: {str(e)}"


async def search_code(query: str, repo: str = "", per_page: int = 10) -> str:
    """Search code in GitHub."""
    try:
        result = await call_mcp_tool("github", "search_code", query=query, repo=repo, per_page=per_page)
        data = parse_mcp_response(result)
        
        if "error" in data:
            return f"[FAIL] {data['error']}"
        
        results = data.get("code_results", [])
        output = f"🔎 Found {data.get('total_count', 0)} code matches\n"
        for item in results[:5]:
            output += f"- {item.get('repository', '')}/{item.get('path', '')}\n"
        
        return output
    except Exception as e:
        return f"[FAIL] Error: {str(e)}"


async def list_issues(owner: str, repo: str, state: str = "open", per_page: int = 10) -> str:
    """List repository issues."""
    try:
        result = await call_mcp_tool("github", "list_issues", owner=owner, repo=repo, state=state, per_page=per_page)
        data = parse_mcp_response(result)
        
        if "error" in data:
            return f"[FAIL] {data['error']}"
        
        issues = data.get("issues", [])
        output = f"🐛 {len(issues)} {state} issues\n"
        for issue in issues[:5]:
            output += f"- #{issue.get('number', '')}: {issue.get('title', '')}\n"
        
        return output
    except Exception as e:
        return f"[FAIL] Error: {str(e)}"


async def get_user_repositories(username: str, per_page: int = 10) -> str:
    """Get user repositories."""
    try:
        result = await call_mcp_tool("github", "get_user_repositories", username=username, per_page=per_page)
        data = parse_mcp_response(result)
        
        if "error" in data:
            return f"[FAIL] {data['error']}"
        
        repos = data.get("repositories", [])
        output = f"👤 {username}'s repositories ({len(repos)})\n"
        for repo in repos[:5]:
            output += f"- {repo.get('name', '')}\n"
        
        return output
    except Exception as e:
        return f"[FAIL] Error: {str(e)}"


async def get_latest_commit(owner: str, repo: str) -> str:
    """Get latest commit from repository."""
    try:
        # GitHub MCP server doesn't have this tool, so we use get_repository_info instead
        result = await call_mcp_tool("github", "get_repository_info", owner=owner, repo=repo)
        data = parse_mcp_response(result)
        
        if "error" in data:
            return f"[FAIL] {data['error']}"
        
        return f"📝 Latest update: {data.get('updated_at', 'Unknown')}"
    except Exception as e:
        return f"[FAIL] Error: {str(e)}"
