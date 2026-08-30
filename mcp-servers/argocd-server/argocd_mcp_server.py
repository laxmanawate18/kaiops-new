#!/usr/bin/env python3
"""
ArgoCD MCP Server - Python Implementation

MCP server for ArgoCD deployment management using FastMCP.
Provides tools for application management, synchronization, and monitoring.
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


class ArgocdMCPServer:
    def __init__(self):
        self.argocd_url = os.getenv("ARGOCD_URL", "http://localhost:8080")
        self.argocd_token = os.getenv("ARGOCD_AUTH_TOKEN", "")

        print(f"[*] ArgoCD MCP Server initialized:", file=sys.stderr)
        print(f"    URL: {self.argocd_url}", file=sys.stderr)
        print(f"    Token present: {bool(self.argocd_token)}", file=sys.stderr)

    def make_argocd_request(self, endpoint: str, method: str = "GET", params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a request to the ArgoCD API."""
        # Check if ArgoCD is properly configured
        if not self.argocd_url or self.argocd_url == "http://localhost:8080":
            return {"error": "ArgoCD not configured. Please set ARGOCD_URL and ARGOCD_AUTH_TOKEN."}
        
        if not self.argocd_token:
            return {"error": f"ArgoCD authentication token not configured for {self.argocd_url}"}
        
        url = f"{self.argocd_url}/api/v1{endpoint}"

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # Add authorization header only if token is provided
        if self.argocd_token:
            headers["Authorization"] = f"Bearer {self.argocd_token}"

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=10, verify=False)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=params, timeout=10, verify=False)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=params, timeout=10, verify=False)
            elif method == "PATCH":
                headers["Content-Type"] = "application/merge-patch+json"
                response = requests.patch(url, headers=headers, json=params, timeout=10, verify=False)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError as e:
            error_msg = f"Cannot connect to ArgoCD at {self.argocd_url}. Check if server is accessible. Error: {str(e)}"
            print(f"[!] {error_msg}", file=sys.stderr)
            return {"error": error_msg}
        except requests.exceptions.Timeout as e:
            error_msg = f"ArgoCD request timeout at {self.argocd_url}. Server may be slow or unreachable."
            print(f"[!] {error_msg}", file=sys.stderr)
            return {"error": error_msg}
        except requests.exceptions.HTTPError as e:
            body = ""
            try:
                body = response.text[:300]
            except Exception:  # noqa: BLE001
                pass
            error_msg = f"ArgoCD API HTTP Error: {response.status_code} {response.reason}" + (f" | detail: {body}" if body else "")
            print(f"[!] {error_msg}", file=sys.stderr)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"ArgoCD API request failed: {str(e)}"
            print(f"[!] {error_msg}", file=sys.stderr)
            return {"error": error_msg}


# Create FastMCP server
server = ArgocdMCPServer()
mcp = FastMCP("argocd-mcp-server")


@mcp.tool()
def list_applications(project: str = "", limit: int = 50) -> str:
    """List all ArgoCD applications."""
    try:
        params = {"limit": limit}
        if project:
            params["projects"] = project

        data = server.make_argocd_request("/applications", "GET", params)

        applications = data.get("items", []) if isinstance(data, dict) else data
        if "error" in data:
            return json.dumps(data)

        applications = (data.get("items") or []) if isinstance(data, dict) else (data or [])

        result = {
            "total": len(applications),
            "applications": [
                {
                    "name": app.get("metadata", {}).get("name", ""),
                    "namespace": app.get("metadata", {}).get("namespace", ""),
                    "project": app.get("spec", {}).get("project", ""),
                    "sync_status": app.get("status", {}).get("sync", {}).get("status", "Unknown"),
                    "health_status": app.get("status", {}).get("health", {}).get("status", "Unknown"),
                    "repo_url": app.get("spec", {}).get("source", {}).get("repoURL", ""),
                    "target_revision": app.get("spec", {}).get("source", {}).get("targetRevision", "")
                }
                for app in applications
            ]
        }

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Failed to list applications: {str(e)}"})


