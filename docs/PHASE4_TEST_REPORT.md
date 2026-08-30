# KaiOps Phase 4 — End-to-End Test Report (Live Deployed Backend)

> Tested against the **live Cloud Run backend**: `https://sre-agent-backend-rkapewlsyq-uc.a.run.app`
> Date: 2026-08-30
> Method: read-only / non-destructive where possible; auth-gated CRUD tested with real JWT.

---

## ✅ PASSED

| # | Feature / Endpoint | Result | Evidence |
|---|---|---|---|
| 1 | Backend root `/` | ✅ 200 | ADK FastAPI app banner |
| 2 | `/docs`, `/openapi.json` | ✅ 200 | 64 `/api/v1` routes enumerated |
| 3 | `/api/v1/health` | ✅ 200 | `{"status":"healthy","firestore_connected":true}` |
| 4 | Auth: admin/user/teamlead login | ✅ 200 | JWT access_token issued (all 3 roles) |
| 5 | Auth: bad password | ✅ 401 | rejected |
| 6 | Auth: no-token → protected route | ✅ 401 | rejected |
| 7 | Auth: `/auth/me` | ✅ 200 | returns user profile |
| 8 | `/applications` | ✅ 200 | 6 apps |
| 9 | `/teams` | ✅ 200 | 3 teams |
| 10 | `/teams/{id}` + members + agents + agent-types/priorities | ✅ 200 | all read OK |
| 11 | `/metadata` | ✅ 200 | `[]` (expected, empty) |
| 11 | `/feedback/stats` | ✅ 200 | 8 feedback, 6 pending |
| 12 | Chat: create/list/get session | ✅ 201/200 | session created, listed, fetched |
| 13 | Chat: stats | ✅ 200 | 67 sessions, 264 messages |
| 14 | Chat: stream agent turn | ✅ 200 | SSE events + `success: true` |
| 15 | Runtime auth: no/bad token | ✅ 401 | `Missing Authorization` / `Invalid runtime token` |
| 16 | Application search/owner/status/stats | ✅ 200 | all query endpoints OK |
| 17 | Feedback lifecycle POST+review APPROVED | ✅ 200 | total 8→9, approved 2→3 |
| 18 | Auth: refresh / logout / change-password-validation | ✅ 200/422 | refresh min token, logout OK, validation enforced |
| 19 | RBAC: admin-only endpoints | ✅ 403 user/teamlead vs 200 admin | `/auth/admin/users` enforced |

---

## ❌ BUGS / ISSUES FOUND

### BUG-P4-1: `POST /api/v1/feedback` (no trailing slash) returns 307 redirect — OBS-4 fix NOT deployed
- **Symptom**: `POST /api/v1/feedback` → **307**; `POST /api/v1/feedback/` → 422 (needs `conversation_id`).
- **Root cause**: The deployed Cloud Run backend's OpenAPI registers the route as **`/api/v1/feedback/`** (trailing slash), so the slug-less path redirects. The **source** `apps/api/app/feedback/routes.py` HAS `@router.post("")` (the OBS-4 fix) — but the **deployed service is running an older revision** that predates it.
- **Impact**: API consumers hitting `/feedback` silently 307-redirect (POST body can be lost on some clients). Not a hard break (client should follow), but inconsistent with the fix in source.
- **Fix**: **Redeploy the backend** so the current source (with `@router.post("")` + gemini-3.6-flash + us-central1) goes live.

### BUG-P4-2: Interactive chat agent did NOT ground on the runbook (RAG/search_knowledge not firing)
- **Symptom**: Asked "What does the runbook say about CrashLoopBackOff?" → agent replied *"I'm sorry, I was unable to access the runbook. The search for 'CrashLoopBackOff' failed."* Metadata: `reasoning_steps:[{title:"Direct response", description:"Answered from session context without external tool calls"}]`.
- **Root cause (confirmed)**: The **Cloud Run backend `apps/api`** uses `apps/api/agents/sre_agent/agent.py` which wires the **legacy `search_runbooks` (Vertex AI Search)** tool (`runbook_search.py`, line 338) + `search_past_incidents_tool`/`search_approved_feedback_tool` (line 348). It does **NOT** use the new unified `search_knowledge` RAG tool. The legacy Vertex AI Search call fails. The **governed engine** (`kaiops/apps/api/agents/sre_agent_gov/agent.py`) DOES use the working `search_knowledge` RAG (verified returns grounded answers).
- **Impact**: Interactive chat grounding is broken/inconsistent vs the governed mesh. Not a crash, but an agent-quality gap (can hallucinate / miss runbook context).
- **Fix**: Port the `search_knowledge` RAG tool (from `sre_agent_gov`) into `apps/api/agents/sre_agent/agent.py`, or point the interactive backend at the governed engine.

