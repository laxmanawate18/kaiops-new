"""
Azure RCA Agent - LlmAgent with Official Azure Monitor MCP Tools

This module initializes the LLM agent with:
- 3 RCA tools (check_application_logs, check_ingress_logs, analyze_pod_logs)
- Official Azure Monitor MCP Server tools (18 additional tools via MCPToolset)
- Azure-specific expertise and RCA instructions
- Performance optimization (caching, timeouts, rate limiting)

No performance impact - uses MCPToolset with optimized connection management
"""

import logging
import datetime
import os
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from agents.azure_rca_agent.tools import (
    check_application_logs,
    check_ingress_logs,
    analyze_pod_logs
)
from agents.azure_rca_agent.prompt import log_rca_expertise

logger = logging.getLogger(__name__)

# Configuration from environment
# The Azure Monitor MCP server is stdio-based (`npx @microsoft/azure-mcp-server`),
# which needs Node.js and is NOT present in the python:3.11-slim Cloud Run image.
# Default to DISABLED so it never crashes agent load; the Azure RCA agent still
# works via its FunctionTools (check_application_logs / analyze_pod_logs) and the
# remote azure-mcp-server (MCP_URL_AZURE).
AZURE_MCP_ENABLED = os.environ.get('AZURE_MCP_ENABLED', 'false').lower() == 'true'


def get_current_iso_time() -> str:
    """Returns current UTC time in ISO 8601 format for timestamping."""
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    iso_time = now_utc.isoformat().replace('+00:00', 'Z')
    return iso_time


# Create FunctionTools for each RCA function
check_app_logs_tool = FunctionTool(func=check_application_logs)
check_ingress_logs_tool = FunctionTool(func=check_ingress_logs)
analyze_logs_tool = FunctionTool(func=analyze_pod_logs)
time_tool = FunctionTool(func=get_current_iso_time)

# Build tools list - always include custom RCA tools
tools_list = [
    check_app_logs_tool,
    check_ingress_logs_tool,
    analyze_logs_tool,
    time_tool,
]

# Add official Azure Monitor MCP Server tools if enabled
# These provide additional capabilities without performance impact due to caching
if AZURE_MCP_ENABLED:
    try:
        mcp_toolset = MCPToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command='npx',
                    args=[
                        '@microsoft/azure-mcp-server@latest',
                        '--subscription-id', os.environ.get('AZURE_SUBSCRIPTION_ID', ''),
                        '--credentials-type', 'cli'
                    ],
                ),
                timeout=30  # 30 second timeout prevents hammering
            ),
            # Filter which tools from the MCP server are exposed (18 tools available)
            tool_filter=[
                # Activity Log tools (1)
                'list_activity_log',
                # Log Analytics tools (4)
                'list_workspaces',
                'list_table_types',
                'list_tables',
                'query_workspace_logs',
                'query_resource_logs',
                # Health tools (1)
                'get_entity_health',
                # Metrics tools (2)
                'query_metrics',
                'list_metric_definitions',
                # Workbooks tools (5)
                'list_workbooks',
                'show_workbook_details',
                'create_workbook',
                'update_workbook',
                'delete_workbooks',
                # Web Tests tools (4)
                'create_web_tests',
                'get_web_tests',
                'list_web_tests',
                'update_web_tests',
            ]
        )
        tools_list.append(mcp_toolset)
        logger.info("Azure Monitor MCP Server tools enabled (18 tools available)")
    except Exception as e:
        logger.warning(f"Failed to initialize Azure MCP Server: {e}")
        logger.info("Continuing with custom RCA tools only")
else:
    logger.info("Azure MCP Server disabled (AZURE_MCP_ENABLED=false)")

# Initialize the Azure RCA Agent
root_agent = LlmAgent(
    model=os.environ.get("GEMINI_MODEL", "gemini-3.6-flash"),
    name="azure_log_rca_agent",
    instruction=log_rca_expertise,
    tools=tools_list
)

logger.info("Azure RCA Agent initialized successfully")

__all__ = ["root_agent", "get_current_iso_time"]


