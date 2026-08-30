"""
Deploy the governed KaiOps mesh agents (identity + gateway).

Each engine is created with BOTH:
  - identity_type = AGENT_IDENTITY
  - agent_gateway_config bound to the EXISTING kaiops-egress-gw

This is the documented "new agent" path. The working *_noident mesh is not touched.

Usage:
   python deploy_governed.py <engine>   where engine in {orchestrator, gcp, aws, azure}
"""

import os
import sys
import json
import traceback

# Ensure the whole `agents` package is importable. We deploy from the package root.
PKG_ROOT = r"f:\Personal\AI-Project\kaiops_latest\apps\api\agents"
GOV_ROOT = os.path.join(PKG_ROOT, "governed")
sys.path.insert(0, PKG_ROOT)
sys.path.insert(0, GOV_ROOT)

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-3da8cb5f-328e-44d3-b7a")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = os.environ.get("KAI_OPS_STAGING_BUCKET", "gs://kaiops-gateway-identity-staging")
AGENT_GATEWAY = (
    f"projects/{PROJECT}/locations/{LOCATION}/agentGateways/kaiops-egress-gw"
)
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

# agent_name -> (display_name, import_path)
ENGINES = {
    "orchestrator": ("kaiops-orchestrator-gov", "agents.sre_agent.agent:root_agent"),
    "gcp": ("gcp-rca-specialist-gov", "agents.gcp_rca_agent:get_root_agent"),
    "aws": ("aws-rca-specialist-gov", "agents.aws_rca_agent:get_root_agent"),
    "azure": ("azure-rca-specialist-gov", "agents.azure_rca_agent:get_root_agent"),
}


def load_agent(import_path):
    module_name, attr = import_path.split(":")
    import importlib
    mod = importlib.import_module(module_name)
    val = getattr(mod, attr)
    # `get_root_agent` is a lazy factory function that returns an Agent object.
    # `root_agent` (orchestrator) is already an Agent object. Detect by callable.
    if callable(val):
        return val()
    return val


def main():
    engine = sys.argv[1] if len(sys.argv) > 1 else "orchestrator"
    if engine not in ENGINES:
        print(f"Unknown engine {engine}. Choose one of {list(ENGINES.keys())}")
        sys.exit(1)
    display_name, import_path = ENGINES[engine]

    import vertexai
    from vertexai import types
    from vertexai.agent_engines import AdkApp

    os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT
    os.environ["GOOGLE_CLOUD_LOCATION"] = LOCATION

    print(f"[governed] engine={engine} display={display_name} import={import_path}")
    print(f"[governed] model={MODEL} gateway={AGENT_GATEWAY} bucket={STAGING_BUCKET}")

    root_agent = load_agent(import_path)
    os.environ["GEMINI_MODEL"] = MODEL

    client = vertexai.Client(project=PROJECT, location=LOCATION, http_options=dict(api_version="v1beta1"))
    app = AdkApp(agent=root_agent)
    config = {
        "display_name": display_name,
        "identity_type": types.IdentityType.AGENT_IDENTITY,
        "agent_gateway_config": {"agent_to_anywhere_config": {"agent_gateway": AGENT_GATEWAY}},
        "requirements": ["google-cloud-aiplatform[adk,agent_engines]"],
        "staging_bucket": STAGING_BUCKET,
        "env_vars": {"GEMINI_MODEL": MODEL},
    }
    print(f"[governed] creating {display_name} with identity+gateway...")
    remote = client.agent_engines.create(agent=app, config=config)
    print(f"[governed] created. resource = {remote}")
    try:
        print(f"[governed] resource name = {remote.resource_name}")
    except Exception as e:
        print(f"[governed] (no resource_name attr: {e}); use API list/get for id")
    print("[governed] DONE")


if __name__ == "__main__":
    main()