@mcp.tool()
def get_application_details(app_name: str) -> str:
    """Get detailed information about a specific ArgoCD application."""
    try:
        data = server.make_argocd_request(f"/applications/{app_name}", "GET")

        result = {
            "name": data.get("metadata", {}).get("name", ""),
            "namespace": data.get("metadata", {}).get("namespace", ""),
            "project": data.get("spec", {}).get("project", ""),
            "sync_status": data.get("status", {}).get("sync", {}).get("status", "Unknown"),
            "health_status": data.get("status", {}).get("health", {}).get("status", "Unknown"),
            "source": {
                "repo_url": data.get("spec", {}).get("source", {}).get("repoURL", ""),
                "path": data.get("spec", {}).get("source", {}).get("path", ""),
                "target_revision": data.get("spec", {}).get("source", {}).get("targetRevision", "")
            },
            "destination": {
                "server": data.get("spec", {}).get("destination", {}).get("server", ""),
                "namespace": data.get("spec", {}).get("destination", {}).get("namespace", "")
            },
            "last_sync_time": data.get("status", {}).get("operationState", {}).get("finishedAt", ""),
            "last_sync_result": data.get("status", {}).get("operationState", {}).get("phase", "")
        }

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Failed to get application details: {str(e)}"})


@mcp.tool()
def get_application_status(app_name: str) -> str:
    """Get sync and health status of an ArgoCD application."""
    try:
        data = server.make_argocd_request(f"/applications/{app_name}", "GET")

        # Fail loudly for missing/unreachable apps instead of returning
        # Unknown placeholders indistinguishable from a real degraded app.
        if isinstance(data, dict) and "error" in data:
            not_found_markers = ("404", "not found")
            if any(m in str(data["error"]).lower() for m in not_found_markers):
                return json.dumps({"error": f"Application '{app_name}' not found in ArgoCD"})
            return json.dumps(data)

        result = {
            "app_name": app_name,
            "sync_status": data.get("status", {}).get("sync", {}).get("status", "Unknown"),
            "health_status": data.get("status", {}).get("health", {}).get("status", "Unknown"),
            "sync_message": data.get("status", {}).get("sync", {}).get("comparedTo", {}).get("source", ""),
            "last_sync_time": data.get("status", {}).get("operationState", {}).get("finishedAt", ""),
            "last_sync_result": data.get("status", {}).get("operationState", {}).get("phase", ""),
            "resources": {
                "total": len(data.get("status", {}).get("resources", [])),
                "healthy": sum(1 for r in data.get("status", {}).get("resources", []) if r.get("health", {}).get("status") == "Healthy")
            }
        }

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Failed to get application status: {str(e)}"})


@mcp.tool()
def sync_application(app_name: str, force: bool = False, prune: bool = False) -> str:
    """Trigger a manual sync of an ArgoCD application."""
    try:
        params = {
            "name": app_name,
            "appNamespace": "argocd"
        }

        # For sync, we typically POST with sync preferences in body
        sync_params = {
            "dryRun": False,
            "prune": prune,
            "force": force
        }

        data = server.make_argocd_request(f"/applications/{app_name}/sync", "POST", sync_params)

        result = {
            "app_name": app_name,
            "status": "Sync initiated",
            "operation_id": data.get("metadata", {}).get("uid", ""),
            "sync_phase": data.get("status", {}).get("operationState", {}).get("phase", "Pending")
        }

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Failed to sync application: {str(e)}"})


