# KaiOps — Governed Multi-Cloud SRE Agent Fleet

**Google Cloud is the governed control plane; AWS, Azure and GCP workloads are the
managed estate the agent fleet investigates.**

KaiOps is an autonomous, human-in-the-loop **Site Reliability Engineering (SRE)
agent fleet** built on the **Gemini Enterprise Agent Platform** with **Google ADK**.
When a deployment crashes or degrades, KaiOps detects it end-to-end (ArgoCD health /
Kubernetes events), runs a **root-cause analysis** grounded in its RAG/runbook
knowledge base and **live Grafana + Prometheus** state, posts a **Slack report** with
a deep-link to a live console session, and — once an operator **approves** the
remediation (HITL gate) — executes the fix across **GKE, EKS or AKS** using the
target cloud's native APIs.

> **Track:** Fortified Enterprise Fleet · **Model:** `gemini-3.6-flash` (Gemini Enterprise Agent Platform)
> · **Framework:** Google ADK · **Entrant:** solo

---

## Problem Statement

Production outages are expensive and increasingly cross-cloud. An on-call engineer
has to triage an incident across **GCP, AWS and Azure**, pull logs and metrics from
three different providers, correlate them with **Grafana / Prometheus** alert state,
consult runbooks, and apply a fix — often at 2 AM, under pressure, alone.

Most of that work is mechanical. But existing agents are either single-cloud or
"answer-only" chatbots that can explain an incident and then stop, because nobody
wants to give a language model unsupervised write access to production.

**KaiOps is built for the engineer who has no SRE team behind them** — the developer
paged at 3 AM about a cluster they didn't build, with nobody to escalate to. It
*watches* the fleet, *investigates* autonomously, *explains* the root cause with
observability evidence, and *executes* a fix only after a human approves it — on any
of the three major clouds.

---

## The Autonomous Loop

```
webhook (ArgoCD Degraded / K8s crash)  →  Firestore agent_jobs[PENDING]
   →  worker claims job (status-guarded compare-and-swap)
   →  RCA: orchestrator plans, delegates to cloud specialist, grounds on runbooks
   →  Slack report + console deep-link
   →  HITL Approve / Reject
   →  cloud-aware remediation (GKE / EKS / AKS)  →  recovered
```

No human is in the loop until the approval gate. The loop is driven unattended by
two **Cloud Scheduler** jobs: `kaiops-argocd-poller` (every 1 min →
`/api/v1/runtime/argocd/check`) detects an ArgoCD Degraded app and enqueues a job,
then `kaiops-agent-worker` (every 1 min → `/api/v1/runtime/worker/run?max_jobs=1`)
claims it with a status-guarded compare-and-swap, runs the RCA, and posts the Slack
report. A `kaiops-crash-watcher` job additionally watches Kubernetes crash events.
The trigger, the job claim, the investigation, the cross-cloud evidence gathering
and the report all happen without a human on camera.

**Failure tolerance.** A worker claims a `PENDING` job through a status-guarded
compare-and-swap, so two workers can never execute the same job. Each run is bounded
by a job timeout (`KAIOPS_JOB_TIMEOUT_SECONDS`, default 900s) and a bounded number of
re-claims (`KAIOPS_JOB_MAX_ATTEMPTS`, default 2). On timeout or repeated failure the
job moves to the terminal `FAILED` state with the error recorded, rather than looping
or silently retrying forever.

---

## Architecture

![KaiOps architecture](docs/Kaiops.svg)

For the detailed live inventory of the deployed mesh — Cloud Run revisions, Agent
Engine reasoning engines, MCP servers, load balancer, certificates — see
[`docs/Full_Architecture.svg`](docs/Full_Architecture.svg) and
[`docs/kaiops-detailed-flow.svg`](docs/kaiops-detailed-flow.svg).

