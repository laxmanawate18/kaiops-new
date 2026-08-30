"""
KaiOps Gateway + Identity Isolation Agent

This is a MINIMAL, self-contained ADK agent created specifically to validate
that Agent Identity (identity_type=AGENT_IDENTITY) and Agent Gateway
(agent_gateway_config) can be bound TOGETHER at agent creation time.

It is deliberately isolated from the working 4-engine A2A mesh so it does not
disrupt the existing deployment. It has zero external tool dependencies so the
deployment is lightweight and fast to verify.

Deployment (documented path in
docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-gateway-runtime-deploy):
    client = vertexai.Client(project=PROJECT, location=LOCATION,
                             http_options=dict(api_version="v1beta1"))
    remote = client.agent_engines.create(
        agent=AdkApp(agent=root_agent),
        config={
            "display_name": "...",
            "identity_type": types.IdentityType.AGENT_IDENTITY,
            "agent_gateway_config": {
                "agent_to_anywhere_config": {"agent_gateway": ".../agentGateways/kaiops-egress-gw"}
            },
            "staging_bucket": "gs://...",
        },
    )
"""

import os
from google.adk.agents import LlmAgent

# The working mesh uses gemini-3.6-flash; use the same proven model.
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

root_agent = LlmAgent(
    model=MODEL,
    name="kaiops_gateway_identity_agent",
    instruction=(
        "You are an isolation test agent for the KaiOps platform. "
        "Your purpose is to verify that Agent Identity (identity_type=AGENT_IDENTITY) "
        "and Agent Gateway (agent_gateway_config) are correctly bound at creation time. "
        "When deployed, reply concisely with a confirmation that your identity and "
        "gateway binding are active, and describe the governance context of your environment."
    ),
    tools=[],
)

__all__ = ["root_agent", "MODEL"]
