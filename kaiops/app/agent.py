# KaiOps full SRE agent — Agent Platform Runtime entry.
# Wraps the FULL KaiOps root_agent (26+ tools + 3 cloud subagents + runbooks +
# history + Slack) from apps/api in the ADK App. The heavy Azure MCPToolset
# (npx spawn) is DISABLED at runtime via AZURE_MCP_ENABLED=false (set in the
# runtime env) so the container builds/serves cleanly on Agent Runtime.
import os
import sys

# Make apps/api importable so `agents.*` resolves. In the Agent Runtime
# container, the working dir is /code and agents live at /code/apps/api/agents,
# so we must add that dir to sys.path for `from agents.sre_agent.agent import`.
_APP_API = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "apps", "api"))
if _APP_API not in sys.path:
    sys.path.insert(0, _APP_API)
# Also ensure cwd is on path so 'agents' resolves if apps/api is already cwd.
for _p in ("", "."):
    if _p not in sys.path:
        sys.path.append(_p)

# Disable the Azure npx MCPToolset BEFORE importing the agent (import-time gate).
os.environ.setdefault("AZURE_MCP_ENABLED", "false")

from google.adk.apps import App

# The real KaiOps full root agent (imports all domain tools/subagents).
from agents.sre_agent.agent import root_agent as kaiops_root_agent

# Use the imported KaiOps root_agent DIRECTLY — it already has its 3 cloud
# subagents parented to it. Set a platform-served name and wrap in the ADK App.
# ADK 2.x forbids re-parenting a sub_agent to a second parent, so we must NOT
# create a new Agent with the same sub_agents; reuse kaiops_root_agent as-is.
kaiops_root_agent.name = "kaiops_sre_agent"
root_agent = kaiops_root_agent

app = App(root_agent=root_agent, name="kaiops")

__all__ = ["root_agent", "app"]
