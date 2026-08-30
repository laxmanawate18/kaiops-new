# OVERNIGHT AUTOPILOT — KaiOps Hackathon Prep (Unattended Run)

You are an autonomous coding agent working ALONE overnight on the KaiOps repo.
The human is asleep and will NOT answer questions. The hackathon deadline is
Aug 31 2026, 5:00 PM PDT (Sep 1, 5:30 AM IST). Your job: complete the tasks
below in order, safely, and leave a full report. Nothing you do may break the
currently working, deployed system.

====================================================================
SECTION A — HARD RULES (violating any of these is total failure)
====================================================================

A1. FULLY AUTONOMOUS, SKIP-ON-BLOCK. If any step would require human
    approval, credentials you don't have, interactive input, a login, or a
    confirmation prompt: DO NOT attempt workarounds. Log it in the report as
    SKIPPED(reason) and move to the next task.

A2. OFFICIAL DOCS FIRST for Gemini Enterprise Agent Platform. Before ANY
    change related to Agent Engine, Agent Registry, Agent Identity, Agent
    Gateway, Memory Bank, Model Armor, Sessions, or ADK memory tools, you MUST
    first read the relevant official documentation (cloud.google.com,
    docs.cloud.google.com, or google.github.io/adk-docs) and record the exact
    URL(s) consulted in the commit message and the report. If you cannot
    access official docs, SKIP that task entirely — do not proceed from memory.

A3. NO CLOUD MUTATIONS. You must NOT run any command that modifies live
    Google Cloud resources: no gcloud deploy/create/update/delete/set, no
    kubectl apply/delete/scale, no terraform, no docker push. READ-ONLY cloud
    commands ARE allowed and encouraged for evidence-gathering (gcloud ...
    describe / list, gcloud logging read, gcloud run services list) — use them
    to verify README claims with real resource names/URLs. If a read-only
    command prompts for auth/input, rule A1 applies (skip). Deployment happens
    tomorrow, by the human, after review. If a task seems to need a deploy: do
    the code change, mark "NEEDS-DEPLOY" in the report, move on.

A3b. BACKUP GATE. Do NOT make any change until you confirm the backup exists:
    a file matching ../kaiops-backup-*.tar.gz AND a git branch
    backup-pre-autopilot (local or on origin). If missing, create it yourself
    with the Section A0 command below. No backup → no changes.

A4. PROTECTED PATHS — never delete, move, or rename:
    kaiops-gcp/  kaiops-aws/  kaiops-azure/   (Docker build contexts for the
    live Cloud Run A2A specialists; build-a2a-docker.ps1 and
    deploy-a2a-mesh.ps1 build FROM these)
    Also never delete kaiops/, apps/, mcp-servers/, agent-runtime/,
    infrastructure/.

A5. PROTECTED CONTRACT — never rename the "model_armor" metadata key in any
    Python file. apps/web/src/components/chat/ApprovalCard.tsx reads
    metadata.model_armor; renaming breaks the HITL approval UI.

A6. GIT DISCIPLINE. First action:
      git config user.name "kaiops-autopilot" (if unset)
      git config user.email "autopilot@local" (if unset)
      git checkout -b submission-prep
    Never touch main. One commit per task, message format:
    "[autopilot][T<N>] <summary>". Never force-push, never rebase. You MAY
    push ONLY the branches submission-prep and backup-pre-autopilot to origin
    (git push origin submission-prep) — do so after every 2-3 commits as an
    off-site backup. NEVER push main or any other branch. If a task's
    verification fails: git revert that task's commit(s), mark
    REVERTED(reason) in the report, continue.

A7. VERIFY EVERY TASK before committing:
    - For every changed .py file: python -m py_compile <file> must pass, and
      importing the module (with repo-appropriate sys.path) must not raise at
      import time.
    - If a fast test suite exists (pytest under 5 minutes), run it after code
      tasks T5 and T6; on new failures caused by your change → revert.
    - New runtime behavior MUST be gated behind an env var defaulting to OFF
      so the system behaves identically unless explicitly enabled.

A8. VERIFY-BEFORE-DELETE. Before deleting any file/folder, grep the ENTIRE
    repo for its name (scripts, Dockerfiles, workflows, imports, .ps1, .bat,
    .yaml). Any reference found → do not delete; log it.

