"""
Root SRE Agent - Orchestration Layer

Main orchestrator that coordinates all domain experts.
Loads all subagent tools, combines prompts, and provides intelligent routing.
"""

import os
import logging
logger = logging.getLogger(__name__)
import sys
from google.adk.agents import Agent, BaseAgent
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import all tools from subagents
from agents.metadata_agent.tools import (
    search_application_by_name,
    list_all_applications,
    query_mongodb
)

from agents.argocd_agent.tools import (
    get_application_status,
    get_deployment_history,
    sync_application,
    search_applications as search_argocd_applications,
    list_repositories,
    list_projects
)

from agents.github_agent.tools import (
    search_repositories,
    get_repository_info,
    search_code,
    list_issues,
    get_user_repositories,
    get_latest_commit
)

from agents.grafana_agent.tools import (
    search_dashboards,
    get_dashboard_summary,
    list_alert_rules
)

from agents.azure_rca_agent.tools import (
    check_application_logs as azure_check_application_logs,
    check_ingress_logs as azure_check_ingress_logs,
    analyze_pod_logs as azure_analyze_pod_logs
)

from agents.aws_rca_agent.tools import (
    check_application_logs as aws_check_application_logs,
    check_ingress_logs as aws_check_ingress_logs,
    analyze_pod_logs as aws_analyze_pod_logs
)

from agents.gcp_rca_agent.tools import (
    check_application_logs as gcp_check_application_logs,
    check_ingress_logs as gcp_check_ingress_logs,
    analyze_pod_logs as gcp_analyze_pod_logs
)

# Import all domain expertise prompts
from agents.sre_agent.prompt import root_instruction
from agents.metadata_agent.prompt import metadata_expertise
from agents.argocd_agent.prompt import argocd_expertise
from agents.github_agent.prompt import github_expertise
from agents.grafana_agent.prompt import grafana_expertise
from agents.azure_rca_agent.prompt import log_rca_expertise
from agents.aws_rca_agent.prompt import aws_rca_expertise
from agents.gcp_rca_agent.prompt import gcp_rca_expertise

# Get model configuration
gemini_model = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
model_temperature = float(os.environ.get("MODEL_TEMPERATURE", "0.7"))

# Cloud-provider-aware router functions
def get_cloud_provider_from_app(app_name: str) -> str:
    """Determine cloud provider for an application from metadata.
    
    Queries Firestore to get cloud_provider field.
    Returns: "azure", "aws", "gcp", or "gcp" (default)
    """
    try:
        from app.applications.database_firestore import application_db
        import logging
        
        logger = logging.getLogger(__name__)
        app = application_db.get_application_by_name(app_name)
        
        if app:
            cloud_provider = app.get("cloud_provider") or ""
            logger.info(f"[SEARCH] Cloud provider lookup: app='{app_name}' -> cloud_provider='{cloud_provider}'")
            
            if cloud_provider:
                provider_lower = str(cloud_provider).lower()
                if provider_lower in ["azure", "aws", "gcp"]:
                    logger.info(f" Routing to {provider_lower.upper()} RCA agent")
                    return provider_lower
        
        logger.warning(f" Cloud provider not found for {app_name}, defaulting to GCP")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f" Error determining cloud provider for {app_name}: {str(e)}", exc_info=True)
    
    return "gcp"


def check_application_logs(app_name: str, lines: int = 100, error_only: bool = False) -> dict:
    """
    Route to appropriate cloud provider's log checker based on application cloud provider.
    
    Supports:
    - Azure: Azure Log Analytics
    - AWS: CloudWatch Logs
    - GCP: Cloud Logging
    """
    import logging
    logger = logging.getLogger(__name__)
    
    cloud_provider = get_cloud_provider_from_app(app_name)
    logger.info(f"🔀 check_application_logs routing: app='{app_name}' -> cloud_provider='{cloud_provider}'")
    
    if cloud_provider == "aws":
        logger.info(f"📋 Calling AWS check_application_logs for {app_name}")
        return aws_check_application_logs(app_name, lines, error_only)
    elif cloud_provider == "gcp":
        logger.info(f"📋 Calling GCP check_application_logs for {app_name}")
        return gcp_check_application_logs(app_name, lines, error_only)
    else:  # Default to Azure
        logger.info(f"📋 Calling Azure check_application_logs for {app_name} (cloud_provider={cloud_provider})")
        return azure_check_application_logs(app_name, lines, error_only)

