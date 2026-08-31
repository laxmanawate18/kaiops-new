"""
GCP RCA Agent - Cloud Logging & Root Cause Analysis for GKE

This agent performs log investigation, troubleshooting, and automated RCA using
Google Cloud Logging and Cloud Monitoring APIs directly (no MCP server needed).
It dynamically resolves application names to GKE deployment information from MongoDB metadata.

The standalone LlmAgent (`root_agent`) is exposed lazily via `get_root_agent()` so that merely
importing this package (e.g. `from agents.gcp_rca_agent.tools import ...`) does NOT build an
ADK agent at import time.
"""

__all__ = ["get_root_agent"]


def get_root_agent():
    """Build (or return) the standalone GCP RCA agent only when explicitly requested."""
    from .agent import root_agent as _root_agent

    return _root_agent
