"""
AWS RCA Specialist — independent reasoning engine entry for Agent Runtime.

Wraps the self-contained AWS RCA specialist agent (from
agents.aws_rca_agent.agent) in an ADK App so `agents-cli deploy` can build it
as its own reasoning engine with --agent-identity.
"""

import os

from google.adk.apps import App  # noqa: E402
from agents.aws_rca_agent.agent import root_agent as aws_root_agent  # noqa: E402

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

aws_root_agent.name = "aws_cloudwatch_rca_specialist"
aws_root_agent.model = MODEL

# The independent AWS RCA specialist engine.
root_agent = aws_root_agent

app = App(
    root_agent=root_agent,
    name="aws_cloudwatch_rca_specialist",
)

__all__ = ["root_agent", "app"]
