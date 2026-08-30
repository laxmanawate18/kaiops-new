# KaiOps — Governed Multi-Cloud SRE Agent Fleet

**Google Cloud is the governed control plane; AWS, Azure and GCP workloads are the
managed estate the agent fleet investigates.**

KaiOps is an autonomous, human-in-the-loop **Site Reliability Engineering (SRE)
agent fleet** built on the **Gemini Enterprise Agent Platform** (Google ADK). When a
deployment crashes or degrades, KaiOps detects it end-to-to-end (ArgoCD health /
Kubernetes events), runs a **root-cause analysis (RCA)** grounded in its RAG/runbook
knowledge base, posts a **Slack report** with a deep-link to a live console session,
and — once an operator **approves** the remediation (HITL gate) — executes the fix
across **GKE, EKS or AKS** using the target cloud's native APIs.

> **Track:** Fortified Enterprise Fleet · **Model:** `gemini-3.6-flash` (Vertex AI)

---

## Architecture

![KaiOps architecture](docs/architecture-simple.svg)

For a detailed, live inventory of the deployed mesh (Cloud Run revisions, Agent
Engine orchestrators, MCP servers, load balancer, certificates) see
[`docs/architecture-system.png`](docs/architecture-system.png) (and
[`docs/architecture-live-inventory.png`](docs/architecture-live-inventory.png)).

---

## Hackathon Requirements Compliance

| Mandatory requirement | Where it is met in this repo |
|---|---|
| Gemini 3.5+ (Gemini API / Vertex AI) | `apps/api/agents/*` — model default `GEMINI_MODEL=gemini-3.6-flash` via Vertex AI (`GOOGLE_GENAI_USE_VERTEXAI=1`) |
| A Google agent framework | Google ADK (`LlmAgent`, `sub_agents`, `FunctionTool`, `AdkApp`) in `apps/api/agents/sre_agent/agent.py` |
| ≥ 1 GCP infrastructure service | Cloud Run (backend + 3 A2A specialists + 6 MCP servers), GKE + CI/CD (`deploy-to-gke.yml`), Firestore (metadata / sessions / `agent_jobs`), Vertex AI Agent Engine, Secret Manager, Cloud Build, Artifact Registry, Cloud Logging / Monitoring, IAP |

---

## Fortified Enterprise Fleet Pillars

| Pillar | Status | Evidence / link |
|---|---|---|
| **Agent Registry** | 🔶 partial | global Agent Registry with 6 `TOOL_SPEC` MCP servers (43 tools); A2A specialists registered as Cloud Run A2A endpoints |
| **Agent Runtime** | ✅ live | Firestore-backed job queue (`agent_jobs`) + autonomous worker loop (`/api/v1/runtime/worker/run`) |
| **Memory Bank** | ✅ live (RAG) | Vertex AI Search corpus (`kaiops-knowledge-us-east5`) + `search_knowledge` tool grounded on runbooks / past incidents / approved feedback |
| **Agent Identity** | ✅ live | Agent Engine `AGENT_IDENTITY` (SPIFFE) on the gateway-bound orchestrator |
| **Agent Gateway** | 🔶 partial | egress allowlist + IAP **live**; full `A2A_AGENT` registry routing is a documented platform limitation — see [`docs/GATEWAY_FINDING.md`](docs/GATEWAY_FINDING.md) |
| **Model Armor** | 🔶 partial (honest) | provisioned as template `kaiops-governance-template`; the Agent Gateway exposes **no** model-armor binding field, so enforcement is **app-layer**, plus an independent HITL gate on destructive tools |
| **Observability** | ✅ live | Cloud Logging / Monitoring queries in the GCP RCA agent; gateway decision-log runbook `runbooks/gateway-observability.md` |

---

## The Autonomous Loop

```
webhook (ArgoCD Degraded / K8s crash) → Firestore agent_jobs[PENDING]
→ worker claims (status-guarded CAS) → RCA (grounded by search_knowledge)
→ Slack report + console deep-link → HITL Approve/Reject
→ cloud-aware remediation (GKE / EKS / AKS) → recovered
```

See [`docs/WEBHOOK_TRIGGER.md`](docs/WEBHOOK_TRIGGER.md) for the full cloud-aware
trigger + remediation design, and [`docs/PHASE4_TEST_REPORT.md`](docs/PHASE4_TEST_REPORT.md)
for the test rationale.

**Failure tolerance:** the worker claims a `PENDING` job via a status-guarded
compare-and-swap so no two workers ever execute the same job (no double-claim).
Each agent run is bounded by a job timeout (`KAIOPS_JOB_TIMEOUT_SECONDS`, default
900s) and a bounded number of re-claims (`KAIOPS_JOB_MAX_ATTEMPTS`, default 2);
on timeout or a persistent failure the job is moved to the terminal `FAILED`
state rather than looping forever.

---

## Repository Structure (as it is)

