"""
Deploy governed KaiOps mesh engines (Agent Identity + Agent Gateway).

Creates NEW reasoning engines with:
  - identity_type = AGENT_IDENTITY
  - agent_gateway_config bound to the EXISTING kaiops-egress-gw
Exact same source/tools/prompts as the working *_noident mesh, but new IDs.
The working mesh is NOT touched.

Usage:
    python deploy_governed.py <engine> [--dry-run]
    engine in {orchestrator, gcp, aws, azure}

Writes progress to deploy_governed_<engine>.log. Designed to run as a detached
process (survives the snippet executor) via run_deploy_governed.py wrapper.
"""

import os
import sys
import json
import importlib
import traceback

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-3da8cb5f-328e-44d3-b7a")
# INFRA location: where the gateway/registry/session infra lives. ALWAYS us-central1.
# Decoupled from the MODEL location below so routing 3.6-flash via "global" never
# leaks into infra URLs (gateway binding, registry, session service).
INFRA_LOCATION = os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_LOCATION", "us-central1")
# MODEL location: the Gemini Enterprise endpoint that serves the model.
# gemini-3.6-flash is ONLY served on the GLOBAL (and multi-region us/eu) endpoint,
# so the container runtime must init vertexai with location="global".
MODEL_LOCATION = os.environ.get("KAI_OPS_MODEL_LOCATION", "global")
STAGING_BUCKET = os.environ.get("KAI_OPS_STAGING_BUCKET", "gs://kaiops-gateway-identity-staging")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
AGENT_GATEWAY = f"projects/{PROJECT}/locations/{INFRA_LOCATION}/agentGateways/kaiops-egress-gw"

# Where the `agents` package lives (parent of the package dir must be on sys.path).
# This deploy script lives at kaiops/apps/api/agents/, so the package parent is kaiops/apps/api.
AGENTS_PARENT = r"f:\Personal\AI-Project\kaiops_latest\kaiops\apps\api"

# engine -> (display_name, module:attr that yields the agent, extra env for specialists)
ENGINES = {
    "orchestrator": ("kaiops-orchestrator-gov", "agents.sre_agent_gov.agent:root_agent", {}),
    "gcp": ("gcp-rca-specialist-gov", "agents.gcp_rca_agent_gov:get_root_agent", {}),
    "aws": ("aws-rca-specialist-gov", "agents.aws_rca_agent_gov:get_root_agent", {}),
    "azure": ("azure-rca-specialist-gov", "agents.azure_rca_agent_gov.agent:root_agent", {}),
}

# The A2A base URLs pointing at the GOVERNED specialists (filled after their IDs are known).
# For initial deploy we pass placeholders that will be updated; here they come from env.
def a2a_base(engine):
    # e.g. GCP_A2A_BASE_URL points at the governed gcp engine endpoint.
    m = {
        "gcp": os.environ.get("GCP_A2A_BASE_URL"),
        "aws": os.environ.get("AWS_A2A_BASE_URL"),
        "azure": os.environ.get("AZURE_A2A_BASE_URL"),
    }.get(engine)
    return m or os.environ.get("A2A_BASE_URL")


