"""
KaiOps isolated Agent Identity + Agent Gateway deployment script.

Validates the documented "new agent" path from
docs.cloud.google.com/gemini-enterprise-agent-platform/scale/runtime/agent-gateway-runtime-deploy
which requires BOTH identity_type=AGENT_IDENTITY AND agent_gateway_config at
creation time.

Usage:
    python deploy_identity_gateway.py
"""

import json
import os
import sys
import time

import vertexai
from vertexai import types
from vertexai.agent_engines import AdkApp

from agent import root_agent, MODEL

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-3da8cb5f-328e-44d3-b7a")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
DISPLAY_NAME = "kaiops-gateway-identity-agent"
STAGING_BUCKET = os.environ.get(
    "KAI_OPS_STAGING_BUCKET", "gs://kaiops-gateway-identity-staging"
)
AGENT_GATEWAY = (
    f"projects/{PROJECT}/locations/{LOCATION}/agentGateways/kaiops-egress-gw"
)


def main() -> None:
    print(f"[deploy] project={PROJECT} location={LOCATION}")
    print(f"[deploy] model={MODEL}")
    print(f"[deploy] gateway={AGENT_GATEWAY}")
    print(f"[deploy] staging_bucket={STAGING_BUCKET}")

    # The documented Agent Identity + Agent Gateway path requires the v1beta1 api_version.
    client = vertexai.Client(
        project=PROJECT,
        location=LOCATION,
        http_options=dict(api_version="v1beta1"),
    )

    app = AdkApp(agent=root_agent)

    config = {
        "display_name": DISPLAY_NAME,
        # Both fields required for gateway-mediated governance (Model Armor /
        # Semantic Governance Policies eligibility).
        "identity_type": types.IdentityType.AGENT_IDENTITY,
        "agent_gateway_config": {
            "agent_to_anywhere_config": {"agent_gateway": AGENT_GATEWAY}
        },
        "requirements": ["google-cloud-aiplatform[adk,agent_engines]"],
        "staging_bucket": STAGING_BUCKET,
    }

    print(f"[deploy] creating agent engine with identity + gateway...")
    remote_app = client.agent_engines.create(agent=app, config=config)

    print(f"[deploy] created. resource: {remote_app}")
    print(f"[deploy] resource name: {remote_app.resource_name}")
    try:
        print(f"[deploy] effective identity: {remote_app.api_resource.spec.effective_identity}")
    except Exception as e:  # pragma: no cover
        print(f"[deploy] (effective_identity not read yet: {e})")

    print("[deploy] DONE")


if __name__ == "__main__":
    main()
