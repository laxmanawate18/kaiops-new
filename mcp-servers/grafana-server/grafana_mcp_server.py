#!/usr/bin/env python3
"""
Grafana MCP Server - Python Implementation

MCP server for Grafana observability tools using FastMCP.
Provides tools for dashboard management, metrics querying, and alerting.
"""

import json
import os
import sys
from typing import Any, Dict, Optional

import requests
from mcp.server import FastMCP


class GrafanaMCPServer:
    def __init__(self):
        self.grafana_url = os.getenv("GRAFANA_URL", "http://localhost:3000")
        # Accept any of the common token variable names. Strip so secrets with a
        # trailing newline/CR (common when written via `echo > file`) never break
        # the Authorization header (Grafana rejects whitespace in header values).
        self.service_account_token = (
            (
                os.getenv("GRAFANA_SERVICE_ACCOUNT_TOKEN")
                or os.getenv("GRAFANA_API_KEY")
                or os.getenv("GRAFANA_TOKEN")
                or ""
            ).strip()
        )

        print(f"[*] Grafana MCP Server initialized:", file=sys.stderr)
        print(f"    URL: {self.grafana_url}", file=sys.stderr)
        print(f"    Token present: {bool(self.service_account_token)}", file=sys.stderr)
        print(f"    Token length: {len(self.service_account_token)}", file=sys.stderr)

    def resolve_datasource_uid(self, ds_type: str) -> str:
        """Return the uid of the first datasource matching ds_type ('' if none)."""
        datasources = self.make_grafana_request("/datasources", "GET")
        if not isinstance(datasources, list):
            return ""
        for ds in datasources:
            if ds.get("type") == ds_type:
                return ds.get("uid", "")
        for ds in datasources:
            if str(ds.get("type", "")).startswith(ds_type):
                return ds.get("uid", "")
        return ""

    def make_grafana_request(self, endpoint: str, method: str = "GET", params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make a request to the Grafana API."""
        # Check if Grafana is properly configured
        if not self.grafana_url or self.grafana_url == "http://localhost:3000":
            return {"error": "Grafana not configured. Please set GRAFANA_URL and GRAFANA_SERVICE_ACCOUNT_TOKEN."}
        
        if not self.service_account_token:
            return {"error": f"Grafana authentication token not configured for {self.grafana_url}"}
        
        url = f"{self.grafana_url}/api{endpoint}"

        headers = {
            "Content-Type": "application/json",
        }

        # Add authorization header only if token is provided
        if self.service_account_token:
            headers["Authorization"] = f"Bearer {self.service_account_token}"

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=10, verify=False)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=params, timeout=10, verify=False)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError as e:
            error_msg = f"Cannot connect to Grafana at {self.grafana_url}. Check if server is accessible. Error: {str(e)}"
            print(f"[!] {error_msg}", file=sys.stderr)
            return {"error": error_msg}
        except requests.exceptions.Timeout as e:
            error_msg = f"Grafana request timeout at {self.grafana_url}. Server may be slow or unreachable."
            print(f"[!] {error_msg}", file=sys.stderr)
            return {"error": error_msg}
        except requests.exceptions.HTTPError as e:
            error_msg = f"Grafana API HTTP Error: {response.status_code} {response.reason}"
            print(f"[!] {error_msg}: {response.text}", file=sys.stderr)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Grafana API request failed: {str(e)}"
            print(f"[!] {error_msg}", file=sys.stderr)
            return {"error": error_msg}


# Create FastMCP server
server = GrafanaMCPServer()
mcp = FastMCP("grafana-mcp-server")


@mcp.tool()
def search_dashboards(query: str = "", limit: int = 10) -> str:
    """Search for Grafana dashboards by query."""
    try:
        # Use simple parameters that work with all Grafana versions
        # Only send query parameter if it's not empty to avoid "invalid request parameters" error
        params = {"limit": limit}
        if query and query.strip():
            params["query"] = query

        data = server.make_grafana_request("/search", "GET", params)

        # Handle different response formats
        if isinstance(data, list):
            dashboards = data
        elif isinstance(data, dict) and "dashboards" in data:
            dashboards = data["dashboards"]
        else:
            dashboards = []

        return json.dumps({
            "dashboards": [
                {
                    "title": dashboard.get("title", ""),
                    "uid": dashboard.get("uid", ""),
                    "tags": dashboard.get("tags", []),
                    "url": dashboard.get("url", ""),
                }
                for dashboard in dashboards[:limit]
            ],
            "total": len(dashboards),
        })
    except Exception as e:
        return json.dumps({"error": f"Dashboard search failed: {str(e)}"})


@mcp.tool()
def get_dashboard_summary(uid: str) -> str:
    """Get detailed information about a specific dashboard."""
    try:
        data = server.make_grafana_request(f"/dashboards/uid/{uid}")

        dashboard = data.get("dashboard", {})
        panels = dashboard.get("panels", [])

        return json.dumps({
            "title": dashboard.get("title", ""),
            "uid": dashboard.get("uid", ""),
            "description": dashboard.get("description", ""),
            "panels": [
                {
                    "title": panel.get("title", ""),
                    "type": panel.get("type", ""),
                    "datasource": panel.get("datasource", {}).get("type", "unknown"),
                }
                for panel in panels
            ],
            "variables": [
                v.get("name", "")
                for v in dashboard.get("templating", {}).get("list", [])
            ],
            "tags": dashboard.get("tags", []),
        })
    except Exception as e:
        return json.dumps({"error": f"Dashboard summary failed: {str(e)}"})


@mcp.tool()
def query_prometheus(query: str, datasource_uid: str = "") -> str:
    """Execute a Prometheus query."""
    try:
        # /api/ds/query cannot resolve a type-only datasource ref; if no uid
        # was supplied, look up the default datasource of that type first.
        if not datasource_uid:
            datasource_uid = server.resolve_datasource_uid("prometheus")

        data = server.make_grafana_request("/ds/query", "POST", {
            # /api/ds/query needs an explicit window: without from/to an instant
            # query evaluates in an empty default range and returns 0 samples.
            "from": "now-1h",
            "to": "now",
            "queries": [{
                "refId": "A",
                "datasource": {"type": "prometheus", "uid": datasource_uid},
                "expr": query,
                "instant": True,
                "maxDataPoints": 100,
                "intervalMs": 1000,
            }],
        })

        return json.dumps({
            "status": "success",
            "data": data.get("results", {}).get("A", {}).get("frames", []),
        })
    except Exception as e:
        return json.dumps({"error": f"Prometheus query failed: {str(e)}"})


@mcp.tool()
def query_loki(query: str, datasource_uid: str = "") -> str:
    """Execute a Loki query for logs."""
    try:
        # Same type-only ref problem as Prometheus: resolve a uid first.
        if not datasource_uid:
            datasource_uid = server.resolve_datasource_uid("loki")

        data = server.make_grafana_request("/ds/query", "POST", {
            "from": "now-6h",
            "to": "now",
            "queries": [{
                "refId": "A",
                "datasource": {"type": "loki", "uid": datasource_uid},
                "expr": query,
                "limit": 100,
                "maxDataPoints": 100,
                "intervalMs": 1000,
            }],
        })

        return json.dumps({
            "status": "success",
            "data": data.get("results", {}).get("A", {}).get("frames", []),
        })
    except Exception as e:
        return json.dumps({"error": f"Loki query failed: {str(e)}"})


@mcp.tool()
def list_alert_rules() -> str:
    """List Grafana alert rules with detailed information."""
    try:
        # Get alert rules from provisioning API
        data = server.make_grafana_request("/v1/provisioning/alert-rules")
        
        # Handle response - it returns a list directly
        rules_list = data if isinstance(data, list) else data.get("rules", [])
        
        # Format alert rules with all available details
        formatted_rules = []
        for rule in rules_list:
            is_paused = rule.get("isPaused", False)
            formatted_rule = {
                "uid": rule.get("uid", ""),
                # Expose both "name" and "title" so consumers can rely on either key
                "name": rule.get("title", ""),
                "title": rule.get("title", ""),
                "group": rule.get("ruleGroup", ""),
                "folder": rule.get("folderUID", ""),
                "condition": rule.get("condition", ""),
                "for": rule.get("for", ""),
                "noDataState": rule.get("noDataState", "NoData"),
                "execErrState": rule.get("execErrState", "Error"),
                "isPaused": is_paused,
                "updated": rule.get("updated", ""),
                # Derived state based on isPaused status
                "state": "paused" if is_paused else "active",
            }
            formatted_rules.append(formatted_rule)
        
        firing = sum(1 for r in formatted_rules if r["state"] == "firing")
        paused = sum(1 for r in formatted_rules if r["state"] == "paused")
        
        return json.dumps({
            # Canonical key is "rules" (matches the TypeScript MCP server);
            # legacy consumers reading "alerts" are updated to read "rules".
            "rules": formatted_rules,
            "total": len(formatted_rules),
            "firing": firing,
            "paused": paused,
        })
    except Exception as e:
        import traceback
        print(f"[ERROR] list_alert_rules failed: {str(e)}", file=sys.stderr)
        print(traceback.format_exc(), file=sys.stderr)
        return json.dumps({"error": f"Alert rules query failed: {str(e)}"})


@mcp.tool()
def list_datasources() -> str:
    """List configured Grafana datasources."""
    try:
        data = server.make_grafana_request("/datasources")

        return json.dumps({
            "datasources": [
                {
                    "name": ds.get("name", ""),
                    "type": ds.get("type", ""),
                    "uid": ds.get("uid", ""),
                    "url": ds.get("url", ""),
                    "isDefault": ds.get("isDefault", False),
                }
                for ds in data
            ]
        })
    except Exception as e:
        return json.dumps({"error": f"Datasources query failed: {str(e)}"})


if __name__ == "__main__":
    # Run the server
    mcp.run()