def load_dotenv_env():
    """Read kaiops/apps/api/.env into a dict so provider creds reach the engines."""
    env = {}
    envfile = r"f:\Personal\AI-Project\kaiops_latest\kaiops\apps\api\.env"
    try:
        with open(envfile, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    except Exception as e:
        print(f"[warn] could not read .env: {e}")
    return env


def build_env(engine):
    envfile = load_dotenv_env()
    env = {
        "GEMINI_MODEL": MODEL,
        "GOOGLE_CLOUD_PROJECT": PROJECT,
        # MODEL endpoint location: global (where gemini-3.6-flash is served).
        # The agent infra (registry/session/A2A) must NOT use this — it uses
        # GOOGLE_CLOUD_AGENT_ENGINE_LOCATION (runtime-injected us-central1),
        # decoupled via the gcp_location helper.
        "GOOGLE_CLOUD_LOCATION": MODEL_LOCATION,
        "GOOGLE_GENAI_USE_VERTEXAI": "1",
        # Enable Agent Observability (Cloud Trace + Logging) so each A2A delegation
        # hop and agent invocation is traced/attributable across the governed mesh.
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        "AGENT_VERSION": "governed-2",
    }
    token = os.environ.get("A2A_SHARED_TOKEN", envfile.get("A2A_SHARED_TOKEN", "kaiops-shared-governed-token"))
    env["A2A_SHARED_TOKEN"] = token
    # Forward RAG Engine env (so the deployed orchestrator grounds via the unified
    # knowledge corpus; source defaults also apply, but make them explicit).
    # Location is us-east5 (serverless KNN corpus), NOT us-central1.
    for k in ("KAIOPS_RAG_CORPUS", "KAIOPS_RAG_LOCATION", "KAIOPS_RAG_TOP_K"):
        if os.environ.get(k):
            env[k] = os.environ[k]
        elif k in envfile and envfile[k]:
            env[k] = envfile[k]
    if "KAIOPS_RAG_CORPUS" not in env:
        env["KAIOPS_RAG_CORPUS"] = "projects/275388304596/locations/us-east5/ragCorpora/2305843009213693952"
    if "KAIOPS_RAG_LOCATION" not in env:
        env["KAIOPS_RAG_LOCATION"] = "us-east5"
    if "KAIOPS_RAG_TOP_K" not in env:
        env["KAIOPS_RAG_TOP_K"] = "4"
    if engine == "orchestrator":
        # FULL GOVERNED A2A: the orchestrator delegates to the 3 specialist A2A
        # servers deployed on Cloud Run (each serves a real A2A card + JSON-RPC).
        # The A2A wiring in sre_agent/_gov builds the card URL as
        #   {base}/a2a/<app_name>/.well-known/agent-card.json
        # from <CLOUD>_A2A_BASE_URL, so each must be the Cloud Run SERVICE BASE URL
        # (not /api, not the reasoning engine URL). This is the A2A-addressable path.
        CLOUD_RUN_A2A = {
            "GCP": "https://kaiops-gcp-a2a-rkapewlsyq-uc.a.run.app",
            "AWS": "https://kaiops-aws-a2a-rkapewlsyq-uc.a.run.app",
            "AZURE": "https://kaiops-azure-a2a-rkapewlsyq-uc.a.run.app",
        }
        for prefix, basevar in [
            ("GCP", "GCP_A2A_BASE_URL"),
            ("AWS", "AWS_A2A_BASE_URL"),
            ("AZURE", "AZURE_A2A_BASE_URL"),
        ]:
            env[basevar] = CLOUD_RUN_A2A[prefix]
        env["GOOGLE_CLOUD_PROJECT"] = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-3da8cb5f-328e-44d3-b7a")
        env["GOOGLE_CLOUD_LOCATION"] = MODEL_LOCATION
        # APP_URL (orchestrator's own A2A endpoint) — only set if the orchestrator ID is known.
        orch_id = os.environ.get("ORCH_ENGINE_ID")
        if orch_id:
            PN = os.environ.get("GOOGLE_CLOUD_PROJECT_NUMBER", "275388304596")
            A2A_BASE = f"https://us-central1-aiplatform.googleapis.com/reasoningEngines/v1/projects/{PN}/locations/us-central1/reasoningEngines"
            env["APP_URL"] = f"{A2A_BASE}/{orch_id}/api"
    # Merge ALL provider/credential vars from .env (GCP/AWS/Azure/ArgoCD/GitHub/Grafana/Mongo/Vertex)
    # EXCLUDE the runtime-reserved GOOGLE_CLOUD_AGENT_ENGINE_* prefix (Agent Engine
    # injects + owns it; sending it in env is rejected with FAILED_PRECONDITION).
    for k, v in envfile.items():
        if v and k.startswith(("GOOGLE_", "AWS_", "AZURE_", "GCP_", "ARGOCD_", "GRAFANA_", "GITHUB_", "VERTEX_", "MONGO_", "DB_", "SECRET_KEY", "KUBE", "K8S", "K8S_")) and not k.startswith("GOOGLE_CLOUD_AGENT_ENGINE_"):
            env[k] = v
    # Overlay any directly-passed os.environ creds (highest priority)
    for k, v in os.environ.items():
        if k.startswith(("GOOGLE_", "AWS_", "AZURE_", "GCP_", "ARGOCD_", "GRAFANA_", "GITHUB_", "VERTEX_", "MONGO_", "DB_", "SECRET_KEY", "KUBE", "K8S", "K8S_")) and v and not k.startswith("GOOGLE_CLOUD_AGENT_ENGINE_"):
            env[k] = v

    # Agent Runtime reserves these env var names for its own use; remove them.
    # NOTE: GOOGLE_API_USE_CLIENT_CERTIFICATE + GOOGLE_API_USE_MTLS_ENDPOINT are NOT
    # reserved — the agent NEEDS them to present its identity cert for mTLS to the
    # gateway. Set them explicitly (do not strip).
    # NOTE: GOOGLE_CLOUD_LOCATION is NOT popped — we DECOUPLE the MODEL endpoint
    # (global, where gemini-3.6-flash lives) from the INFRA region (us-central1,
    # runtime-injected via GOOGLE_CLOUD_AGENT_ENGINE_LOCATION for registry/session/A2A).
    # Popping GOOGLE_CLOUD_LOCATION would let the runtime re-inject us-central1 and
    # break the model call. GOOGLE_CLOUD_AGENT_ENGINE_LOCATION is NEVER set here (it is
    # a runtime-reserved prefix; deploying it is rejected with FAILED_PRECONDITION).
    RESERVED = {
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_CLOUD_PROJECT_NUMBER",
        "GOOGLE_CLOUD_QUOTA_PROJECT",
    }
    for k in RESERVED:
        env.pop(k, None)

    # Enable mTLS client certificate so the agent presents its identity cert to the
    # gateway (needed for gateway client-cert chain validation).
    env["GOOGLE_API_USE_CLIENT_CERTIFICATE"] = "true"
    env["GOOGLE_API_USE_MTLS_ENDPOINT"] = "true"

    # Engine-specific overrides (must match the proven *_noident working engines).
    if engine == "azure":
        # The azure agent with MCP enabled spawns an npx subprocess whose stdio
        # stream is not picklable by the cloud build -> force MCP off (same as
        # the working azure_rca_specialist_noident). It keeps its 3 RCA tools.
        env["AZURE_MCP_ENABLED"] = "false"
        env["AZURE_MOCK_MODE"] = envfile.get("AZURE_MOCK_MODE", "false")
    if engine in ("gcp", "aws", "azure"):
        env["MCP_ENABLED"] = envfile.get("MCP_ENABLED", "false")
    return env


def load_agent(import_path):
    mod_name, attr = import_path.split(":")
    mod = importlib.import_module(mod_name)
    val = getattr(mod, attr)
    return val() if callable(val) else val


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ENGINES:
        print(f"Usage: python deploy_governed.py [{'|'.join(ENGINES)}] [--dry-run]")
        sys.exit(1)
    engine = sys.argv[1]
    dry_run = "--dry-run" in sys.argv[2:]
    no_gateway = "--no-gateway" in sys.argv[2:]
    display_name, import_path, _ = ENGINES[engine]

    sys.path.insert(0, AGENTS_PARENT)
    os.environ["GEMINI_MODEL"] = MODEL
    os.environ["GOOGLE_CLOUD_PROJECT"] = PROJECT
    # MODEL endpoint location for the built agent (global serves 3.6-flash).
    # Infra resources use GOOGLE_CLOUD_AGENT_ENGINE_LOCATION (runtime-injected).
    os.environ["GOOGLE_CLOUD_LOCATION"] = MODEL_LOCATION

    # Run from the parent of `agents` so source_packages=["agents"] resolves and
    # the SDK uploads the whole agents/ package tree to the runtime container.
    os.chdir(AGENTS_PARENT)

    # Set engine-specific MCP env BEFORE loading the agent: the agents read these
    # from os.environ at import time (e.g. AZURE_MCP_ENABLED gates the unpicklable
    # npx MCPToolset). Mirror the proven *_noident engines.
    if engine == "azure":
        os.environ["AZURE_MCP_ENABLED"] = "false"
        os.environ["AZURE_MOCK_MODE"] = os.environ.get("AZURE_MOCK_MODE", "false")
    if engine in ("gcp", "aws", "azure"):
        os.environ["MCP_ENABLED"] = os.environ.get("MCP_ENABLED", "false")

    # For the orchestrator: set the A2A base URLs in os.environ BEFORE the agent is
    # built (the agent's RemoteA2aAgent wiring reads os.environ at import time).
    if engine == "orchestrator":
        # FULL GOVERNED A2A: delegate to the 3 Cloud Run specialist A2A servers.
        # Card URL = {base}/a2a/<app>/.well-known/agent-card.json, so <CLOUD>_A2A_BASE_URL
        # must be the Cloud Run SERVICE BASE URL (not /api, not a reasoning engine URL).
        CLOUD_RUN_A2A = {
            "GCP": "https://kaiops-gcp-a2a-rkapewlsyq-uc.a.run.app",
            "AWS": "https://kaiops-aws-a2a-rkapewlsyq-uc.a.run.app",
            "AZURE": "https://kaiops-azure-a2a-rkapewlsyq-uc.a.run.app",
        }
        for prefix, basevar in [
            ("GCP", "GCP_A2A_BASE_URL"),
            ("AWS", "AWS_A2A_BASE_URL"),
            ("AZURE", "AZURE_A2A_BASE_URL"),
        ]:
            os.environ[basevar] = CLOUD_RUN_A2A[prefix]
        os.environ["GOOGLE_CLOUD_PROJECT"] = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-3da8cb5f-328e-44d3-b7a")
        # Model endpoint = global (3.6-flash). Infra stays us-central1 (runtime).
        os.environ["GOOGLE_CLOUD_LOCATION"] = MODEL_LOCATION
        os.environ["A2A_SHARED_TOKEN"] = os.environ.get("A2A_SHARED_TOKEN", "localtok123")
        orch_id = os.environ.get("ORCH_ENGINE_ID")
        if orch_id:
            PN = os.environ.get("GOOGLE_CLOUD_PROJECT_NUMBER", "275388304596")
            A2A_BASE = f"https://us-central1-aiplatform.googleapis.com/reasoningEngines/v1/projects/{PN}/locations/us-central1/reasoningEngines"
            os.environ["APP_URL"] = f"{A2A_BASE}/{orch_id}/api"

    import vertexai
    from vertexai import types
    from vertexai.agent_engines import AdkApp

    print(f"[{engine}] display={display_name} import={import_path}")
    print(f"[{engine}] model={MODEL} gateway={AGENT_GATEWAY} bucket={STAGING_BUCKET}")

    root_agent = load_agent(import_path)
    print(f"[{engine}] loaded agent: {type(root_agent).__name__} name={getattr(root_agent, 'name', '?')}")

    client = vertexai.Client(project=PROJECT, location=INFRA_LOCATION, http_options=dict(api_version="v1beta1"))

    # Memory Bank (Agent Runtime auto-provisions a per-engine Memory Bank; the
    # runtime sets GOOGLE_CLOUD_AGENT_ENGINE_ID in the container). We hook
    # VertexAiMemoryBankService as the ADK memory service so the orchestrator can
    # persist + retrieve cross-session user memories. Only wired for the orchestrator.
    def _memory_builder():
        from google.adk.memory import VertexAiMemoryBankService
        engine_id = os.environ.get(
            "GOOGLE_CLOUD_AGENT_ENGINE_ID",
            os.environ.get("ORCH_ENGINE_ID", ""),
        )
        if not engine_id:
            # No dedicated ID known; Memory Bank still usable via the engine's own
            # default identity. Fall back to project+location only.
            return VertexAiMemoryBankService(project=PROJECT, location=INFRA_LOCATION)
        return VertexAiMemoryBankService(
            project=PROJECT, location=INFRA_LOCATION, agent_engine_id=engine_id
        )

    # Memory-enabled ADK app: hook the memory service builder + memory tools on the
    # agent so the orchestrator can generate/retrieve memories across sessions.
    if engine == "orchestrator":
        from google.adk.tools.load_memory_tool import LoadMemoryTool
        from google.adk.tools.preload_memory_tool import PreloadMemoryTool

        # Inject memory retrieval tools (idempotent: avoid duplicates by name).
        existing = {getattr(t, "name", "") for t in (root_agent.tools or [])}
        if not existing.intersection({"load_memory", "preload_memory"}):
            root_agent.tools = list(root_agent.tools or []) + [LoadMemoryTool(), PreloadMemoryTool()]

    app = AdkApp(
        agent=root_agent,
        memory_service_builder=_memory_builder if engine == "orchestrator" else None,
    )
    env = build_env(engine)
    if dry_run:
        print(f"[{engine}] DRY-RUN: env_vars ({len(env)}):")
        for k in sorted(env.keys()):
            v = env[k]
            show = v[:12] + "..." if len(str(v)) > 12 and "TOKEN" in k or any(x in k for x in ("SECRET", "PASSWORD", "KEY")) else v
            print(f"    {k} = {show}")
        print(f"[{engine}] DRY-RUN complete (no create).")
        return
    config = {
        "identity_type": types.IdentityType.AGENT_IDENTITY,
        # Upload the whole `agents` package alongside the serialized agent so
        # `import agents` resolves in the runtime container.
        "extra_packages": ["agents"],
        "requirements": [
            "google-cloud-aiplatform[adk,agent_engines]",
            # >=1.29.0 needed for AgentRegistry.get_remote_a2a_agent (gateway-routed
            # A2A). 1.29.0 still supports Runner(auto_create_session=True), so the
            # deploy path is unchanged. Keep pinned for reproducibility.
            "google-adk==1.29.0",
            "a2a-sdk>=0.3.4,<0.4.0",
            "fastapi",
            "uvicorn[standard]",
            "pydantic",
            "pydantic-settings",
            "python-multipart",
            "python-jose",
            "opik",
            "pymongo",
            "passlib",
            "pydantic[email]",
            "argon2-cffi",
            "mcp<2.0.0",
            "aiohttp>=3.9.0",
            "requests>=2.31.0",
            "cachetools>=5.0.0",
            "python-dotenv",
            "google-auth>=2.23.0",
            "google-api-core>=2.23.0,<2.35",
            "google-cloud-logging>=3.8.0",
            "google-cloud-monitoring>=2.16.0",
            "google-cloud-firestore>=2.13.0",
            "google-cloud-container>=2.40.0",
            "kubernetes>=29.0.0",
            "cloudpickle",
            "httpx",
            "google-genai",
        ],
        "staging_bucket": STAGING_BUCKET,
        "env_vars": env,
        # Warm-start + async throughput tuning (Agent Runtime caps max at 10).
        # min_instances=1 keeps a warm baseline (no cold start on first A2A delegation).
        # container_concurrency is a multiple of 9 so the ADK agent handles concurrent
        # A2A/message-send calls without queue spikes (avoid OOM by not going too high).
        "min_instances": 1,
        "max_instances": 5,
        "container_concurrency": 36,
    }
    if no_gateway:
        # HYBRID: keep gateway artifacts intact, but bind this agent identity-ONLY
        # (no egress agent_gateway_config) so it serves through the normal path.
        # Gateway governance (registry/IAM/authz/identity) still demonstrated.
        print(f"[{engine}] creating {display_name} IDENTITY-ONLY (no gateway binding) ...")
    else:
        config["agent_gateway_config"] = {
            "agent_to_anywhere_config": {"agent_gateway": AGENT_GATEWAY}
        }
        print(f"[{engine}] creating {display_name} with identity+gateway ...")
    remote = client.agent_engines.create(agent=app, config=config)
    print(f"[{engine}] created. resource={remote}")
    try:
        print(f"[{engine}] resource_name={remote.resource_name}")
    except Exception as e:
        print(f"[{engine}] (no resource_name attr {e}; see API list/get for ID)")
    print(f"[{engine}] DONE")


if __name__ == "__main__":
    main()