@mcp.tool()
def rollback_application(app_name: str, target_revision: str = "", deployment_id: int = -1, prune: bool = False) -> str:
    """Roll back an ArgoCD application to a previous deployment.

    Resolves a commit SHA (full or short) against the application's sync
    history and triggers the native ArgoCD rollback API. Alternatively a
    numeric history deployment_id can be supplied directly.
    ArgoCD REJECTS rollbacks while Git auto-sync is enabled; this tool
    detects that condition and temporarily disables auto-sync first,
    reporting every step it took.
    """
    try:
        autosync_disabled = False

        resolved_id = deployment_id

        if resolved_id is None or int(resolved_id) < 0:
            rev = (target_revision or "").strip().lower()
            if not rev or rev in ("n/a", "none"):
                return json.dumps({
                    "error": "Either target_revision (commit SHA) or deployment_id is required for rollback."
                })

            data = server.make_argocd_request(f"/applications/{app_name}", "GET")
            if isinstance(data, dict) and "error" in data:
                return json.dumps(data)

            history = data.get("status", {}).get("history", []) if isinstance(data, dict) else []
            match = next(
                (h for h in history if str(h.get("revision", "")).lower().startswith(rev)),
                None,
            )
            if not match:
                revisions = [h.get("revision", "")[:12] for h in history]
                return json.dumps({
                    "error": (
                        f"Revision '{target_revision}' not found in deployment history "
                        f"of '{app_name}'. Available revisions: {revisions}"
                    )
                })
            resolved_id = match.get("id")

            # Detect Git auto-sync BEFORE attempting rollback (ArgoCD 400s otherwise)
            sync_policy = data.get("spec", {}).get("syncPolicy", {}) if isinstance(data, dict) else {}
            if isinstance(sync_policy, dict) and sync_policy.get("automated"):
                app_obj = data.get("metadata") or {}
                spec_obj = data.get("spec") or {}
                spec_obj.pop("syncPolicy", None)
                for f in ("uid", "resourceVersion", "creationTimestamp",
                          "generation", "managedFields", "selfLink"):
                    app_obj.pop(f, None)
                stripped_meta = {k: v for k, v in app_obj.items()
                                 if k in ("name", "namespace", "labels", "annotations")}
                put_body = {"metadata": stripped_meta, "spec": spec_obj}
                updated = server.make_argocd_request(
                    f"/applications/{app_name}", "PUT", put_body
                )
                if isinstance(updated, dict) and "error" in updated:
                    return json.dumps({
                        "error": (
                            "Rollback requires auto-sync to be disabled, but failed to "
                            f"disable it: {updated.get('error')}"
                        )
                    })
                autosync_disabled = True

        body = {
            "name": app_name,
            "id": int(resolved_id),
            "prune": prune,
            "dryRun": False,
        }
        result = server.make_argocd_request(f"/applications/{app_name}/rollback", "POST", body)

        if isinstance(result, dict) and "error" in result:
            return json.dumps(result)

        notes = [
            "ArgoCD disables auto-sync after a rollback; re-enable sync to restore GitOps drift correction."
        ]
        if autosync_disabled:
            notes.insert(0, "Git auto-sync was ENABLED — the tool disabled it automatically so the rollback could proceed.")
        if autosync_disabled:
            pass

        resp_payload = {
            "app_name": app_name,
            "rolled_back_to_deployment_id": int(resolved_id),
            "target_revision": target_revision,
            "autosync_was_disabled_by_tool": autosync_disabled,
            "status": "Rollback initiated",
            "sync_status": result.get("status", {}).get("sync", {}).get("status", "") if isinstance(result, dict) else "",
            "health_status": result.get("status", {}).get("health", {}).get("status", "") if isinstance(result, dict) else "",
        }
        resp_payload["note"] = (" ".join(notes) if autosync_disabled else notes[0])
        return json.dumps(resp_payload)
    except Exception as e:
        return json.dumps({"error": f"Failed to roll back application: {str(e)}"})


@mcp.tool()
def get_deployment_history(app_name: str, limit: int = 10) -> str:
    """Get deployment/sync history of an ArgoCD application."""
    try:
        data = server.make_argocd_request(f"/applications/{app_name}", "GET")

        history = data.get("status", {}).get("history", [])

        result = {
            "app_name": app_name,
            "total_syncs": len(history),
            "recent_syncs": [
                {
                    "revision": sync.get("revision", ""),
                    "deployed_at": sync.get("deployedAt", ""),
                    "status": sync.get("result", {}).get("phase", "Unknown"),
                    "message": sync.get("result", {}).get("message", "")
                }
                for sync in history[:limit]
            ]
        }

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Failed to get deployment history: {str(e)}"})