**Why this stack.** Cloud Run gives per-service scale-to-zero and IAM-private MCP
endpoints, so each tool group is an independently deployed, separately authorised
service instead of a function in one process. Firestore is the source of truth for
jobs, sessions and metadata, so a crashed worker can resume rather than lose an
in-flight investigation. Gemini Enterprise Agent Platform AI + ADK provide a real agent framework — planning,
sub-agent delegation, tool confirmation — instead of a prompt wrapper. Secret Manager
and the HITL gate keep destructive actions governed.

---

## Hackathon Requirements Compliance

| Mandatory requirement | Where it is met in this repo |
|---|---|
| **Gemini 3.5+** (Gemini API / Gemini Enterprise Agent Platform AI) | `GEMINI_MODEL=gemini-3.6-flash` served through Gemini Enterprise Agent Platform AI (`GOOGLE_GENAI_USE_Gemini Enterprise Agent PlatformAI=1`); wired in `apps/api/agents/*/agent.py` |
| **A Google agent framework** | Google ADK — `LlmAgent`, `sub_agents` delegation, `FunctionTool(require_confirmation=True)`, `AdkApp`; root agent in `apps/api/agents/sre_agent/agent.py` |
| **≥ 1 Google Cloud infrastructure service** | Cloud Run (backend, 3 A2A specialists, 6 MCP servers, frontend), GKE + CI/CD (`.github/workflows/deploy-to-gke.yml`), Firestore (metadata / ADK sessions / `agent_jobs`), **Gemini Enterprise Agent Platform AI RAG Engine** (RAG grounding), Secret Manager, Cloud Build, Artifact Registry, Cloud Logging & Monitoring, **Cloud Scheduler** (autonomous poller + worker + crash-watcher triggers), IAP |

---

## Fortified Enterprise Fleet Pillars

Status is reported honestly. Where the platform imposed a limit, that limit is
documented rather than papered over.

| Pillar | Status | Evidence |
|---|---|---|
| **Agent Registry** | 🔶 custom (not platform) | Cloud Run registry catalogue of 6 MCP servers + 43 `TOOL_SPEC` tools; the three A2A specialists are served as Cloud Run A2A endpoints. We use our own registry rather than the Gemini Enterprise Agent Platform agent registry — disclosed. |
| **Agent Runtime** | ✅ live | Firestore-backed job queue (`agent_jobs`) and autonomous worker loop (`POST /api/v1/runtime/worker/run`) with CAS claim, timeout and bounded attempts — `apps/api/app/runtime/`. (Custom ADK runtime on Cloud Run, not the managed Agent Engine.) |
| **Memory Bank** | 🔶 alternative approach | Durable recall is served by a **Gemini Enterprise Agent Platform AI RAG Engine** corpus (`kaiops-knowledge-us-east5`) over runbooks, past incidents and expert-approved feedback via the `search_knowledge` tool. Retrieval-grounded memory — not the managed Memory Bank service. |
| **Agent Identity** | 🔶 not live | Agent Identity (SPIFFE) / gateway-bound identity is exercised via Agent Engine tooling during setup; the demo agent runs on Cloud Run and does not attach a managed SPIFFE identity. |
| **Agent Gateway** | 🔶 partial (platform-limited) | Egress allowlist and IAP are **live**. Full `A2A_AGENT` registry routing is **not exposable** via the services registry; the orchestrator therefore reaches specialists by Cloud Run URL + Secret-Manager shared credential, gateway-enforced destination allowlisting. Full investigation: [`docs/GATEWAY_FINDING.md`](docs/GATEWAY_FINDING.md). |
| **Model Armor** | 🔶 partial (platform-limited) | Template `kaiops-governance-template` (prompt-injection / jailbreak / SDP filters) is provisioned and applied at the app layer (no gateway binding field). Complemented by an **independent HITL gate** on every destructive tool. See [`docs/FEATURE_PROGRESS.md`](docs/FEATURE_PROGRESS.md). |
| **Observability** | ✅ live | Cloud Logging / Monitoring queries in the GCP RCA agent, **per-app Grafana dashboards + Prometheus alerts auto-provisioned** on registration, and a gateway decision-log runbook: [`apps/api/runbooks/gateway-observability.md`](apps/api/runbooks/gateway-observability.md). (App-level observability; agent-lifecycle OTel/tracing not wired.) |

