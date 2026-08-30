"""
KaiOps Agent Platform Runtime — ADK App entry point.

Wraps the existing KaiOps root_agent (from apps/api/agents) in vertexai's
`AdkApp`, which implements the Agent Runtime contract
(/api/reasoning_engine + /api/stream_reasoning_engine) and, when deployed to
Agent Engine with GOOGLE_GENAI_USE_ENTERPRISE=TRUE, AUTO-BUILDS the managed
VertexAiSessionService (Sessions) + VertexAiMemoryBankService (Memory Bank),
plus enables Cloud Observability (OTel traces/logs/metrics).

This keeps the Cloud Run backend (apps/api/) untouched; this is a thin wrapper
for the Gemini Enterprise Agent Platform deployment.
"""

import os
import sys

# Make apps/api importable so `agents.*` resolves (root_agent lives there).
_APP_API = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "apps", "api")
)
if _APP_API not in sys.path:
    sys.path.insert(0, _APP_API)

# Enterprise mode is what makes AdkApp use the managed Sessions + Memory Bank
# instead of in-memory services. Set it before importing AdkApp/agent.
os.environ.setdefault("GOOGLE_GENAI_USE_ENTERPRISE", "TRUE")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# The KaiOps root agent (with its sub_agents, tools, prompts). Reused as-is.
from agents.sre_agent.agent import root_agent  # noqa: E402

try:
    from vertexai import agent_engines
    from vertexai.agent_engines import AdkApp
except Exception as e:  # pragma: no cover - import only fails if deps missing
    logger.error(f"[RUNTIME] Failed to import vertexai.agent_engines.AdkApp: {e}")
    raise


def build_adk_app():
    """Build the AdkApp wrapper around the KaiOps root_agent."""
    adk_app = AdkApp(
        agent=root_agent,
        app_name="kaiops_sre_agent",
        # Do NOT pass session_service_builder/memory_service_builder: on Agent
        # Engine the template auto-builds VertexAiSessionService +
        # VertexAiMemoryBankService (managed Sessions + Memory Bank).
        # enable_tracing is deprecated; telemetry is controlled by the
        # GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY env var at deploy time.
    )
    logger.info("[RUNTIME] AdkApp built wrapping root_agent (SRE agent)")
    return adk_app


# Module-level instance so the runtime server picks it up.
runtime_app = build_adk_app()

__all__ = ["runtime_app", "build_adk_app", "AdkApp"]