@mcp.tool()
def search_applications(query: str, limit: int = 20) -> str:
    """Search for ArgoCD applications by name or label."""
    try:
        data = server.make_argocd_request("/applications", "GET", {"limit": 100})

        applications = data.get("items", []) if isinstance(data, dict) else data
        if "error" in data:
            return json.dumps(data)

        applications = (data.get("items") or []) if isinstance(data, dict) else (data or [])
        query_lower = query.lower()
        # Token-aware matching so "todo" also finds "azure-to-do" /
        # "todo-app". Each query token must appear in at least one of:
        #   a) the raw lowercase text ("azure-to-do"),
        #   b) separator-normalized text ("azure to do"),
        #   c) separator-squashed text ("azluetodo"-style concatenation).
        def _variants(s: str):
            low = (s or "").lower()
            yield low
            norm = low.replace("-", " ").replace("_", " ")
            yield norm
            yield norm.replace(" ", "")
            yield low.replace("-", "").replace("_", "")

        def _matches(app: dict) -> bool:
            name = app.get("metadata", {}).get("name", "")
            project = app.get("spec", {}).get("project", "")
            hay_variants = [a + " " + b for b in _variants(project) for a in _variants(name)]
            if not query_lower.strip():
                return True
            for tok in query_lower.replace("-", " ").replace("_", " ").split():
                if not any(
                    tok in hv or tok in hv.replace(" ", "")
                    for hv in hay_variants
                ):
                    return False
            return True

        filtered = [
            app for app in applications
            if _matches(app)
        ][:limit]

        result = {
            "query": query,
            "results_count": len(filtered),
            "applications": [
                {
                    "name": app.get("metadata", {}).get("name", ""),
                    "project": app.get("spec", {}).get("project", ""),
                    "sync_status": app.get("status", {}).get("sync", {}).get("status", "Unknown"),
                    "health_status": app.get("status", {}).get("health", {}).get("status", "Unknown")
                }
                for app in filtered
            ]
        }

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Failed to search applications: {str(e)}"})


@mcp.tool()
def list_repositories() -> str:
    """List all configured Git repositories in ArgoCD."""
    try:
        data = server.make_argocd_request("/repositories", "GET")

        repositories = data.get("items") or [] if isinstance(data, dict) else (data or [])
        if isinstance(data, dict) and "error" in data:
            return json.dumps(data)

        result = {
            "total": len(repositories),
            "repositories": [
                {
                    "url": repo.get("repo", ""),
                    "connection_status": repo.get("connectionState", {}).get("status", "Unknown"),
                    "last_checked": repo.get("connectionState", {}).get("attemptedAt", ""),
                    "insecure": repo.get("insecure", False)
                }
                for repo in repositories
                if isinstance(repo, dict)
            ]
        }

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Failed to list repositories: {str(e)}"})


@mcp.tool()
def list_projects() -> str:
    """List all ArgoCD projects."""
    try:
        data = server.make_argocd_request("/projects", "GET")

        projects = data.get("items", []) if isinstance(data, dict) else data

        result = {
            "total": len(projects),
            "projects": [
                {
                    "name": proj.get("metadata", {}).get("name", ""),
                    "description": proj.get("spec", {}).get("description", ""),
                    "destinations": len(proj.get("spec", {}).get("destinations", [])),
                    "source_repos": len(proj.get("spec", {}).get("sourceRepos", []))
                }
                for proj in projects
            ]
        }

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Failed to list projects: {str(e)}"})


@mcp.tool()
def get_server_info() -> str:
    """Get ArgoCD server version and information."""
    try:
        data = server.make_argocd_request("/version", "GET")

        if isinstance(data, dict) and "error" in data:
            return json.dumps(data)

        result = {
            # ArgoCD returns capitalized keys; fall back to lowercase variants.
            "version": data.get("Version") or data.get("version", ""),
            "build_date": data.get("BuildDate") or data.get("buildDate", ""),
            "git_commit": data.get("GitCommit") or data.get("gitCommit", ""),
            "git_branch": data.get("GitBranch") or data.get("gitBranch", "")
        }

        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"Failed to get server info: {str(e)}"})


if __name__ == "__main__":
    print("Starting ArgoCD MCP Server...", file=sys.stderr)
    mcp.run()