def check_ingress_logs(app_name: str, lines: int = 50, status_code_filter: str = "", min_response_time_ms: int = 0) -> dict:
    """
    Route to appropriate cloud provider's ingress log checker.
    
    Supports:
    - Azure: Application Gateway / Load Balancer logs
    - AWS: ALB/NLB logs
    - GCP: Cloud Load Balancing logs
    """
    import logging
    logger = logging.getLogger(__name__)
    
    cloud_provider = get_cloud_provider_from_app(app_name)
    logger.info(f"🔀 check_ingress_logs routing: app='{app_name}' -> cloud_provider='{cloud_provider}'")
    
    if cloud_provider == "aws":
        logger.info(f"📋 Calling AWS check_ingress_logs for {app_name}")
        return aws_check_ingress_logs(app_name, lines, status_code_filter, min_response_time_ms)
    elif cloud_provider == "gcp":
        logger.info(f"📋 Calling GCP check_ingress_logs for {app_name}")
        return gcp_check_ingress_logs(app_name, lines, status_code_filter, min_response_time_ms)
    else:  # Default to Azure
        logger.info(f"📋 Calling Azure check_ingress_logs for {app_name} (cloud_provider={cloud_provider})")
        return azure_check_ingress_logs(app_name, lines, status_code_filter, min_response_time_ms)

def analyze_pod_logs(app_name: str, include_events: bool = True, include_describe: bool = True) -> dict:
    """
    Route to appropriate cloud provider's pod analysis tool.
    
    Performs comprehensive RCA including:
    - Pod logs
    - Kubernetes events
    - Pod resource status and constraints
    
    Supports multi-deployment applications with health summaries.
    
    Supports:
    - Azure: AKS clusters
    - AWS: EKS clusters
    - GCP: GKE clusters
    """
    import logging
    logger = logging.getLogger(__name__)
    
    cloud_provider = get_cloud_provider_from_app(app_name)
    logger.info(f"🔀 analyze_pod_logs routing: app='{app_name}' -> cloud_provider='{cloud_provider}'")
    
    if cloud_provider == "aws":
        logger.info(f"📋 Calling AWS analyze_pod_logs for {app_name}")
        return aws_analyze_pod_logs(app_name, include_events, include_describe)
    elif cloud_provider == "gcp":
        logger.info(f"📋 Calling GCP analyze_pod_logs for {app_name}")
        return gcp_analyze_pod_logs(app_name, include_events, include_describe)
    else:  # Default to Azure
        logger.info(f"📋 Calling Azure analyze_pod_logs for {app_name} (cloud_provider={cloud_provider})")
        return azure_analyze_pod_logs(app_name, include_events, include_describe)

# Combine all prompts into comprehensive instruction
comprehensive_instruction = f"""{root_instruction}

<domain_expertise_metadata>
{metadata_expertise}
</domain_expertise_metadata>

<domain_expertise_argocd>
{argocd_expertise}
</domain_expertise_argocd>

<domain_expertise_github>
{github_expertise}
</domain_expertise_github>

<domain_expertise_grafana>
{grafana_expertise}
</domain_expertise_grafana>

<domain_expertise_log_rca>
{log_rca_expertise}

## Multi-Cloud RCA Support

This agent now supports Root Cause Analysis across multiple cloud providers:

### Azure RCA (Azure Log Analytics & AKS)
- Uses Azure Log Analytics for centralized logging
- Analyzes Azure Kubernetes Service (AKS) pods
- Queries Application Gateway and Azure Load Balancer logs

### AWS RCA (CloudWatch & EKS)
- Uses Amazon CloudWatch for log collection
- Analyzes Amazon Elastic Kubernetes Service (EKS) pods
- Queries AWS Application Load Balancer (ALB) and Network Load Balancer (NLB) logs

### GCP RCA (Cloud Logging & GKE)
- Uses Google Cloud Logging for centralized logging
- Analyzes Google Kubernetes Engine (GKE) pods
- Queries Google Cloud Load Balancing logs

### Automatic Cloud Provider Detection
When analyzing an application, the agent automatically:
1. Queries the metadata database for the application's cloud provider
2. Routes to the appropriate cloud-specific RCA tools
3. Uses cloud-native queries and interpreters
4. Returns cloud-specific analysis and recommendations

The `check_application_logs()`, `check_ingress_logs()`, and `analyze_pod_logs()` tools
automatically route to the correct cloud provider's implementation.

## Multi-Agent Delegation (use your specialist sub-agents)
You are the orchestrator. You have THREE specialist sub-agents available as tools,
each a domain expert you can delegate to when the investigation needs deep,
cloud-specific work:
- `aws_cloudwatch_rca_agent` — AWS CloudWatch logs, metrics, ALB/NLB access logs, EKS
- `gcp_cloud_logging_rca_agent` — Google Cloud Logging, Monitoring, Load Balancer logs, GKE
- `azure_log_rca_agent` — Azure Log Analytics (KQL), AKS, Application Gateway / Load Balancer logs

Rules:
1. For a quick status/metadata check, use your direct tools (metadata, ArgoCD, GitHub, Grafana).
2. For DEEP root cause analysis of a cloud workload (digging into logs, metrics,
   Kubernetes events across many lines), DELEGATE to the matching cloud sub-agent
   that you resolved from the application's `cloud_provider`.
3. Pass a focused, self-contained request to the sub-agent: the application name,
   the symptom, and what you want it to investigate.
4. The sub-agent returns a detailed finding; you synthesize the final RCA answer,
   propose remediation, and (if destructive) pause for human approval.

## Enterprise Grounding & Runbooks

This agent is equipped with a Vertex AI Search tool that connects to the enterprise SRE Runbook and Post-Mortem knowledge base.
When diagnosing an issue, ALWAYS search the knowledge base for related SOPs (Standard Operating Procedures) or post-mortems using the `vertex_ai_search` tool. Quote the exact steps and provide source citations to prevent hallucinations.

## Learn From Organizational History
For every RCA, first check organizational memory: call `search_past_incidents_tool` with key symptoms, and `search_approved_feedback_tool` for expert-validated guidance. Cite past incidents when relevant ('This resembles incident from <date>').

## Notify The Team
After completing a root cause analysis, use the `notify_slack` tool to post a concise summary (symptom, root cause, and remediation) to the team's incident channel (default '#incidents' or SLACK_CHANNEL). This turns the investigation into a real, visible action so the team is notified even while the agent works autonomously.
</domain_expertise_log_rca>

<domain_expertise_aws_rca>
{aws_rca_expertise}
</domain_expertise_aws_rca>

<domain_expertise_gcp_rca>
{gcp_rca_expertise}
</domain_expertise_gcp_rca>
"""

