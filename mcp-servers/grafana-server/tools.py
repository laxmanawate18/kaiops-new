"""
Grafana Tools

Tool functions that call the local Grafana MCP server.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.mcp_client import call_mcp_tool, parse_mcp_response


async def search_dashboards(query: str = "", limit: int = 10) -> str:
    """Search Grafana dashboards."""
    try:
        if not query or query.lower() == "n/a":
            return "[WARN] No Grafana dashboard configured."
        
        result = await call_mcp_tool("grafana", "search_dashboards", query=query, limit=limit)
        data = parse_mcp_response(result)
        
        if "error" in data:
            return f"[FAIL] {data['error']}"
        
        dashboards = data.get("dashboards", [])
        if not dashboards:
            return f"No dashboards found for '{query}'"
        
        output = f"[STATS] Found {len(dashboards)} dashboards\n"
        for dash in dashboards:
            output += f"- {dash.get('title', '')}\n"
        
        return output
    except Exception as e:
        return f"[FAIL] Error: {str(e)}"


async def get_dashboard_summary(uid: str) -> str:
    """Get dashboard details."""
    try:
        result = await call_mcp_tool("grafana", "get_dashboard_summary", uid=uid)
        data = parse_mcp_response(result)
        
        if "error" in data:
            return f"[FAIL] {data['error']}"
        
        output = f"[STATS] **{data.get('title', 'Dashboard')}**\n"
        output += f"Panels: {len(data.get('panels', []))}\n"
        output += f"Variables: {', '.join(data.get('variables', []))}\n"
        
        return output
    except Exception as e:
        return f"[FAIL] Error: {str(e)}"


async def list_alert_rules() -> str:
    """List Grafana alert rules."""
    try:
        result = await call_mcp_tool("grafana", "list_alert_rules")
        data = parse_mcp_response(result)
        
        if "error" in data:
            return f"[FAIL] {data['error']}"
        
        # Canonical key is "rules"; accept legacy "alerts" payloads defensively.
        rules = data.get("rules") or data.get("alerts") or []
        if not rules:
            return "No alert rules configured"
        
        output = f"🚨 {len(rules)} alert rules\n"
        for rule in rules[:10]:
            name = rule.get("title") or rule.get("name") or "Unnamed"
            state = rule.get("state", "unknown")
            marker = "⏸️" if state == "paused" else ("🔴" if state == "firing" else "🟢")
            output += f"- {marker} {name} ({state})\n"
        
        return output
    except Exception as e:
        return f"[FAIL] Error: {str(e)}"
