"""
Azure RCA Specialist Agent — self-contained ADK 2.x LlmAgent for Agent Runtime.

This is the INDEPENDENT Azure RCA specialist reasoning engine. It:
- Uses NO npx MCPToolset (which hung the Agent Runtime build). Azure Log
  Analytics / AKS access is done via the direct HTTP client in
  azure_rca_agent/mcp_client.py (requests-only, lazy/import-safe).
- Exposes the tool functions: check_application_logs, check_ingress_logs,
  analyze_pod_logs.
"""

import logging
import datetime
import os
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from agents.azure_rca_agent.tools import (
    check_application_logs,
    check_ingress_logs,
    analyze_pod_logs,
)
from agents.azure_rca_agent.prompt import log_rca_expertise

logger = logging.getLogger(__name__)


def get_current_iso_time() -> str:
    """Returns the current UTC time in ISO 8601 format (Z suffix)."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    return now_utc.isoformat().replace("+00:00", "Z")


# Self-contained tool wrappers (requests-only, no npx, no import-time I/O)
check_app_logs_tool = FunctionTool(func=check_application_logs)
check_ingress_logs_tool = FunctionTool(func=check_ingress_logs)
analyze_logs_tool = FunctionTool(func=analyze_pod_logs)
time_tool = FunctionTool(func=get_current_iso_time)

logger.info("Azure RCA Specialist initialized (no npx MCPToolset); using direct HTTP alpha client")

# The independent Azure RCA specialist agent (no sub-agents, self-contained)
root_agent = LlmAgent(
    model=os.environ.get("GEMINI_MODEL", "gemini-3.6-flash"),
    name="azure_rca_specialist",
    instruction=log_rca_expertise,
    tools=[
        check_app_logs_tool,
        check_ingress_logs_tool,
        analyze_logs_tool,
        time_tool,
    ],
)

logger.info("Azure RCA Specialist agent initialized successfully")

__all__ = ["root_agent", "get_current_iso_time"]


