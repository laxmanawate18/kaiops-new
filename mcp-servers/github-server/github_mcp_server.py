#!/usr/bin/env python3
"""
GitHub MCP Server - Python Implementation

MCP server for GitHub repository operations using FastMCP.
Provides tools for repository management, code search, and issue tracking.
"""

import json
import os
import sys
from typing import Any, Dict, Optional

import requests
from mcp.server import FastMCP

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()


class GitHubMCPServer:
    def __init__(self):
        self.github_token = os.getenv("GITHUB_TOKEN", "")
        self.github_api_url = "https://api.github.com"

        print(f"🔧 GitHub MCP Server initialized:", file=sys.stderr)
        print(f"   API URL: {self.github_api_url}", file=sys.stderr)
        print(f"   Token present: {bool(self.github_token)}", file=sys.stderr)

    def make_github_request(self, endpoint: str, method: str = "GET", params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a request to the GitHub API."""
        url = f"{self.github_api_url}{endpoint}"

        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHub-MCP-Server/1.0"
        }

        # Add authorization header only if token is provided
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=10)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=params, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            raise Exception(f"GitHub API request failed: {str(e)}")


# Create FastMCP server
server = GitHubMCPServer()
mcp = FastMCP("github-mcp-server")


@mcp.tool()
def search_repositories(query: str, sort: str = "stars", order: str = "desc", per_page: int = 10) -> str:
    """Search for GitHub repositories by query."""
    try:
        params = {
            "q": query,
            "sort": sort,
            "order": order,
            "per_page": min(per_page, 100)  # GitHub API limit
        }

        data = server.make_github_request("/search/repositories", "GET", params)

        repositories = data.get("items", [])
        total_count = data.get("total_count", 0)

        result = {
            "total_count": total_count,
            "repositories": [
                {
                    "name": repo.get("name", ""),
                    "full_name": repo.get("full_name", ""),
                    "description": repo.get("description", ""),
                    "url": repo.get("html_url", ""),
                    "stars": repo.get("stargazers_count", 0),
                    "forks": repo.get("forks_count", 0),
                    "language": repo.get("language", ""),
                    "owner": repo.get("owner", {}).get("login", "")
                }
                for repo in repositories[:per_page]
            ]
        }

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Repository search failed: {str(e)}"})


@mcp.tool()
def get_repository_info(owner: str, repo: str) -> str:
    """Get detailed information about a specific repository."""
    try:
        data = server.make_github_request(f"/repos/{owner}/{repo}")

        result = {
            "name": data.get("name", ""),
            "full_name": data.get("full_name", ""),
            "description": data.get("description", ""),
            "url": data.get("html_url", ""),
            "stars": data.get("stargazers_count", 0),
            "forks": data.get("forks_count", 0),
            "language": data.get("language", ""),
            "topics": data.get("topics", []),
            "created_at": data.get("created_at", ""),
            "updated_at": data.get("updated_at", ""),
            "owner": data.get("owner", {}).get("login", ""),
            "private": data.get("private", False),
            "archived": data.get("archived", False)
        }

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Repository info failed: {str(e)}"})


@mcp.tool()
def search_code(query: str, repo: str = "", language: str = "", per_page: int = 10) -> str:
    """Search for code in GitHub repositories."""
    try:
        search_query = f"{query}"
        if repo:
            search_query += f" repo:{repo}"
        if language:
            search_query += f" language:{language}"

        params = {
            "q": search_query,
            "per_page": min(per_page, 100)
        }

        data = server.make_github_request("/search/code", "GET", params)

        code_results = data.get("items", [])
        total_count = data.get("total_count", 0)

        result = {
            "total_count": total_count,
            "code_results": [
                {
                    "name": item.get("name", ""),
                    "path": item.get("path", ""),
                    "url": item.get("html_url", ""),
                    "repository": item.get("repository", {}).get("full_name", ""),
                    "score": item.get("score", 0)
                }
                for item in code_results[:per_page]
            ]
        }

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Code search failed: {str(e)}"})


@mcp.tool()
def list_issues(owner: str, repo: str, state: str = "open", per_page: int = 10) -> str:
    """List issues for a repository."""
    try:
        params = {
            "state": state,
            "per_page": min(per_page, 100)
        }

        data = server.make_github_request(f"/repos/{owner}/{repo}/issues", "GET", params)

        issues = [
            {
                "number": issue.get("number", 0),
                "title": issue.get("title", ""),
                "state": issue.get("state", ""),
                "url": issue.get("html_url", ""),
                "created_at": issue.get("created_at", ""),
                "updated_at": issue.get("updated_at", ""),
                "user": issue.get("user", {}).get("login", ""),
                "labels": [label.get("name", "") for label in issue.get("labels", [])]
            }
            for issue in data[:per_page]
        ]

        result = {
            "total_count": len(issues),
            "issues": issues
        }

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Issues list failed: {str(e)}"})


@mcp.tool()
def get_user_repositories(username: str, type: str = "owner", sort: str = "updated", per_page: int = 10) -> str:
    """Get repositories for a specific user."""
    try:
        params = {
            "type": type,
            "sort": sort,
            "per_page": min(per_page, 100)
        }

        data = server.make_github_request(f"/users/{username}/repos", "GET", params)

        repositories = [
            {
                "name": repo.get("name", ""),
                "full_name": repo.get("full_name", ""),
                "description": repo.get("description", ""),
                "url": repo.get("html_url", ""),
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "language": repo.get("language", ""),
                "private": repo.get("private", False),
                "archived": repo.get("archived", False)
            }
            for repo in data[:per_page]
        ]

        result = {
            "total_count": len(repositories),
            "repositories": repositories
        }

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"User repositories failed: {str(e)}"})


@mcp.tool()
def get_latest_commit(owner: str, repo: str) -> str:
    """Get the latest commit from a GitHub repository."""
    try:
        # Get the latest commit from the default branch
        data = server.make_github_request(f"/repos/{owner}/{repo}/commits", "GET", {"per_page": 1})
        
        if not data or len(data) == 0:
            return json.dumps({"error": "No commits found"})
        
        commit_data = data[0]
        commit_info = commit_data.get("commit", {})
        author_info = commit_info.get("author", {})
        
        result = {
            "sha": commit_data.get("sha", ""),
            "commit": {
                "author": {
                    "name": author_info.get("name", "Unknown"),
                    "email": author_info.get("email", ""),
                    "date": author_info.get("date", "")
                },
                "message": commit_info.get("message", ""),
                "url": commit_data.get("html_url", "")
            },
            "branch": "main",  # Default branch
            "stats": commit_data.get("stats", {"additions": 0, "deletions": 0, "total": 0})
        }
        
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Failed to get latest commit: {str(e)}"})


if __name__ == "__main__":
    # Run the server
    mcp.run()