Also enforced across the fleet: **Semantic Governance Policy** (`kaiops-rca-governance`)
binds a natural-language operating constraint to the orchestrator's agent identity.

---

## Multi-Agent Design

A single root orchestrator plans and delegates; specialists own one cloud each.

- **Root orchestrator** (`sre_agent`) — an ADK `LlmAgent` on `gemini-3.6-flash`. Owns
  cross-cutting data tools (metadata, ArgoCD, GitHub, Grafana, RAG, Slack) and the
  three HITL-gated destructive tools.
- **Cloud specialists** (`gcp_rca_agent`, `aws_rca_agent`, `azure_rca_agent`) — passed
  as real `sub_agents`, which ADK auto-wraps as delegation targets. Deep, multi-step,
  provider-specific RCA lives here.
- **Two deliberate routing paths.** Shallow, single-shot lookups go through
  deterministic Python routers (`check_application_logs`, `check_ingress_logs`,
  `analyze_pod_logs`) that resolve the app's cloud from Firestore and dispatch
  directly — fast and non-negotiable. Deep investigation is **delegated** to the
  matching specialist sub-agent. The fast path exists so the model doesn't pay a
  delegation hop to answer "show me the last 50 error lines."
- **Tool isolation.** The 43 tools live behind **6 IAM-private Cloud Run MCP servers**
  (argocd / aws / azure / gcp / github / grafana), not as in-process functions. Each
  is independently deployed and separately authorised, so a compromised or misbehaving
  agent is bounded by IAM rather than by prompt instructions.

---

## Grafana Observability (built in, per app)

Every KaiOps-registered application gets an auto-provisioned **Grafana dashboard and
Prometheus alert rule** the moment it registers — zero-touch, via the ArgoCD poller.
The RCA agent then pulls **live** Grafana data (dashboard link, firing alert state,
CPU / memory / pod-restart metrics) and cites it in the report.

- Dashboard uid `kaiops-{app}` · alert rule uid `kaiops-{app}-alert`, foldered under `KaiOps`
- 10 registered apps each have a dashboard and an alert
- Implemented in `apps/api/agents/grafana_agent/provision.py`; surfaced through the
  Grafana MCP tools (`search_dashboards`, `list_alert_rules`, `query_prometheus`)

This is why the output reads like an SRE's diagnosis rather than a log summary.

---

## Cloud-Aware, Not Just GCP

The ArgoCD poller **auto-registers** each discovered app and **infers its cloud
provider** from the cluster destination (AKS → azure, EKS → aws, otherwise gcp), so
Azure and AWS apps get correct routing and Grafana provisioning with no manual
Firestore edits. The executor then applies remediation through each cloud's native API.

| Cloud | Applications (registered, auto-inferred from ArgoCD destination) |
|---|---|
| **GCP** | `kaiops-demo-app`, `gcp-todo-app`, `gcp-todo` |
| **Azure** | `kaiops-azure-demo` (verified end-to-end on AKS), `azure-to-do`, `Azure Ingress App` |
| **AWS** | `kaiops-aws-demo`, `failing-app`, `demo-broken`, `log-agent-eks` (live EKS operations are scaffold-only) |

See [`docs/WEBHOOK_TRIGGER.md`](docs/WEBHOOK_TRIGGER.md).

---

## Repository Structure

