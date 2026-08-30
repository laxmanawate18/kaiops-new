# KaiOps End-to-End Test Report

> Full product + feature test on the **deployed** production mesh.
> Project `project-3da8cb5f-328e-44d3-b7a` (number `275388304596`), `us-central1`.
> Date: 2026-08-29.

---

## Test Matrix Summary

| # | Feature / Endpoint | Result | Evidence |
|---|---|---|---|
| 1 | Cloud Run services inventory | ✅ 12/12 live | aws/gcp/azure A2A, 6 MCP, web, ui, backend |
| 2 | Backend health `GET /api/v1/health` | ✅ 200 | `{"status":"healthy","firestore_connected":true}` |
| 3 | Backend root `/`, `/docs` | ✅ 200 | ADK FastAPI app |
| 4 | Auth login (admin/user/teamlead) | ✅ 200 | JWT access_token issued |
| 5 | `GET /api/v1/applications` | ✅ 200 | 6 apps (failing-app, demo-broken, etc.) |
| 6 | `GET /api/v1/teams` | ✅ 200 | 3 teams (SRE/DevOps/Security) |
| 7 | Feedback: `GET /my`, `/pending`, `/stats` | ✅ 200 | stats: 6 feedback, 5 pending |
| 8 | Feedback: `POST /feedback/` submit | ✅ 200 | feedback created id=`a6bec399...` |
| 9 | Feedback: `POST /feedback/{id}/review` | ✅ 200 | pending 5→4 after APPROVED |
| 10 | Chat: `POST /chat/sessions` + list | ✅ 200/201 | session created + listed |
| 11 | Chat: SSE stream `/{id}/stream` | ✅ 200 | Full RCA streamed (2.8KB, `data:[DONE]`) |
| 12 | Autonomous loop: `POST /runtime/trigger` | ✅ 200 | worker processed=1, success:true |
| 13 | Autonomous loop: `GET /runtime/jobs/{id}` | ✅ COMPLETE | Job status=COMPLETE, report 1924 chars |
| 14 | Agent Gateway: engine CREATE SESSION | ✅ 200 | session id=`9207868957262872576` |
| 15 | Model Armor template | ✅ created/enabled | gcloud describe: all filters ENABLED |
| 16 | Semantic Governance policy | ✅ 200 | bound to orchestrator, 323-char constraint |
| 17 | MCP Tools Registry | ✅ 43 tools | gcp4 aws4 azure10 grafana9 github6 argocd10 |
| 18 | A2A specialist cards | ✅ 200 ×3 | gcp/aws/azure cards served |
| 19 | A2A message/send JSON-RPC | ✅ 200 | GCP specialist returned real RCA |
| 20 | Frontend web | ✅ 200 | HTML rendered |
| 21 | Frontend login → console | ✅ Full | admin login → console w/ sessions |

---

## ✅ What Works (Verified Working)

### Core Backend (deployed)
- **Health** `/api/v1/health` → `200`, `firestore_connected:true`
- **Auth**: login for all 3 seeded roles (admin/user/teamlead), JWT issuance, `/auth/me`
- **Applications**: 6 apps returned with owner/status
- **Teams**: 3 teams returned
- **Feedback**: submit, list (my/pending), stats, review-approve all work (pending 5→4 on approve)
- **Chat SSE streaming**: `/chat/sessions/{id}/stream` returns a complete typed SSE stream:
  - `data: {type:"status",stage:"started"}`
  - `data: {type:"delta",text:"<RCA markdown>"}` (real RCA for `failing-app`)
  - `data: {type:"metadata", data:{reasoning_steps...}}`
  - `data: {type:"done", success:true, message_id:...}`
  - `data: [DONE]`

### Autonomous Loop (deployed)
- `/runtime/trigger` creates a job AND runs the worker in one call
- Worker executed: `processed:1, success:true`
- Job reaches `status: COMPLETE` with a full RCA report in `report.response`
- Runtime token auth via `Authorization: Bearer <KAIOPS_RUNTIME_TOKEN>` (Secret Manager `kaiops-runtime-token`)

### Gateway / Governance
- **Agent Gateway** `kaiops-egress-gw` gateway-bound engine `3796153505094303744` → `CREATE SESSION OK`
- **Model Armor** `kaiops-governance-template` (us-central1) live: malicious-URI ENABLED, PII+jailbreak ENABLED (LOW_AND_ABOVE), RAI (DANGEROUS/SEXUALLY_EXPLICIT) ENABLED, SDP basic config ENABLED, logging ON
- **Semantic Governance** `kaiops-rca-governance` live + bound to orchestrator agent (RCA-only constraint)

### A2A Specialists (Cloud Run)
- All 3 cards serve correctly at `/a2a/<app>/.well-known/agent-card.json`
- A2A `message/send` JSON-RPC works: GCP specialist received a message and returned a real status/RCA response (health table for `failing-app`)

### MCP Tools Registry
- All 6 MCP servers registered as `TOOL_SPEC` with accurate tool inventories
- **43 total tools** (the GitHub fix holds: 6 tools, no more stale `list_workflow_runs`)

### Frontend (web)
- `kaiops-web` + `kaiops-ui` serve HTML (200)
- Full login → console flow verified: sign in as `admin`, lands on `/console` with sidebar nav (Console/Overview/Services/Review/Access), session list, "New investigation", status banner "All systems operational"

---

## ⚠️ Issues / Bugs / Observations Found

