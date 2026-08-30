"""
Azure RCA Specialist — independent reasoning engine entry for Agent Runtime.

Wraps the self-contained Azure RCA specialist agent (from
agents.azure_rca_agent.agent) in an ADK App so `agents-cli deploy` can build it
as its own reasoning engine with --agent-identity.
"""

import os

# Skip any npx MCPToolset (defensive; the specialist agent has none already).
os.environ.setdefault("AZURE_MCP_ENABLED", "false")

from google.adk.apps import App  # noqa: E402
from agents.azure_rca_agent.agent import root_agent as azure_root_agent  # noqa: E402

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

azure_root_agent.name = "azure_rca_specialist"
azure_root_agent.model = MODEL

# The independent Azure RCA specialist engine.
root_agent = azure_root_agent

app = App(
    root_agent=root_agent,
    name="azure_rca_specialist",
)

__all__ = ["root_agent", "app"]