| Path | Purpose |
|---|---|
| `apps/api` | **Backend** — FastAPI + Google ADK. Build context for the deployed Cloud Run service (`infrastructure/docker/Dockerfile.backend`). |
| `apps/api/app` | FastAPI routers: `applications/`, `auth/`, `chat/` (sessions + HITL approve/reject), `runtime/` (job queue + worker), `slack/`, `feedback/`, `metadata/`. |
| `apps/api/agents` | The agent fleet: `sre_agent/` (root orchestrator), `gcp_rca_agent/`, `aws_rca_agent/`, `azure_rca_agent/`, `argocd_agent/`, `github_agent/`, `grafana_agent/`, `metadata_agent/`, `gateway_identity_agent/`, plus `k8s_crash_watcher.py` and `executor.py` (cloud-aware remediation). |
| `apps/web` | **Frontend** — React + Vite. Reasoning timeline and HITL approval card. Build context for `kaiops-web`. |
| `specialists/kaiops-gcp`<br>`specialists/kaiops-aws`<br>`specialists/kaiops-azure` | **A2A specialist container contexts** (Cloud Run). Three parallel deployments that share a common scaffold and diverge in their provider tooling — deployed separately, on purpose. |
| `mcp-servers/` | 6 IAM-private Cloud Run MCP servers (argocd / aws / azure / gcp / github / grafana) + `shared/mcp_proxy.py`. |
| `agent-runtime/` | Agent Engine wrapper (`AdkApp`) and A2A mesh glue. |
| `infrastructure/` | Dockerfiles, Cloud Build triggers, GKE / K8s manifests, load-balancer Terraform. |
| `docs/` | Architecture diagrams, gateway findings, feature progress, E2E test report. |

> **Note on the orchestrator context.** The pre-restructure scaffold that carries the
> already-deployed orchestrator reasoning engine is kept locally and intentionally
> **not** committed (see `.gitignore`). `deploy-a2a-mesh.ps1` deploys the three
> specialists from `specialists/`; the orchestrator step requires that local context
> and is skipped in a fresh clone. The orchestrator itself is already live on Agent
> Engine, so nothing in the demo path depends on redeploying it.

---

## Proven Working State

This is not a scaffold. It has been run end-to-end against the **deployed** mesh in
region `us-central1`.

| Proof | Result | Where |
|---|---|---|
| Cloud Run services inventory | ✅ 12/12 live | [`docs/E2E_TEST_REPORT.md`](docs/E2E_TEST_REPORT.md) |
| Health + auth + registered applications | ✅ 200, Firestore connected | [`docs/E2E_TEST_REPORT.md`](docs/E2E_TEST_REPORT.md) |
| Chat SSE stream — full RCA streamed | ✅ 200, `data:[DONE]` | [`docs/E2E_TEST_REPORT.md`](docs/E2E_TEST_REPORT.md) |
| Admin can open + chat in an autonomous runtime session | ✅ `GET /stream` + `GET /messages` on a `runtime-*` session return 200 | `apps/api/app/chat/routes.py` (`allow_runtime`) |
| Autonomous trigger → job `COMPLETE` | ✅ worker `processed:1, success:true` | [`docs/E2E_TEST_REPORT.md`](docs/E2E_TEST_REPORT.md) |
| Cloud Scheduler auto-trigger (poller + worker, no manual curl) | ✅ both jobs ENABLED, requests 200 | Cloud Scheduler (`kaiops-argocd-poller`, `kaiops-agent-worker`, `kaiops-crash-watcher`) |
| GCP + Azure RCA, cloud-aware routing | ✅ no misroute; live alert state + metrics | [`docs/E2E_TEST_REPORT.md`](docs/E2E_TEST_REPORT.md) |
| Slack `#incidents` per-app thread (Failed → RCA reply) | ✅ parent + threaded reply verified | [`docs/E2E_TEST_REPORT.md`](docs/E2E_TEST_REPORT.md) |
| HITL approve → tool runs; reject → tool blocked | ✅ both paths verified | [`docs/E2E_TEST_REPORT.md`](docs/E2E_TEST_REPORT.md) |
| Grafana dashboards + alerts for every app | ✅ one per registered app (10 apps → 10 dashboards + 10 alerts) | `apps/api/agents/grafana_agent/provision.py` |