# Collect all tools
all_tools = [
    # Metadata tools (ALWAYS available - primary context source)
    search_application_by_name,
    list_all_applications,
    query_mongodb,
    
    # ArgoCD tools (sync_application & rollback_application are HITL-gated below)
    get_application_status,
    get_deployment_history,
    search_argocd_applications,
    list_repositories,
    list_projects,
    
    # GitHub tools
    search_repositories,
    get_repository_info,
    search_code,
    list_issues,
    get_user_repositories,
    get_latest_commit,
    
    # Grafana tools
    search_dashboards,
    get_dashboard_summary,
    list_alert_rules,
    
    # Cloud-provider-aware Log RCA tools (route based on app's cloud provider)
    check_application_logs,
    check_ingress_logs,
    analyze_pod_logs
]

# HITL / Destructive Action Tools
try:
    from google.adk.tools import FunctionTool
    from agents.gcp_rca_agent.tools import restart_pod
    from agents.argocd_agent.tools import rollback_application, sync_application
    
    # Wrap destructive actions with require_confirmation=True
    # The ADK runner will automatically pause execution and emit a ToolConfirmation event
    # which the frontend can intercept to show an Approve/Reject modal.
    restart_pod_tool = FunctionTool(func=restart_pod, require_confirmation=True)
    rollback_app_tool = FunctionTool(func=rollback_application, require_confirmation=True)
    sync_app_tool = FunctionTool(func=sync_application, require_confirmation=True)
    
    all_tools.extend([restart_pod_tool, rollback_app_tool, sync_app_tool])
    logger.info("✅ Added HITL confirmation tools (restart_pod, rollback_application, sync_application)")
except Exception as e:
    logger.error(f"❌ Failed to load HITL confirmation tools: {e}")

# Add Runbook Knowledge Search tool (real Vertex AI Search grounding)
from agents.sre_agent.runbook_search import search_runbooks as _search_runbooks

def search_runbooks(query: str) -> str:
    """Search enterprise SRE runbooks and post-mortem documentation for incident remediation steps."""
    return _search_runbooks(query)

all_tools.append(search_runbooks)
logger.info("✅ Added Runbook Knowledge Base tool (FunctionTool compatible with Gemini)")

# Historical learning tools: past incidents + expert-approved feedback
from agents.sre_agent.history_search import search_past_incidents, search_approved_feedback

def search_past_incidents_tool(query: str) -> str:
    """Search previous investigation sessions for similar past incidents and their resolutions."""
    return search_past_incidents(query)

def search_approved_feedback_tool(query: str) -> str:
    """Search expert-approved (APPROVED status) feedback for validated guidance on similar issues."""
    return search_approved_feedback(query)

all_tools.append(search_past_incidents_tool)
all_tools.append(search_approved_feedback_tool)
logger.info("✅ Added historical learning tools (past incidents + approved feedback)")

# Slack notification tool: the agent can post its RCA summary to a team channel,
# turning an autonomous investigation into a real, visible action.
from agents.sre_agent.slack_notify import notify_slack

all_tools.append(notify_slack)
logger.info("✅ Added Slack notification tool (notify_slack)")

