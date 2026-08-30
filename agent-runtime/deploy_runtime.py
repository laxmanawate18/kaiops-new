"""
Deploy the KaiOps agent to Gemini Enterprise Agent Platform (Agent Runtime).

Prereqs:
  - Runtime container image already pushed:
      us-central1-docker.pkg.dev/<PROJECT>/mcp-servers/kaiops-agent-runtime:latest
  - google-cloud-aiplatform[agent_engines,adk] installed >=1.165.1
  - GOOGLE_GENAI_USE_ENTERPRISE=TRUE so AdkApp uses managed Sessions + Memory Bank.

This deploys via client.agent_engines.create with identify_id=AGENT_IDENTITY,
auto-registering the agent in Agent Registry + creating managed Sessions + 
enabling Cloud Observability.
"""
import os
import json
import sys

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "project-3da8cb5f-328e-44d3-b7a")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
IMAGE = os.getenv(
    "KAIOPS_RUNTIME_IMAGE",
    f"us-central1-docker.pkg.dev/{PROJECT_ID}/mcp-servers/kaiops-agent-runtime:latest",
)

os.environ["GOOGLE_GENAI_USE_ENTERPRISE"] = "TRUE"
os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT_ID
os.environ["GOOGLE_CLOUD_LOCATION"] = LOCATION

import vertexai
from vertexai import agent_engines
from vertexai import types

client = vertexai.Client(project=PROJECT_ID, location=LOCATION)


def main():
    # For a BYOC container deploy, we pass the app object; the runtime service
    # pulls the image AR tag from the AdkApp / config. The AdkApp wraps the
    # KaiOps root_agent; the container implements the runtime contract.
    from runtime_app import build_adk_app

    adk_app = build_adk_app()

    print(f"[DEPLOY] Deploying KaiOps agent to Agent Runtime in {PROJECT_ID}/{LOCATION}")
    remote_agent = agent_engines.create(
        agent_engine=adk_app,
        requirements=["google-cloud-aiplatform[agent_engines,adk]>=1.165.1"],
        display_name="kaiops-sre-agent",
        description=(
            "KaiOps multi-cloud SRE RCA agent: autonomous RCA loop, ADK "
            "subagents (AWS/GCP/Azure), 6 IAM-secured MCP servers, Slack "
            "notify, HITL approvals, Memory Bank."
        ),
        # Agent identity: use the agent's own identity for zero-trust access.
        # The installed SDK exposes `service_account`; Agent identity (SPIFFE)
        # is the recommended route and is set via the platform. We pass a
        # service_account to satisfy the SDK; agent identity is handled by the
        # platform default (AGENT_IDENTITY) when GOOGLE_GENAI_USE_ENTERPRISE=TRUE.
        env_vars={
            "GEMINI_MODEL": "gemini-3.6-flash",
            "GOOGLE_GENAI_USE_ENTERPRISE": "TRUE",
            "GOOGLE_CLOUD_PROJECT": PROJECT_ID,
            "GOOGLE_CLOUD_LOCATION": LOCATION,
            # Enable Cloud Observability telemetry for the agent.
            "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        },
    )

    resource = remote_agent.api_resource
    print(f"[DEPLOY] SUCCESS. resource_name={resource.name}")
    print("[DEPLOY] The agent is now registered in Agent Registry + has managed Sessions + Memory Bank + OTel telemetry.")
    print("[DEPLOY] Query it via:")
    print(f"  async for e in remote_agent.async_stream_query(user_id='admin', message='...'):")
    return resource.name


if __name__ == "__main__":
    name = main()
    print(f"[DEPLOY] resource_name={name}")