---

## Spin-Up

### Configuration

The backend reads configuration from environment variables. Replace every
angle-bracket placeholder with your own values — no live endpoints or credentials are
published here.

| Env var | Value / example |
|---|---|
| `GOOGLE_CLOUD_PROJECT` | `<your-gcp-project-id>` |
| `GOOGLE_CLOUD_LOCATION` | `global` (model endpoint) |
| `GOOGLE_GENAI_USE_VERTEXAI` | `1` |
| `GEMINI_MODEL` | `gemini-3.6-flash` |
| `ENVIRONMENT` | `production` |
| `ALLOWED_ORIGINS` | `*` |
| `KAI_OPS_FRONTEND_URL` | `<your-frontend-url>` |
| `SEED_DEMO_USERS` | `false` |
| `AZURE_MOCK_MODE` | `false` |
| `AZURE_MCP_ENABLED` | `false` (backend default — the Azure npx MCP server is disabled; Azure RCA uses the native service-principal / KQL path) |
| `GKE_CLUSTER_NAME` / `GKE_CLUSTER_LOCATION` | `<cluster>` / `<zone>` |
| `AZURE_TENANT_ID` / `AZURE_CLIENT_ID` / `AZURE_SUBSCRIPTION_ID` | `<your Azure service principal>` |
| `AZURE_RESOURCE_GROUP` / `AZURE_AKS_CLUSTER_NAME` | `<rg>` / `<aks-cluster>` |
| `ARGOCD_URL` / `ARGOCD_USERNAME` | `<your-argocd-host>` / `<argocd-user>` |
| `GRAFANA_URL` / `GRAFANA_USERNAME` | `<your-grafana-host>` / `<grafana-user>` |
| `VERTEX_SEARCH_DATA_STORE_ID` | `<your RAG data store id>` |
| `KUBE_API_URL` / `KUBE_API_VERIFY_TLS` | `<cluster API endpoint>` / `true` |
| `AWS_REGION` / `AWS_CLUSTER_NAME` | `<region>` / `<eks-cluster>` |
| `AWS_CLOUDWATCH_LOG_GROUP` | `<your CloudWatch log group>` |
| `AWS_MCP_URL` | `<your AWS MCP server URL>` |
| `SLACK_CHANNEL` | `#incidents` |
| `KAIOPS_JOB_TIMEOUT_SECONDS` | `900` |
| `KAIOPS_JOB_MAX_ATTEMPTS` | `2` |
| `MCP_URL_ARGOCD` / `_AZURE` / `_GITHUB` / `_GRAFANA` / `_AWS` | `<your MCP server URLs>` |

**Secret-backed** — supplied through Secret Manager, never committed: `SECRET_KEY`,
`AZURE_CLIENT_SECRET`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`KAIOPS_RUNTIME_TOKEN`, `SLACK_WEBHOOK_URL`, `SLACK_BOT_TOKEN`,
`SLACK_SIGNING_SECRET`, `ARGOCD_AUTH_TOKEN`, `ARGOCD_PASSWORD`, `GITHUB_TOKEN`,
`GRAFANA_TOKEN`, `GRAFANA_PASSWORD`, `KAI_OPS_DEPLOY_WEBHOOK_TOKEN`,
`A2A_SHARED_TOKEN`.

### Run locally

```bash
# Backend — FastAPI + ADK
cd apps/api
pip install -r ../../requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend — React + Vite
cd apps/web
npm ci && npm run dev
```

Backend on `http://localhost:8000` (`/docs` for the OpenAPI UI), frontend on
`http://localhost:5173`.

### Deploy to Google Cloud