### BUG-P4-3: `GET /api/v1/teams/stats` → 404 "Team not found" (even for admin)
- Route exists in OpenAPI (`/api/v1/teams/stats` ['get']) but returns **404 "Team not found"** for admin AND user.
- Likely a route-ordering bug (the `/teams/{team_id}` path is matching `stats` as a team_id, OR the handler has no stats implementation).
- **Impact**: Minor — teams stats endpoint broken.

### OBS-P4-4: `/api/v1/feedback` no-slash 307 (see BUG-P4-1) + `/feedback/` requires full `FeedbackCreate` schema
- `POST /api/v1/feedback/` correctly validates `FeedbackCreate` (required: `conversation_id, message_id, user_message, ai_response, feedback_type`). My earlier 422 was an incomplete payload — **correct behavior**, not a bug.

### OBS-P4-3: `/api/v1/health` cold-start ~50s
- The health check took ~50s on first call. The Cloud Run backend appears to be `minInstances=0` (scale-to-zero). **Not a bug**, but flagging for UX — consider `minInstances=1` to avoid the latency spike.
### BUG-P4-5: `POST /api/v1/metadata` → 400 `NameError: name 'prometheus' is not defined`
- **Symptom**: Creating metadata returns `400 {"detail":"Error adding metadata: name 'prometheus' is not defined"}`.
- **Root cause (confirmed)**: `apps/api/app/metadata/service.py` line 163: `metadata_db.create_metadata(app_name, description, environment, team, github, argocd, grafana, prometheus)` references `prometheus`, but the method signature only defines `cost` (line 163 passes `prometheus` which was never defined). `NameError`.
- **Impact**: Metadata creation is **completely broken** — admin cannot add app metadata (blocks app onboarding/configuration).
- **Fix**: Replace the `prometheus` argument with `cost` (matches `create_metadata(**kwargs)`).
---

## ⚠️ TO VERIFY (needs service creds / deeper access)
- Autonomous loop `/runtime/trigger` end-to-end (needs `KAIOPS_RUNTIME_TOKEN` — I confirmed **auth is enforced (401)** but did not have the token to run the full job).
- Role-based authorization on admin-only endpoints (e.g. `/auth/admin/users`, team member management) — I validated login works for all roles but did not exhaustively test each RBAC boundary.

---

## Next steps
1. **Deploy current source** (fixes BUG-P4-1: feedback route + brings gemini-3.6-flash + us-central1 live).
2. **Investigate BUG-P4-2**: confirm whether the Cloud Run interactive agent should use `search_knowledge` RAG; if so, wire/enable it (it already works on the governed engine).
3. Re-run full E2E after deploy to confirm bug fixes.

---

## ✅ FIXES APPLIED (source, both apps/api + kaiops/apps/api twins) — 2026-08-30
- **BUG-P4-5 FIXED**: `metadata/service.py` — `prometheus` → `cost` (arg was undefined `NameError`).
- **BUG-P4-3 FIXED**: `auth/team_routes.py` — moved `@router.get("/stats")` to register BEFORE `@router.get("/{team_id}")` so `/teams/stats` isn't captured as a team_id (route-ordering).
- **BUG-P4-2 FIXED**: `agents/sre_agent/agent.py` — replaced legacy `search_runbooks` (Vertex AI Search) with the unified `search_knowledge` RAG tool (same as governed engine `sre_agent_gov`, verified working). Prompt updated to reference `search_knowledge`. Verified the agent imports cleanly with `search_knowledge` in tools.
- **BUG-P4-1 PENDING**: requires backend **redeploy** (the live Cloud Run runs an older revision). Will do on approval.

