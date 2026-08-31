"""
Grafana Agent Tools

Tool functions for observability and monitoring via Grafana MCP Server.
"""

import logging
from agents.mcp_client import call_mcp_tool

logger = logging.getLogger(__name__)

async def _call_and_format_grafana_mcp(tool_name: str, **kwargs) -> str:
    """Helper to call MCP and return the raw text content."""
    try:
        result = await call_mcp_tool('grafana', tool_name, **kwargs)
        if "error" in result:
            return f"[FAIL] **Grafana MCP Error**: {result['error']}"
            
        content = result.get("content", [])
        if content and len(content) > 0:
            return content[0].get("text", "No content returned.")
        return "No content in MCP response."
    except Exception as e:
        logger.error(f"Grafana MCP call failed: {e}")
        return f"[FAIL] **Error**: {str(e)}"


async def search_dashboards(query: str = "", limit: int = 10) -> str:
    """Search for Grafana dashboards by query with comprehensive details."""
    return await _call_and_format_grafana_mcp("search_dashboards", query=query, limit=limit)


async def get_dashboard_summary(uid: str) -> str:
    """Get detailed summary of a Grafana dashboard by UID."""
    if not uid:
        return "[WARN] **Invalid Dashboard UID**"
    return await _call_and_format_grafana_mcp("get_dashboard_summary", uid=uid)


async def list_alert_rules() -> str:
    """Get list of alert rules and active alert status in Grafana."""
    return await _call_and_format_grafana_mcp("list_alert_rules")


__all__ = [
    "search_dashboards",
    "get_dashboard_summary",
    "list_alert_rules"
]