# Root agent definition
class SREAgent(Agent):
    """Root SRE Agent - Orchestrates all domain tools for operational intelligence."""
    pass


# True multi-subagent delegation: the root agent delegates deep, cloud-specific
# RCA to the PER-CLOUD reasoning engines via A2A (Agent2Agent). Each is a
# RemoteA2aAgent (a BaseAgent) so ADK exposes it as an AgentTool named after
# the agent (e.g. azure_rca_specialist). The remote card URL + bearer token are
# resolved from env so the orchestrator is decoupled from the specialists.
# Data-lookup tools (metadata, ArgoCD, GitHub, Grafana) stay on the root.
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent

# A2A card well-known path. The exposing side (fast_api_app.attach_a2a_routes)
# uses the a2a-sdk constant `/.well-known/agent-card.json`.
_CARD_WELL_KNOWN = "/.well-known/agent-card.json"


def _a2a_card_url(base: str, app_name: str) -> str:
    """Build the A2A agent-card URL for a deployed reasoning engine.

    Agent Runtime exposes A2A at ``{APP_BASE}/a2a/<app.name>``; ADK serves the
    card (JSON) at ``{rpc_path}/.well-known/agent-card.json``.
    """
    return f"{base.rstrip('/')}/a2a/{app_name}{_CARD_WELL_KNOWN}"


def _get_shared_token() -> str:
    """Return the A2A bearer token shared with the specialist engines.

    Resolution order: ``A2A_SHARED_TOKEN`` env var, then Secret Manager
    (``A2A_SHARED_TOKEN_SECRET``), then a placeholder for local/dev.
    """
    from agents.a2a_auth import get_shared_a2a_token

    return get_shared_a2a_token()


def _build_remote_cloud_agents() -> list[BaseAgent]:
    """Build RemoteA2aAgent sub-agents for each cloud specialist engine.

    Each specialist's public A2A base URL is resolved from env in priority order:
      1. `<CLOUD>_A2A_BASE_URL`  (explicit, e.g. set after a specialist deploy)
      2. `A2A_BASE_URL`          (shared base if all specialists on one host)
    If none is set, the agent is skipped (fallback: log a warning). This keeps
    the orchestrator deployable before the specialists exist.

    A2A auth is OPT-IN token-based: the shared bearer token (A2A_SHARED_TOKEN,
    injected from Secret Manager at deploy) is attached to both the agent-card
    fetch and every A2A message send via the request interceptors built by
    RemoteA2aAgent from `auth_scheme`/`auth_credential`.
    """
    from google.adk.auth.auth_credential import (
        AuthCredential,
        AuthCredentialTypes,
        HttpAuth,
        HttpCredentials,
    )
    from fastapi.openapi.models import HTTPBearer

    scheme = HTTPBearer()
    token = _get_shared_token()
    credential = AuthCredential(
        auth_type=AuthCredentialTypes.HTTP,
        http=HttpAuth(scheme="bearer", credentials=HttpCredentials(token=token)),
    )

    specs = [
        ("azure", "azure_rca_specialist", "Azure RCA: Log Analytics, AKS, App Gateway"),
        ("aws", "aws_cloudwatch_rca_specialist", "AWS RCA: CloudWatch, EKS, ALB/NLB"),
        ("gcp", "gcp_cloud_logging_rca_specialist", "GCP RCA: Cloud Logging, GKE, LB"),
    ]

    remote_agents: list[BaseAgent] = []
    for prefix, app_name, desc in specs:
        base = os.environ.get(f"{prefix.upper()}_A2A_BASE_URL") or os.environ.get("A2A_BASE_URL")
        if not base:
            logger.warning(
                "No A2A base URL for %s (set %s_A2A_BASE_URL or A2A_BASE_URL); "
                "skipping remote sub-agent %s",
                prefix, prefix.upper(), app_name,
            )
            continue
        remote_agents.append(
            RemoteA2aAgent(
                name=app_name,
                description=desc,
                agent_card=_a2a_card_url(base, app_name),
                auth_scheme=scheme,
                auth_credential=credential,
                credential_key=f"a2a:{prefix}",
            )
        )
        logger.info("Wired remote A2A sub-agent %s at %s", app_name, _a2a_card_url(base, app_name))

    return remote_agents


sub_agent_refs = _build_remote_cloud_agents()

root_agent = SREAgent(
    name="sre_agent",
    description="KaiOPS Root SRE Agent - Orchestrates metadata management, deployment status, source code, and observability across all domains",
    instruction=comprehensive_instruction,
    model=gemini_model,
    generate_content_config={"temperature": model_temperature},
    tools=all_tools,
    sub_agents=sub_agent_refs,
)

__all__ = ["root_agent", "all_tools"]