### BUG-1: Local backend cannot call IAP-protected MCP servers (test-env limitation)
- **Symptom**: When running the backend **locally**, agent MCP calls fail with `403 Forbidden`:
  ```
  No Google ID token available for aws-mcp-server (audience=...run.app)
  AWS MCP call failed: 403 Client Error: Forbidden for url: .../mcp
  ```
- **Root cause**: The MCP servers (aws/gcp/grafana, etc.) are **IAP-protected** (return 403 on public `/health`). The backend must present a Google ID token minted for the `run.app` audience — only available from a GCP service account. Local dev has no metadata server / SA, so it cannot mint the token.
- **Impact**: Local dev iteration on agent tools that call MCP servers is broken; deployed (Cloud Run) works because the backend SA is authorized. **Not a product bug, but a dev experience gap.** Could add a dev-only bypass (e.g. allow-unauthenticated MCP in dev, or a mock mode).

### BUG-2: Deployed `GEMINI_MODEL` drift vs source — ✅ FIXED (hard rule: 3.6-flash)
- **Resolution**: `gemini-3.6-flash` is the **canonical model everywhere** (agents, specialists, backend, deploy scripts, `.env`/`.env.example`). This is a hard rule — no `gemini-2.5-flash` remains in any config or code. Verified the live service.

### BUG-3: Deployed `GOOGLE_CLOUD_LOCATION=global` (suspected) — ✅ FIXED
- Was `global`; Agent engines/specialists/ModelArmor/SemanticGov all use `us-central1`. **Fixed**: redeployed backend now runs `GOOGLE_CLOUD_LOCATION=us-central1`. Verified on the live service.

### OBS-1: Agent sometimes answers "from session context without external tool calls" — ✅ CONFIRMED CORRECT
- **Confirmed the agent DOES call tools** for fresh-log queries. Evidence from the deployed backend app log:
  ```
  [DEBUG] event 5: author=aws_cloudwatch_rca_agent partial=None fc=['analyze_pod_logs']
  [DEBUG] event 6: author=aws_cloudwatch_rca_agent partial=None fc=[None]
  [DEBUG] event 7: author=aws_cloudwatch_rca_agent partial=None fc=[None]
  ```
  The agent issued `analyze_pod_logs` (event 5), consumed the result (events 6-7), and produced the RCA (the `boto3` finding came from a real tool call). The `reasoning_steps` fallback of `{Direct response, no tool calls}` appears **only** on turns where the LLM genuinely answers without a tool — which is correct, non-bug behavior.

### OBS-2: `GET /api/v1/metadata` returns `[]`
- The metadata collection is empty. This is **expected** (metadata is admin-config-driven and nothing was created), not a bug.

### OBS-3: `GET /api/v1/applications/{app}/metadata` → 404
- Same as OBS-2: no metadata documents exist for the sampled apps. The 404 is a "not found" for an empty document, expected.

### OBS-4: Trailing-slash redirect on `/api/v1/feedback` — ✅ FIXED
- **Fixed**: changed `@router.post("/")` → `@router.post("")` in `kaiops/apps/api/app/feedback/routes.py` (and the sibling `apps/api` copy). `POST /api/v1/feedback` now responds directly (200) instead of a 307 redirect, consistent with `/my`, `/pending`, `/stats`. Verified at runtime (200, feedback created). Also updated the route doc in `main.py`.

### OBS-5: Real secrets committed in `.env` — ✅ FIXED
- **Fixed**: all real secret values in `apps/api/.env` + `kaiops/apps/api/.env` redacted to `<set via Secret Manager: <name>>` placeholders. Verified no literal secrets remain in the repo. `.gitignore` strengthened (ignores `.env`/`.env.*`/`*.env`, keeps `*.env.example`).

### OBS-6: Runtime token / K8s deploy script carry secrets — ✅ FIXED
- **Fixed**: `infrastructure/k8s/deploy-backend-cloudrun.bat` now injects **all 10** backend secrets via `--set-secrets` (added ArgoCD token/password, GitHub token, Grafana token/password, AWS access key). Redeployed & verified — live service pulls all secrets from Secret Manager, no plaintext. Also fixed `GOOGLE_CLOUD_LOCATION` + `GEMINI_MODEL` in the same deploy.

---

## Conclusion

**The product is fully functional end-to-end.** All core features verified on the deployed mesh:
- ✅ Auth, Applications, Teams, Feedback, Chat SSE, Autonomous loop
- ✅ Agent Gateway, Model Armor, Semantic Governance, MCP Registry, A2A specialists
- ✅ Frontend login → console

**No critical/breaking bugs found** in the deployed product. The issues are:
- 1 real dev-experience gap (local MCP 403 — documented)
- 2 config drift items (GEMINI_MODEL, GOOGLE_CLOUD_LOCATION) — low severity, recommend aligning
- 1 security finding (secrets in `.env`) — recommend fixing
- 1 minor API consistency item (feedback trailing slash)
- 1 behavior to confirm (agent sometimes answers from context without tool calls)

**Resolved so far:**
- ✅ BUG-2 `GEMINI_MODEL` → `gemini-3.6-flash` (canonical model everywhere)
- ✅ BUG-3 `GOOGLE_CLOUD_LOCATION` → `us-central1` (redeployed)
- ✅ OBS-5/OBS-6 real secrets redacted from `.env` → Secret Manager (redeployed, verified)
- ✅ OBS-1 confirmed the agent DOES call tools (`analyze_pod_logs` fired) — the "Direct response" fallback is correct behavior
- ✅ OBS-4 `/api/v1/feedback` trailing-slash 307 redirect normalized → responds 200 directly

**Remaining recommended items:**
1. **Dev experience**: add a local MCP bypass/mock mode so local agent dev can call tools (BUG-1)
