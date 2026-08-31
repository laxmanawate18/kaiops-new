"""
GCP RCA Agent - Google ADK Agent for Cloud Logging-based RCA

This module initializes the LLM agent with GCP Cloud Logging tools for
automated root cause analysis of GKE applications.

Uses direct GCP API calls (no MCP server required).
"""

import os
import logging
import datetime
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from .config import GCPConfig
from .prompt import AGENT_INSTRUCTION
from .tools import (
    check_application_logs,
    check_ingress_logs,
    analyze_pod_logs
)

logger = logging.getLogger(__name__)


def get_current_iso_time() -> str:
    """
    Returns the current Coordinated Universal Time (UTC) date and time
    in the ISO 8601 format (YYYY-MM-DDTHH:MM:SS.sssZ).

    This format is ideal for logging, timestamps, and API interactions.

    Returns:
        str: The current UTC time in ISO 8601 format.
    """
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    iso_time = now_utc.isoformat().replace('+00:00', 'Z')
    return iso_time


# Time tool for current timestamp queries
time_tool = FunctionTool(func=get_current_iso_time)

# Custom tools for RCA analysis
check_app_logs_tool = FunctionTool(func=check_application_logs)
check_ingress_logs_tool = FunctionTool(func=check_ingress_logs)
analyze_logs_tool = FunctionTool(func=analyze_pod_logs)

# Validate GCP configuration
gcp_valid, gcp_error = GCPConfig.validate()
if not gcp_valid:
    logger.warning(f" GCP Configuration Warning: {gcp_error}")
    logger.warning("Please configure GCP credentials in .env file before using GCP RCA Agent")
else:
    logger.info(f" GCP Configuration validated:")
    logger.info(f"   Project: {GCPConfig.GCP_PROJECT_ID}")
    logger.info(f"   Cluster: {GCPConfig.GCP_CLUSTER_NAME}")
    logger.info(f"   Zone: {GCPConfig.GCP_CLUSTER_ZONE}")

# Initialize the GCP RCA Agent
root_agent = LlmAgent(
    model=os.environ.get("GEMINI_MODEL", "gemini-3.6-flash"),
    name='gcp_cloud_logging_rca_agent',
    instruction=AGENT_INSTRUCTION,
    tools=[
        # Custom RCA tools (using Python functions, direct GCP API calls)
        check_app_logs_tool,
        check_ingress_logs_tool,
        analyze_logs_tool,
        time_tool
    ],
)

logger.info(" GCP RCA Agent initialized successfully")
logger.info(f"   Agent name: {root_agent.name}")
logger.info(f"   Tools available: {len(root_agent.tools)}")

__all__ = ["root_agent", "get_current_iso_time"]