| Path | Purpose |
|---|---|
| `apps/api` | **Backend** (FastAPI + Google ADK). Build context for the deployed Cloud Run service (`infrastructure/docker/Dockerfile.backend` → `COPY apps/api/`) |
| `apps/web` | **Frontend** (React + Vite). Build context for `kaiops-web` |
| `kaiops-gcp`, `kaiops-aws`, `kaiops-azure` | **A2A specialist** container contexts (Cloud Run). Each is a parallel deployment, NOT duplicates — do not merge/delete |
| `mcp-servers/` | 6 IAM-private Cloud Run MCP servers (argocd / aws / azure / gcp / github / grafana) |
| `agent-runtime/` | Agent Engine wrapper / A2A mesh glue |
| `infrastructure/` | Dockerfiles, Cloud Build triggers, GKE/K8s manifests, load balancer Terraform |
| `docs/` | Architecture, gateway findings, feature progress, test reports, architecture diagrams |
| `kaiops/` | Governed-deployment variant (Agent Engine runtime source, `deploy_governed.py`). In progress / parallel to `apps/api` |

---

## Spin-Up

### Local development (backend + frontend)

The backend reads its configuration from environment variables. The authoritative
list on the deployed service (Cloud Run) is below; for local use set the same keys.

| Env var | Default / example |
|---|---|
| `GOOGLE_CLOUD_PROJECT` | `project-3da8cb5f-328e-44d3-b7a` |
| `GOOGLE_CLOUD_LOCATION` | `global` (model endpoint) |
| `GOOGLE_GENAI_USE_VERTEXAI` | `1` |
| `GEMINI_MODEL` | `gemini-3.6-flash` |
| `ENVIRONMENT` | `production` |
| `ALLOWED_ORIGINS` | `*` |
| `KAI_OPS_FRONTEND_URL` | `https://kaiops-sre.searceinc.net` |
| `SEED_DEMO_USERS` | `false` |
| `AZURE_MOCK_MODE` | `false` |
| `GKE_CLUSTER_NAME` / `GKE_CLUSTER_LOCATION` | `gcp-demo-cluster` / `us-central1-a` |
| `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_SUBSCRIPTION_ID` | (your Azure service principal) |
| `AZURE_RESOURCE_GROUP` / `AZURE_AKS_CLUSTER_NAME` | `dontdelete` / `my-demo-cluster` |
| `ARGOCD_URL` / `ARGOCD_USERNAME` | `https://34.61.13.1` / `admin` |
| `GRAFANA_URL` / `GRAFANA_USERNAME` | `http://34.9.192.101` / `admin` |
| `VERTEX_SEARCH_DATA_STORE_ID` | (your RAG data store) |
| `KUBE_API_URL` / `KUBE_API_VERIFY_TLS` | cluster API endpoint / `true` |
| `AWS_REGION` / `AWS_CLUSTER_NAME` | `ap-southeast-2` / `kaiops-demo-cluster` |
| `AWS_CLOUDWATCH_LOG_GROUP` | (your CloudWatch group) |
| `AWS_MCP_URL` | (your AWS MCP server URL) |
| `SLACK_CHANNEL` | `#incidents` |
| `MCP_URL_ARGOCD/AZURE/GITHUB/GRAFANA/AWS` | (your MCP server URLs) |

Secret-backed (set via Secret Manager, never committed): `SECRET_KEY`,
`AZURE_CLIENT_SECRET`, `AWS_SECRET_ACCESS_KEY`, `KAIOPS_RUNTIME_TOKEN`,
`SLACK_WEBHOOK_URL`, `ARGOCD_AUTH_TOKEN`, `ARGOCD_PASSWORD`, `GITHUB_TOKEN`,
`GRAFANA_TOKEN`, `GRAFANA_PASSWORD`, `AWS_ACCESS_KEY_ID`,
`KAI_OPS_DEPLOY_WEBHOOK_TOKEN`, `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`.

**Run locally:**

```bash
# backend
cd apps/api && uvicorn app.main:app --host 0.0.0.0 --port 8000
# frontend
cd apps/web && npm ci && npm run dev
```

### Deploy to Google Cloud

- Backend: `infrastructure/k8s/deploy-backend-cloudrun.bat` (Cloud Build → Cloud Run)
- Frontend: `infrastructure/k8s/deploy-frontend-cloudrun.sh`
- A2A mesh: `deploy-a2a-mesh.ps1` (builds from `kaiops-gcp|aws|azure`)
- CI/CD for GKE: `.github/workflows/deploy-to-gke.yml`

---

## Findings & Learnings

- **Agent Gateway SWP/mTLS egress** is the single biggest platform constraint —
  the gateway CONNECT is validated at the Google-managed Secure Web Proxy layer.
  See [`docs/GATEWAY_FINDING.md`](docs/GATEWAY_FINDING.md).
- **A2A_AGENT registry routing** is not exposable via the services registry — the
  orchestrator reaches specialists via Cloud Run URL + `A2A_SHARED_TOKEN` (documented
  platform limitation).
- **Model Armor has no gateway binding field** (google-managed gateway) — enforcement
  is app-layer, complemented by the HITL destructive-action gate.
- See [`docs/FEATURE_PROGRESS.md`](docs/FEATURE_PROGRESS.md) for the full governance
  bundle status.

---

## Disclosure

> TODO-FOR-AUTHOR: pre-Aug-3-2026 code / template disclosure. Portions of this
> repository are scaffolded from Google's `agent-starter-pack` template. The author
> must fill in the exact scope, dates, and licensing notes before submission.

---

*Model Armor is spelled with a space in the submission materials; the code key is
`model_armor`, which is a frontend contract with `ApprovalCard.tsx`.*