A9. TIME-BOX: maximum 45 minutes per task. If exceeded, commit what is safe
    and verified (or revert), log PARTIAL, move on. Finishing the whole list
    imperfectly beats perfecting task 1.

A10. FACTS ONLY. Never invent env vars, file paths, features, or claims in
     documentation. Every claim in the README must be verifiable in this repo.
     If unsure whether something is true, write it as TODO-FOR-AUTHOR instead.

====================================================================
SECTION A0 — ONE-COMMAND BACKUP (run BEFORE anything else)
====================================================================
From the repo root, run exactly:

  TS=$(date +%Y%m%d-%H%M%S) && tar -czf ../kaiops-backup-$TS.tar.gz --exclude=node_modules --exclude=.git . && git bundle create ../kaiops-backup-$TS.bundle --all && git branch -f backup-pre-autopilot && (git push origin backup-pre-autopilot || echo "PUSH SKIPPED - offline backup still OK")

This produces THREE independent backups: (1) tar.gz of the full working tree
including uncommitted/untracked files, (2) a git bundle of all history, (3) a
remote branch. Verify all three exist (ls ../kaiops-backup-* ; git branch)
and record the filenames in the report. Restore instructions (for the human,
put in report): tar -xzf ../kaiops-backup-<TS>.tar.gz -C <fresh-dir>  OR
git clone ../kaiops-backup-<TS>.bundle.
(If running on Windows PowerShell instead of bash, the equivalent:
  $ts=Get-Date -Format yyyyMMdd-HHmmss; tar -czf ../kaiops-backup-$ts.tar.gz --exclude=node_modules --exclude=.git .; git bundle create ../kaiops-backup-$ts.bundle --all; git branch -f backup-pre-autopilot; git push origin backup-pre-autopilot )

====================================================================
SECTION B — TASKS (execute strictly in this order)
====================================================================

--- T0. RECON (no changes) ---
Read: deploy-backend.ps1, deploy-backend-v2.ps1,
.github/workflows/deploy-to-gke.yml, build-a2a-docker.ps1,
deploy-a2a-mesh.ps1, infrastructure/k8s/ scripts.
Determine and record in the report:
  (a) which tree the deployed backend builds from: apps/api OR kaiops/apps/api
  (b) which tree the frontend builds from
  (c) the full list of env vars actually read by that backend tree
      (grep for os.environ / os.getenv in it).
All later tasks use THE DETECTED BACKEND TREE wherever this document says
apps/api. If detection is ambiguous, assume apps/api and flag it.

--- T1. README.md FULL REWRITE (highest value; Stage One pass/fail gate) ---
Rewrite README.md completely. Verified facts you must use (do not invent
others): model gemini-3.6-flash via Vertex AI (env GEMINI_MODEL); framework
Google ADK (LlmAgent, sub_agents, FunctionTool, AdkApp); GCP services: Cloud
Run (backend + 3 A2A specialists + 6 MCP servers), GKE (+ CI/CD via
.github/workflows/deploy-to-gke.yml), Firestore (metadata, sessions,
agent_jobs), Vertex AI Agent Engine, Secret Manager, Cloud Build, Artifact
Registry, Cloud Logging/Monitoring, IAP. The data layer is FIRESTORE — remove
every MongoDB / Cosmos / SQLite claim.