---

## ✅ NIGHTLY E2E RE-RUN — ALL BUGS CONFIRMED FIXED ON LIVE rev `sre-agent-backend-00064-vsz` (2026-08-30)

> Verified against the same live Cloud Run backend after **4 redeploys**. Every Phase 4 bug is now confirmed passing live.

| Bug | Result on live rev 00064 | Evidence |
|---|---|---|
| **P4-1** `POST /api/v1/feedback` (no slash) | ✅ **200** (was 307) | `{id, conversation_id, ...}` returned |
| **P4-2** Chat RAG grounding (`search_knowledge`) | ✅ **200** grounded answer | Agent cited `gs://project-3da8cb5f-328e-44d3-b7a-rag-staging/kaiops-runbooks/crashloop.md` with full diagnosis + remediation. Model resolved on **global** endpoint (was 404). |
| **P4-3** `GET /api/v1/teams/stats` | ✅ **200** (was 404) | `{total_users:8, total_teams:3, ...}` |
| **P4-5** `POST /api/v1/metadata` (create) | ✅ **200** (was 400/500) | `"Metadata created successfully"` |
| **P4-5b** `GET /api/v1/metadata/{app}` + `GET /api/v1/metadata` (read-back/list) | ✅ **200** (new bug found & fixed) | Full `ApplicationMetadata` model returned; was 500 `'dict' object has no attribute 'app_name'` |

### Live-verification summary of the 4 redeploys
| Revision | Purpose | Outcome |
|---|---|---|
| `00060` | Initial | P4-1/P4-3 failing |
| `00061-vl8` | 1st redeploy (feedback + teams order) | P4-1 ✅, P4-3 ✅, P4-5 still 400 (`create_metadata` arg count) |
| `00062-8dm` | 2nd redeploy (metadata create kwargs) | P4-5 create ✅; discovered **P4-5b** read-path 500 |
| `00063-mk9` | 3rd redeploy (metadata `_to_model` dict→model) | P4-5 create + P4-5b read-back/list ✅ |
| `00064-vsz` | 4th redeploy (model location `us-central1`→`global`) | **P4-2** chat grounding ✅ |

### Additional fix discovered & applied during verification — **P4-5b** (metadata read path)
- **Symptom**: `GET /api/v1/metadata` and `GET /api/v1/metadata/{app}` returned **500** `'dict' object has no attribute 'app_name'` (create worked after P4-5 fix, but reads were broken).
- **Root cause**: `metadata_db.get_metadata()` / `get_all_metadata()` / `search_metadata()` return flat **Firestore dicts**, but the routes access `.app_name` / `.github.enabled` as `ApplicationMetadata` attributes.
- **Fix**: Added `_coerce_dt()` + `_to_model()` helpers to `metadata/service.py` that convert a Firestore doc (preferring the stored `metadata_json`, overlaying top-level fields) into a proper `ApplicationMetadata` Pydantic model. Applied to `get_metadata`, `list_all_metadata`, and `search_metadata`. Mirrored in both `apps/api` and `kaiops/apps/api`.
- **Verified**: conversion logic unit-tested via Pylance snippet (PASS); read-back + list return 200 on live.

### Root cause confirmations
- **P4-2 (grounding)** was ultimately caused by the **model endpoint location**, not the tool: `gemini-3.6-flash` is only served on the **global** endpoint, but the backend was deployed with `GOOGLE_CLOUD_LOCATION=us-central1` → every model call 404'd so the agent could never run `search_knowledge`. Fix: set `GOOGLE_CLOUD_LOCATION=global` in `deploy-backend-cloudrun.bat` (decoupled from infra location via `gcp_location` pattern; RAG corpus stays pinned to `us-east5`). Backend SA confirmed to have `roles/aiplatform.user`.

### Next steps (open)
1. Clean up temp deploy artifacts (`_tmp_backend_redeploy.bat`, `backend_redeploy.log`).
2. Re-run full E2E suite to lock in results.
3. Commit + push fixes to git (git already initialized).
