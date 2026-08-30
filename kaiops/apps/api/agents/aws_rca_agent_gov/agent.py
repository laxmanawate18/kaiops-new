"""
AWS RCA Agent - Google ADK Agent for CloudWatch-based RCA

This module initializes the LLM agent with CloudWatch MCP tools for
automated root cause analysis of EKS applications.
"""

import os
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
import datetime

from .prompt import AGENT_INSTRUCTION
from .tools import (
    check_application_logs,
    check_ingress_logs,
    analyze_pod_logs
)
from .config import AWSConfig


def get_current_iso_time() -> str:
    """
    Returns the current Coordinated Universal Time (UTC) date and time
    in the ISO 8601 format (YYYY-MM-DDTHH:MM:SS.sssZ).

    This format is ideal for logging, timestamps, and API interactions.

    Returns:
        str: The current UTC time in ISO 8601 format.
    """
    # Get the current time in UTC
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    
    # Format the time as ISO 8601 string with 'Z' suffix for UTC
    iso_time = now_utc.isoformat().replace('+00:00', 'Z')
    
    return iso_time


# Time tool for current timestamp queries
time_tool = FunctionTool(func=get_current_iso_time)

# Custom tools for RCA analysis
check_app_logs_tool = FunctionTool(func=check_application_logs)
check_ingress_logs_tool = FunctionTool(func=check_ingress_logs)
analyze_logs_tool = FunctionTool(func=analyze_pod_logs)

# Validate AWS configuration
aws_valid, aws_error = AWSConfig.validate()
if not aws_valid:
    print(f"[WARN]  AWS Configuration Warning: {aws_error}")
    print("Please configure AWS credentials in .env file before using AWS RCA Agent")

# Initialize the root agent (AWS RCA via the real HTTP aws-mcp-server tools only)
root_agent = LlmAgent(
    model=os.environ.get("GEMINI_MODEL", "gemini-3.6-flash"),
    name='aws_cloudwatch_rca_agent',
    instruction=AGENT_INSTRUCTION,
    tools=[
        # Custom RCA tools (real CloudWatch via the deployed aws-mcp-server over HTTP)
        check_app_logs_tool,
        check_ingress_logs_tool,
        analyze_logs_tool,
        time_tool,
    ],
)

__all__ = ["root_agent", "get_current_iso_time"]
