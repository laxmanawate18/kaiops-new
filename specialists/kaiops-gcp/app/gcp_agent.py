"""
GCP RCA Specialist — independent reasoning engine entry for Agent Runtime.

Wraps the self-contained GCP RCA specialist agent (from
agents.gcp_rca_agent.agent) in an ADK App so `agents-cli deploy` can build it
as its own reasoning engine with --agent-identity.
"""

import os

from google.adk.apps import App  # noqa: E402
from agents.gcp_rca_agent.agent import root_agent as gcp_root_agent  # noqa: E402

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

gcp_root_agent.name = "gcp_cloud_logging_rca_specialist"
gcp_root_agent.model = MODEL

# The independent GCP RCA specialist engine.
root_agent = gcp_root_agent

app = App(
    root_agent=root_agent,
    name="gcp_cloud_logging_rca_specialist",
)

__all__ = ["root_agent", "app"]
