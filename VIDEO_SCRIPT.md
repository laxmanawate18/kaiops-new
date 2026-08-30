# KaiOps — 4-Minute Demo Video Script

> **Note to the presenter:** Record in your own voice. The judges explicitly said
> **no AI narration**. The times below are guidance; if you go over, keep the
> cold-open and the podium pieces, trim the middle.

**Total runtime:** ~4:00 · **Format:** screencast + screen-share of the live
KaiOps console and Google Cloud Console.

---

## 0:00–0:30 — Cold open (grab attention)
**On screen:** Live KaiOps console. The `[App_Name] ❌ Failed` Slack thread
(optional) or the console showing a degraded app.

**Voiceover (your own):**
> "A pod crashes at 2 AM. Nobody page's anybody. Within a minute, KaiOps has
> already pulled the logs, run a root cause analysis, and posted a report with
> an Approve button."

**On-screen:** cut to the Slack thread with the `✅ Approve` / `❌ Reject` buttons.

---

## 0:30–2:00 — The autonomous loop (the "wow")
**On screen:** KaiOps console → an incident session.

1. **Trigger it live** — show a deployment going Degraded (ArgoCD) or a crash
   event. Optional: call the webhook manually so the audience sees it fire.
2. **Cut the wait** — jump straight to the outcome (don't let RCA run on screen
   for minutes). Narrate: "KaiOps has already done this in the background."
3. **Prove it with logs** — show `gcloud logging read` or Cloud Logging filter
   for the worker runtime, pointing at the `agent_jobs[PENDING] → RUNNING →
   COMPLETE` transition, and the `search_knowledge` grounding call.

**On-screen:** clip of the worker/Cloud Logging lines scrolling; the Firestore
`agent_jobs` records.

---

## 2:00–3:10 — Governance on the real Cloud Console (podium)
**On screen:** Google Cloud Console → Vertex AI Agent Engine / Agent Registry.

Walk through each pillar honestly:
- **Agent Registry** — the entry, its `TOOL_SPEC` MCP tools (43 tools).
- **Agent Identity** — `AGENT_IDENTITY` / SPIFFE on the orchestrator.
- **Semantic Governance** — the `kaiops-rca-governance` policy bound to the
  orchestrator.
- **Model Armor** — template `kaiops-governance-template`. Use the honest
  wording: *"the gateway is google-managed and exposes no model-armor binding
  field, so enforcement is app-layer plus an independent HITL gate on
  destructive tools."*

**On-screen:** each console panel; highlight the HITL gate card in KaiOps.

---

## 3:10–4:00 — Dashboards + candid line
**On screen:** Cloud Run / Agent Engine dashboards (revisions, instances,
latency).

**Voiceover:**
> "This is the same governed control plane watching GKE, EKS and AKS."

**Candid closing line (important — judges value honesty):**
> "One honest caveat: the Agent Gateway is google-managed and does not yet
> expose full A2A_AGENT registry routing. We've documented that limitation and
> route specialists through Cloud Run URLs with a shared token instead — you can
> read the full finding in our docs."

**On-screen:** open `docs/GATEWAY_FINDING.md` at the limitation paragraph.

**End card:** repo URL + the track that won or the category.
