# KaiOps Overnight Autopilot Report

**Run date:** 2026-08-31 · **Branch:** `submission-prep` · **Backup:**
`kaiops-backup-20260831-001719.tar.gz`, `kaiops-backup-20260831-001719.bundle`,
branch `backup-pre-autopilot`

Backup restore commands: `tar -xzf ../kaiops-backup-20260831-001719.tar.gz -C <fresh-dir>`
or `git clone ../kaiops-backup-20260831-001719.bundle`.

---

## Task summary

| Task | Status | Commit |
|---|---|---|
| T0 Recon | DONE | — (findings below) |
| T1 README.md rewrite | DONE | `1e86d80` |
| T2 Hygiene deletions | DONE (partial: `graphify-out/` kept) | `f109c21`, `f74d9af`, `808ddc5`, `9e4678b`, `8459e77` |
| T3 Model Armor truth-in-naming | DONE | `1c6cff0` |
| T4 Failure-tolerance guard | DONE | `11adef2` |
| T5 Memory Bank tool wiring | SKIPPED (A2: official ADK docs 404/unreachable) | — |
| T6 Project-ID env sweep | DONE (`apps/api` only) | `76cde41` |
| T7 Simple architecture diagram | DONE | `d72d345` |
| T8 Human-handoff drafts | DONE | `2fa9c5b` |
| T9 Final report | DONE | this file |

---

## T0 findings

- **(a) Deployed backend tree = `apps/api`.** `infrastructure/docker/Dockerfile.backend`
  does `COPY apps/api/requirements.txt .` and `COPY apps/api/ .`. Cloud Build
  config (`cloudbuild-backend-fix.yaml`) builds `-f infrastructure/docker/Dockerfile.backend`.
- **(b) Frontend tree = `apps/web`.** `Dockerfile.frontend` copies `apps/web/`.
- **(c) Live env vars** (sourced from `gcloud run services describe sre-agent-backend`,
  read-only). Plaintext: `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION=global`,
  `GOOGLE_GENAI_USE_VERTEXAI=1`, `GEMINI_MODEL=gemini-3.6-flash`,
  `ENVIRONMENT=production`, `ALLOWED_ORIGINS=*`, `KAI_OPS_FRONTEND_URL`,
  `SEED_DEMO_USERS=false`, `AZURE_MOCK_MODE=false`, `GKE_CLUSTER_NAME=gcp-demo-cluster`,
  `GKE_CLUSTER_LOCATION=us-central1-a`, `AZURE_TENANT_ID`, `AZURE_CLIENT_ID`,
  `AZURE_RESOURCE_GROUP=dontdelete`, `AZURE_LOG_ANALYTICS_WORKSPACE_ID`,
  `AZURE_WORKSPACE_NAME`, `AZURE_AKS_CLUSTER_NAME=my-demo-cluster`,
  `ARGOCD_URL=https://34.61.13.1`, `ARGOCD_USERNAME=admin`,
  `GRAFANA_URL=http://34.9.192.101`, `GRAFANA_USERNAME=admin`,
  `VERTEX_SEARCH_DATA_STORE_ID`, `KUBE_API_URL=https://34.42.202.43`,
  `KUBE_API_VERIFY_TLS=true`, `AWS_REGION=ap-southeast-2`,
  `AWS_CLUSTER_NAME=kaiops-demo-cluster`, `AWS_CLOUDWATCH_LOG_GROUP`,
  `AWS_MCP_URL`, `SLACK_CHANNEL=#incidents`, `MCP_URL_ARGOCD/AZURE/GITHUB/GRAFANA/AWS`.
  Secrets (Secret Manager): `SECRET_KEY`, `AZURE_CLIENT_SECRET`,
  `AWS_SECRET_ACCESS_KEY`, `KAIOPS_RUNTIME_TOKEN`, `SLACK_WEBHOOK_URL`,
  `ARGOCD_AUTH_TOKEN`, `ARGOCD_PASSWORD`, `GITHUB_TOKEN`, `GRAFANA_TOKEN`,
  `GRAFANA_PASSWORD`, `AWS_ACCESS_KEY_ID`, `KAI_OPS_DEPLOY_WEBHOOK_TOKEN`,
  `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`. Image:
  `us-central1-docker.pkg.dev/project-3da8cb5f-328e-44d3-b7a/mcp-servers/sre-agent-backend:latest`.

---

## Official-doc URLs consulted (rule A2)

The following were attempted for T5 (ADK memory tools). All redirected to
`adk.dev` and returned **404** — therefore, per A2's hard rule, T5 was **skipped**
(prohibited from proceeding from memory).

- https://google.github.io/adk-docs/tools/memory_tools/ → 404
- https://google.github.io/adk-docs/agent-engine/memory/ → 404
- https://adk.dev/tools/memory_tools/ → 404
- https://adk.dev/agent-engine/memory/ → 404
- https://adk.dev/resources/memory/ → 404
- https://google.github.io/adk-docs/resources/memory/ → 404

Note: an in-repo mirror of the intended memory-tool wiring (LoadMemoryTool +
PreloadMemoryTool) already exists and is verified in
`kaiops/apps/api/agents/deploy_governed.py` (~lines 279-285), but A2 forbids
adding it to the runtime tree without official-doc confirmation.

---

## NEEDS-DEPLOY (human action after review)

None of the changes in this report require redeploy to take effect at the source
level, but they live on `submission-prep`, not `main`. To make them live:

- Merge `submission-prep` → `main`.
- If the human wants the T4 failure-tolerance guard active in the running
  backend, redeploy `sre-agent-backend` (the guard is env-gated off-by-default
  via `KAIOPS_JOB_TIMEOUT_SECONDS` / `KAIOPS_JOB_MAX_ATTEMPTS`, so it does not
  change behavior unless explicitly enabled — safe either way).

## Items requiring human judgment

- **T2 `graphify-out/` KEPT** — referenced by `.github/copilot-instructions.md`
  (and the graphify skill). Deleting it would break the context-optimization
  contract, so per rule A8 it was retained. It was added to `.gitignore` so
  regenerated graphs won't be tracked.
- **T5 Memory Bank** — flagged for a follow-up once official ADK docs are
  reachable (or with the human's explicit confirmation to proceed from the
  in-repo mirror pattern).
- **README Disclosure TODO** — the template-based disclosure placeholder is
  intentionally left for the author (rule A10: do not write the disclosure
  content myself).

---

## MORNING CHECKLIST (for the human, in order)

1. **Read this report** (you are here).
2. **Review the git log on `submission-prep`**, then merge it into `main`.
3. If **NEEDS-DEPLOY** is non-empty (it only becomes necessary if you want the
   T4 guard live): redeploy the backend and re-verify the live demo.
4. **Fill the Disclosure TODO** in `README.md` (the "TODO-FOR-AUTHOR" block about
   pre-Aug-3-2026 code / `agent-starter-pack` scaffolding).
5. **Restyle or keep the diagram** — `docs/architecture-simple.svg` (renders
   correctly) + editable `docs/architecture-simple.mmd`.
6. **Record the video** from `VIDEO_SCRIPT.md` — in **your own voice** (judges
   said no AI narration).
7. **Publish** blog + social from `BLOG_DRAFT.md` / `SOCIAL_DRAFT.md`; add repo
   & video links.
8. **Fill the Devpost form** — category: **Fortified Enterprise Fleet**; if the
   repo is private, grant access to `testing@devpost.com` and
   `cloudhackathons@google.com`; make the video public on YouTube.
9. **SUBMIT BY 1:30 AM IST Sep 1** — hours before the 5:30 AM IST deadline.
