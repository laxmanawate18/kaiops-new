# KaiOps Feature Progress — Governance Bundle (2026-08-29)

> Status of the Gemini Enterprise Agent Platform feature push. All verified live on
> project `project-3da8cb5f-328e-44d3-b7a` (number `275388304596`), `us-central1`.

---

## ✅ EASY BUNDLE — COMPLETE

### 1. MCP Tools Registry
All 6 MCP servers registered as `TOOL_SPEC` in the global Agent Registry. **One real bug fixed:**

| Server | Tools | Notes |
|---|---|---|
| GCP | 4 | `get_pod_logs`, `get_cloud_monitoring`, `list_metrics`, `get_lb_logs` |
| AWS | 4 | `get_log_events`, `execute_log_insights`, `get_cloudwatch_metrics`, `get_alb_logs` |
| Azure | 10 | `list_pods`, `get_pod_logs`, `get_pod_events`, `get_pod_describe`, `list_cluster_nodes`, `restart_deployment`, `scale_deployment`, `get_pvc_status`, `aks_list_clusters`, `aks_get_cluster` |
| Grafana | 9 | alert rules, firing alerts, queries (Prometheus/Loki), dashboards, datasources, annotations |
| **GitHub** | **6** (was 1 stale) | Fixed: was only `list_workflow_runs` (nonexistent); now `search_repositories`, `get_repository_info`, `search_code`, `list_issues`, `get_user_repositories`, `get_latest_commit` |
| ArgoCD | 10 | applications, sync, history, resource tree, workload logs, events, repos |

**Total: 43 real MCP tools** now accurately enumerated in the registry.

### 2. Gateway route/allowlist cleanup
The registry + gateway allowlist were already clean (the bogus `240.0.0.2` endpoint was deleted earlier). Verified the full chain intact:
- `kaiops-egress-gw` → `kaiops-iap-request-authz-policy` (project-number target) → `kaiops-iap-request-authz-ext` (failOpen)
- Gateway-bound orchestrator `3796153505094303744` → `CREATE SESSION OK`

### 3. Gateway + specialist observability polish
Created `apps/api/runbooks/gateway-observability.md` — the definitive observability runbook with:
- The gateway decision-log query (the exact signal that unblocked the gateway)
- The authz policy/extension bind check (project-NUMBER requirement)
- The session probe (engine `:query`)
- Specialist telemetry (Cloud Trace) overview
- Registry/allowlist view
- Fast-triage matrix

---

## ✅ MEDIUM BUNDLE — COMPLETE

### 4. Model Armor 🛡️
Template `kaiops-governance-template` created (us-central1):

```json
{
  "filterConfig": {
    "maliciousUriFilterSettings": {"filterEnforcement": "ENABLED"},
    "piAndJailbreakFilterSettings": {"confidenceLevel": "LOW_AND_ABOVE", "filterEnforcement": "ENABLED"},
    "raiSettings": {"raiFilters": [
      {"confidenceLevel": "LOW_AND_ABOVE", "filterType": "DANGEROUS"},
      {"confidenceLevel": "LOW_AND_ABOVE", "filterType": "SEXUALLY_EXPLICIT"}
    ]},
    "sdpSettings": {"basicConfig": {"filterEnforcement": "ENABLED"}}
  },
  "templateMetadata": {"logSanitizeOperations": true, "logTemplateOperations": true}
}
```

**Integration note:** the Agent Gateway resource is google-managed with **no** model-armor binding field. Model Armor governs at the prediction/eval layer or app-level (the specialist apps ship `google-cloud-modelarmor` and can sanitize prompts/responses in-process).

### 5. Semantic Governance Policies ⚖️
Policy `kaiops-rca-governance` created and **bound to the gateway-bound orchestrator** `3796153505094303744`:

```json
{
  "agent": "projects/project-3da8cb5f-328e-44d3-b7a/locations/us-central1/agents/agentregistry-...-763e-c9a9f19b670e",
  "agentIdentity": "principal://agents.global.org-820797041517.system.id.goog/resources/aiplatform/projects/275388304596/locations/us-central1/reasoningEngines/3796153505094303744",
  "naturalLanguageConstraint": "The orchestrator agent must delegate Root Cause Analysis (RCA) to the cloud specialist A2A agents and synthesize their findings. It MUST NOT deploy, roll back, restart, scale, or otherwise mutate production infrastructure, and MUST NOT expose secrets or credentials. Any destructive action requires explicit human approval."
}
```

**Setup gotchas (documented):**
1. The Semantic Governance Policy **Engine** must be **ACTIVE** first — it was `INACTIVE`, so PATCHed `state=ACTIVE` (long-running op).
2. The policy must be in the **same region as the agent** (or the agent must be global).
3. The agent must have a valid **RuntimeIdentity** (the gateway-bound orchestrator's registry agent does).

---

## 🔴 ROUTE ALL A2A THROUGH THE GATEWAY — PARTIAL (boundary defined)

### What works now (gateway governs the egress)
Registered the 3 Cloud Run A2A specialist **destinations** in the gateway's `AGENT_TO_ANYWHERE` allowlist + granted IAP egressor:

| Endpoint | Cloud Run URL | IAP egressor granted to orchestrator |
|---|---|---|
| `kaiops-endpoint-gcp-a2a` (ID `28ae-b45807a7be6c`) | `kaiops-gcp-a2a-rkapewlsyq-uc.a.run.app` | ✅ |
| `kaiops-endpoint-aws-a2a` (ID `faa0-77aaf26d2086`) | `kaiops-aws-a2a-rkapewlsyq-uc.a.run.app` | ✅ |
| `kaiops-endpoint-azure-a2a` (ID `bbff-583489d8c20d`) | `kaiops-azure-a2a-rkapewlsyq-uc.a.run.app` | ✅ |

This means the **gateway now governably allowlists + authorizes every outbound A2A call** from the orchestrator to the specialists (AGENT_TO_ANYWHERE egress). The orchestrator still reaches the specialists by their Cloud Run URL (A2A shared token via `a2a_request_meta_provider`), but the gateway is authority on whether the destination is allowed.

### The remaining hard boundary
The fully **gateway-routed agent-to-agent** path — ADK `AgentRegistry.get_remote_a2a_agent()` — requires the destination agent to be registered with the **`A2A_AGENT`** protocol type. **This is NOT exposable via the public `services` registry API** for our Cloud Run A2A specialists:

- Probed `agent_spec.type` with `CUSTOM`, `A2A_AGENT`, `A2A`, `AGENT` → **all rejected** ("Invalid value at service.agent_spec.type").
- Only `NO_SPEC` / `TOOL_SPEC` are accepted for services.
- The `A2A_AGENT` protocol type exists in the ADK SDK enum but maps to an internal agent resource not reachable here.

This is a **platform constraint** (same finding as the earlier deep-dive), not a code bug. The delegated A2A still works end-to-end — it's just reached via the specialist's public card URL + shared token, with the **gateway authorizing the destination** rather than the ADK resolving an A2A_AGENT registry entry.

---

## Summary
| Item | Status |
|---|---|
| MCP Tools Registry | ✅ Complete (GitHub fixed, 43 tools) |
| Gateway cleanup | ✅ Complete (already clean) |
| Observability polish | ✅ Complete (runbook created) |
| Model Armor | ✅ Template created |
| Semantic Governance | ✅ Policy created + engine ACTIVE |
| Route A2A through gateway | 🔶 Partially (gateway allowlists destinations; A2A_AGENT path is platform-limited) |