Section order:
 1. Title + one-paragraph pitch. Framing: "Google Cloud is the governed
    control plane; AWS/Azure/GCP workloads are the managed estate the agent
    fleet investigates." Name the track: Fortified Enterprise Fleet.
 2. Image embed of docs/architecture-simple.svg (created in T7) + link to
    docs/architecture-system.png as "detailed live inventory".
 3. "Hackathon Requirements Compliance" table — each mandatory requirement
    (Gemini 3.5+ via Gemini API/Vertex AI; a Google agent framework; ≥1 GCP
    infra service) mapped to exact file paths in this repo.
 4. "Fortified Enterprise Fleet Pillars" table — Agent Registry, Agent
    Runtime, Memory Bank, Agent Identity, Agent Gateway, Model Armor,
    Observability — each with Status (✅ live / 🔶 partial / platform-limited)
    + file/doc link. Be honest: Model Armor = template
    kaiops-governance-template provisioned; the Agent Gateway exposes no
    model-armor binding field so enforcement is app-layer, plus an independent
    HITL gate on destructive tools. Agent Gateway = egress allowlist + IAP
    live; full A2A_AGENT registry routing is a documented platform limitation
    (link docs/GATEWAY_FINDING.md).
 5. "The Autonomous Loop": webhook → Firestore agent_jobs (PENDING) → worker
    claims via status-guarded compare-and-swap → RCA → Slack report with
    console deep-link → HITL approval → cloud-aware remediation (GKE/EKS/AKS).
    Link docs/WEBHOOK_TRIGGER.md.
 6. FOLDER STRUCTURE — describe the repo AS IT IS: apps/api (backend),
    apps/web (frontend), kaiops-gcp|aws|azure (A2A specialist container
    contexts), mcp-servers/ (6 IAM-private Cloud Run MCP servers),
    agent-runtime/ (Agent Engine wrapper), infrastructure/, docs/. If kaiops/
    exists, label it honestly (e.g. "governed-deployment variant, in
    progress"). Adjust to match T0 findings.
 7. Spin-up Instructions: (a) local run of backend + frontend with a table of
    ONLY the env vars found in T0(c); (b) GCP deploy path naming the actual
    scripts. No invented variables.
 8. "Findings & Learnings": 3–4 bullets; lead with the Agent Gateway SWP/mTLS
    egress finding and the A2A_AGENT registry limitation, linking
    docs/GATEWAY_FINDING.md and docs/FEATURE_PROGRESS.md.
 9. "Disclosure" section with a clearly marked TODO-FOR-AUTHOR placeholder for
    pre-Aug-3-2026 code / template disclosure (Google agent-starter-pack
    scaffolding is present). Do NOT write the disclosure content yourself.
Touch no other file in this task.

--- T2. SAFE HYGIENE DELETIONS ---
Apply rule A8 (grep first), then delete only if unreferenced:
  graphify-out/ ; apps/api/scratch/ ; Dockerfile.mcp-backup ;
  Dockerfile.mcp-backup2 ; docs/ARCHITECTURE.md (only if 0 bytes).
Add graphify-out/ and scratch/ to .gitignore. One commit per deletion.
Anything referenced → keep + log.

--- T3. MODEL ARMOR TRUTH-IN-NAMING (comments only) ---
In the detected backend tree's app/chat/agent_service.py (both occurrences)
and app/runtime/worker.py, add above each model_armor block:
  # NOTE: key name is a frontend contract (ApprovalCard.tsx). This block is
  # KaiOps' own HITL destructive-action gate. Google Cloud Model Armor is
  # provisioned separately as template `kaiops-governance-template`
  # (docs/FEATURE_PROGRESS.md §4); the Agent Gateway exposes no model-armor
  # binding field, so platform filters apply at the app/eval layer.
No logic changes. Rule A5 applies.

--- T4. FAILURE-TOLERANCE GUARD (env-gated, additive) ---
In the detected backend tree:
 1. app/runtime/worker.py: wrap the agent execution in
    asyncio.wait_for(..., timeout=int(os.environ.get(
    "KAIOPS_JOB_TIMEOUT_SECONDS", "900"))). On TimeoutError or Exception:
    update the job to STATUS_FAILED with the error string, log, never
    re-raise out of the worker loop.
 2. app/runtime/jobs.py: track an "attempts" field on claim; if attempts >
    int(os.environ.get("KAIOPS_JOB_MAX_ATTEMPTS", "2")) mark FAILED instead
    of re-claiming.
 3. Append a "Failure tolerance" paragraph to README section 5: CAS claim (no
    double-claim), job timeout, bounded attempts, FAILED terminal state.
Verify per A7. Any doubt → revert; this task is skippable.

--- T5. MEMORY BANK TOOL WIRING (env-gated OFF; rule A2 applies — read the
     official ADK memory docs first and record URLs) ---
In the detected backend tree's agents/sre_agent/agent.py, after the root
Agent is constructed, add:
  if os.environ.get("KAIOPS_ENABLE_MEMORY_TOOLS", "").lower() == "true":
      try:
          from google.adk.tools.load_memory_tool import LoadMemoryTool
          from google.adk.tools.preload_memory_tool import PreloadMemoryTool
          root_agent.tools = list(root_agent.tools or []) + [LoadMemoryTool(), PreloadMemoryTool()]
          logger.info("[MEMORY] Memory Bank tools attached")
      except Exception as e:
          logger.warning(f"[MEMORY] Memory tools unavailable: {e}")
(Mirror of kaiops/apps/api/agents/deploy_governed.py lines ~279-285.)
Default OFF → zero runtime change. Document the flag in README section 4 and
the spin-up env table.

--- T6. PROJECT-ID ENV SWEEP (backend tree + agent-runtime/ .py only) ---
Replace literal "project-3da8cb5f-328e-44d3-b7a" with
os.environ.get("GOOGLE_CLOUD_PROJECT", "project-3da8cb5f-328e-44d3-b7a")
— identical default = zero behavior change. Do NOT touch .ps1/.bat/.yaml/
docs/ or the kaiops-gcp|aws|azure trees. Verify per A7.

--- T7. SIMPLE ARCHITECTURE DIAGRAM (draft) ---
Create docs/architecture-simple.svg: ONE screen, ~10 boxes, left→right:
Vertex AI (gemini-3.6-flash) → KaiOps orchestrator [Agent Engine · Registry ·
Agent Identity · Gateway · Semantic Gov] → 3 A2A specialists (Cloud Run) →
6 MCP servers (Cloud Run, IAM-private) → managed estate (GKE/EKS/AKS); below:
Firestore (state/jobs) and the webhook → worker → Slack → HITL loop. Clean
hand-written SVG (rects, arrows, 12-16px sans-serif labels), legible at 1200px
wide. Spell it "Model Armor". Also create docs/architecture-simple.mmd with
the same content as Mermaid so the human can restyle. Embed the SVG in README
section 2.

--- T8. HUMAN-HANDOFF DRAFTS (new files only, no publishing) ---
 1. VIDEO_SCRIPT.md — 4:00 script with timestamps + on-screen directions:
    0:00-0:30 cold open (pod crash → unrequested Slack RCA); 0:30-2:00 the
    autonomous loop (trigger live, cut the wait, prove with worker/Cloud
    Logging logs); 2:00-3:10 governance on the real Cloud Console (Registry
    entry, AGENT_IDENTITY/SPIFFE, Semantic Governance text, Model Armor
    template — use the honest wording from T1§4); 3:10-4:00 Cloud Run /
    Agent Engine dashboards + one candid line on the gateway platform
    limitation. Add note at top: "Record in your own voice — judges
    explicitly said no AI narration."
 2. BLOG_DRAFT.md — 800-1200 words, "Building a governed multi-agent SRE
    fleet on the Gemini Enterprise Agent Platform", synthesized from
    docs/FEATURE_PROGRESS.md + docs/GATEWAY_FINDING.md + README. Must include
    the sentence: "I created this post for the purposes of entering the All
    Things Agentic Hackathon."
 3. SOCIAL_DRAFT.md — LinkedIn (~120 words) and X (~250 chars) variants, each
    containing #AllThingsAgenticHackathon and placeholders for repo/video
    links.

--- T9. FINAL REPORT (always do this, even if earlier tasks failed) ---
Write OVERNIGHT_REPORT.md at repo root:
  - Table: task | DONE / PARTIAL / SKIPPED(reason) / REVERTED(reason) | commit
  - T0 findings (deployed trees, env var list)
  - Every official-doc URL consulted (rule A2)
  - NEEDS-DEPLOY list and anything requiring human judgment
  - "MORNING CHECKLIST" for the human, in order: (1) read this report;
    (2) skim git log on submission-prep, then merge to main; (3) redeploy
    backend if NEEDS-DEPLOY is non-empty and re-verify the live demo;
    (4) fill the Disclosure TODO in README; (5) restyle/keep the diagram;
    (6) record the video from VIDEO_SCRIPT.md — own voice; (7) publish blog +
    social from drafts; (8) fill Devpost form (category: Fortified Enterprise
    Fleet; repo access to testing@devpost.com and cloudhackathons@google.com
    if private; video public on YouTube); (9) SUBMIT BY 1:30 AM IST Sep 1 —
    hours before the 5:30 AM IST deadline.
Final commit: "[autopilot][T9] overnight report". Then STOP. Do not idle-loop,
do not start new work, do not push anywhere.
