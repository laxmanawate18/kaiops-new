"""
AWS RCA Agent - CloudWatch Logging & Root Cause Analysis for EKS

This agent performs log investigation, troubleshooting, and automated RCA using AWS CloudWatch MCP tools.
It dynamically resolves application names to EKS deployment information from MongoDB metadata.

The standalone LlmAgent (`root_agent`) is exposed lazily via `get_root_agent()` so that merely
importing this package (e.g. `from agents.aws_rca_agent.tools import ...`) does NOT build an
ADK agent or spawn any MCP subprocess at import time.
"""

__all__ = ["get_root_agent"]


def get_root_agent():
    """Build (or return) the standalone AWS RCA agent only when explicitly requested.

    Construction pulls in google-adk's LlmAgent + MCP tooling, which we deliberately
    defer so importing `awsw_rca_agent.tools` stays cheap and never triggers a
    subprocess (uvx) spawn at import time.
    """
    from .agent import root_agent as _root_agent

    return _root_agent
