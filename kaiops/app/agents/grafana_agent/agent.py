"""
Grafana Agent

Domain expert for observability and system monitoring.
Coordinates with Grafana MCP server for dashboards and alerts.
"""

from agents.grafana_agent.tools import (
    search_dashboards,
    get_dashboard_summary,
    list_alert_rules
)

from agents.grafana_agent.prompt import grafana_expertise

# Grafana agent exports tools and prompt for root agent composition
grafana_tools = [
    search_dashboards,
    get_dashboard_summary,
    list_alert_rules
]

grafana_prompt = grafana_expertise

__all__ = [
    "grafana_tools",
    "grafana_prompt",
    "search_dashboards",
    "get_dashboard_summary",
    "list_alert_rules"
]