| Component | Command |
|---|---|
| Backend → Cloud Run | `infrastructure/k8s/deploy-backend-cloudrun.bat` (Cloud Build → Cloud Run) |
| Frontend → Cloud Run | `infrastructure/k8s/deploy-frontend-cloudrun.sh` |
| MCP servers → Cloud Run | `mcp-servers/Dockerfile.mcp` per server, IAM-private (no unauthenticated access) |
| A2A specialists → Cloud Run | `deploy-a2a-mesh.ps1` (builds from `specialists/kaiops-gcp|aws|azure`) |
| GKE workloads / CI-CD | `.github/workflows/deploy-to-gke.yml` |

Required APIs: `aiplatform`, `run`, `firestore`, `secretmanager`, `cloudbuild`,
`artifactregistry`, `logging`, `monitoring`, `discoveryengine`.

---

## Insights & Things I'm Proud Of

- **Cross-cloud autonomy that actually routes.** The poller infers AKS / EKS / GKE and
  routes both the RCA and the remediation to the right cloud with no human editing
  metadata. Most agents in this space are single-cloud.
- **Observability is first-class, not decorative.** Every registered app gets a
  Grafana dashboard and a Prometheus alert automatically, and the RCA cites live alert
  state and metrics. The report reads like a diagnosis, not a summary.
- **Destructive actions are genuinely governed.** `restart_pod`,
  `rollback_application` and `sync_application` sit behind an ADK
  `require_confirmation` gate with single-use tokens, session/user binding checks and
  cross-user tamper resistance. A model cannot mutate production without a human
  signing off.
- **Concurrency handled properly.** The status-guarded compare-and-swap job claim
  means horizontal worker scaling is safe by construction, not by luck.
- **Honest about platform limits.** The Agent Gateway mTLS/SWP behaviour, the missing
  Model Armor binding field, and the non-exposable `A2A_AGENT` registry type are all
  documented with evidence instead of glossed over.

---

## Findings & Learnings

- **Agent Gateway SWP / mTLS egress** is the single largest platform constraint we
  hit. The gateway `CONNECT` is validated at the Google-managed Secure Web Proxy
  layer; the decision log showed `clientCertChainVerified: false` with an invalid
  certificate validity window. Full investigation, including probing all four
  `agent_spec.type` values: [`docs/GATEWAY_FINDING.md`](docs/GATEWAY_FINDING.md).
- **`A2A_AGENT` registry routing is not exposable** through the services registry, so
  the orchestrator reaches specialists over Cloud Run URLs with a Secret-Manager-held
  shared credential plus gateway destination allowlisting. This is weaker than
  per-agent identity on the A2A hop and is called out rather than hidden.
- **Model Armor has no gateway binding field** on the managed gateway, so platform
  filtering runs at the app / eval layer alongside the independent HITL gate.
- **Managed Memory Bank is bound to the Agent Engine runtime**, not the Cloud Run
  demo path — which is why durable recall here is retrieval-grounded through Gemini Enterprise Agent Platform
  AI RAG Engine rather than the managed service.
- Full governance-bundle status: [`docs/FEATURE_PROGRESS.md`](docs/FEATURE_PROGRESS.md).

---

## Disclosure

Initial project scaffolding was generated from Google's **`agent-starter-pack`**
template (early project structure and boilerplate; Apache-2.0 headers retained).
Standard frameworks and libraries are used throughout — Google ADK, FastAPI, React,
Vite — and AI coding assistants were used during development, as permitted by the
hackathon rules.

All agent logic, the cloud-aware executor, the cross-cloud poller and
auto-registration, the Grafana provisioning, the Firestore job runtime, the governed
HITL flow, and the gateway / identity / governance integration work are original to
this repository.

---

**Author:** `laxmanawate18` · **Submission:** All Things Agentic Hackathon —
Fortified Enterprise Fleet · **August 2026**

*Note: "Model Armor" is the product name; the code key is `model_armor`, which is a
frontend contract with `ApprovalCard.tsx`.*
