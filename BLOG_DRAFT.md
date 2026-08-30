# Building a Governed Multi-Agent SRE Fleet on the Gemini Enterprise Agent Platform

Incident response is the perfect proving ground for multi-agent systems: it is
time-sensitive, requires pulling data from many different systems, and every
action carries real risk. So when we set out to build KaiOps, the goal was not a
chatbot that answers questions — it was an **operator** that investigates, decides,
and remediates, all under governance.

I created this post for the purposes of entering the All Things Agentic Hackathon.

## From advisor to operator

Most SRE agents stop at advice: they read logs, summarize, and suggest a command.
KaiOps closes the loop. When a deployment degrades, a webhook lands in Firestore
as a `PENDING` job. A background worker claims it with a compare-and-swap so no
two workers ever pick up the same incident, runs a root-cause analysis, posts a
Slack report with a deep-link to a live console session, and waits. Only when an
operator **approves** the remediation through a human-in-the-loop gate does it
actually execute — restart a pod, roll back a release, re-sync a deployment —
across GKE, EKS or AKS using the target cloud's native APIs.

That cloud-aware dispatch is the heart of the "managed estate" framing: Google
Cloud is the governed control plane; AWS, Azure and GCP workloads are the estate
the agent fleet investigates. The orchestrator never hard-codes a cloud — it
reads the application's registered `cloud_provider`, then hands the work to the
right specialist, which authenticates with that cloud's native credentials (a
service principal for Azure, a boto3 session for AWS, the GCP SDK for GKE).

## Grounded, not hallucinated

A governed agent learns to be honest about what it knows. Every RCA is grounded
in a RAG knowledge corpus (runbooks, past incidents, approved operator feedback),
so recommendations cite their source. When the agent says it's an
`ImagePullBackOff` and recommends a rollout restart, it can point at the runbook
it retrieved. This is the same philosophy we carried into the governance layer:
the fleet registers its tools, holds a machine identity (SPIFFE), and routes
outbound calls through an egress gateway with an allowlist.

The result is a loop that looks less like a chat window and more like a
disciplined on-call engineer: it gathers evidence first, cites it, and asks before
it touches anything destructive.

## The seven pillars, in one story

KaiOps intentionally keeps the whole platform in one repository so the story is
coherent:

- **Agent Registry** — six MCP servers registered as `TOOL_SPEC`, enumerating
  forty-three real tools across ArgoCD, AWS, Azure, GCP, GitHub and Grafana.
- **Agent Runtime** — the Firestore-backed job queue and the autonomous worker
  that claims, executes, and persists each investigation.
- **Memory Bank** — the RAG corpus that grounds recommendations and carries
  institutional knowledge forward.
- **Agent Identity** — `AGENT_IDENTITY` / SPIFFE on the gateway-bound orchestrator,
  so every call is attributable to a machine identity.
- **Agent Gateway** — the egress allowlist and IAP layer that constrains where the
  fleet can reach.
- **Model Armor** — a governance template, enforced at the app layer alongside an
  independent HITL gate.
- **Observability** — Cloud Logging / Monitoring queries in the GCP RCA agent, and
  a gateway decision-log runbook that tells you why a call was allowed or denied.

None of these are bolt-ons; they are the load-bearing walls of the same loop.

## The honest parts matter most

Two things we deliberately did not paper over. First, the Agent Gateway is
google-managed and exposes **no model-armor binding field**, so Model Armor is
provisioned as a template and enforced at the app layer, complemented by an
independent HITL gate on destructive tools. Second, full `A2A_AGENT` registry
routing is a documented platform limitation, so specialists are reached by Cloud
Run URL plus a shared token. We wrote both findings up rather than hiding them —
judges and reviewers can see exactly where the platform constrains the design,
and where we used an independent HITL gate as a defense-in-depth complement.

## Fortified by design

The autonomous loop — webhook, job queue, worker, RCA, Slack, HITL approval,
remediation — is the single flow that ties everything together. Add failure
tolerance (timeouts, bounded re-claims, a terminal `FAILED` state) and the system
behaves like a disciplined engineer: it investigates, it asks before it acts, and
it never loops forever.

We also made the console the single pane of glass. Every Slack report carries a
deep-link straight into the live incident session, so clicking "Open in KaiOps
console" jumps from a notification to the full, cited conversation — and, when a
remediation is pending, to the Approve / Reject card.

## What it takes to demo one incident

The end-to-end demo is genuinely short: push a change that references an image
that cannot be pulled, watch ArgoCD mark the app Degraded, let the poller fire a
RCA, and approve the rollback from Slack. Two minutes, and the loop closes. That
is the whole point — the operator approves intent, and the fleet handles the
mechanics.

## What's next

We're continuing to tighten the loop: richer runbook grounding, more per-cloud
specialist coverage, and a cleaner path to the governance contracts the platform
is still maturing. For now, the demo shows the full journey from a crashed pod to
an approved, executed, cloud-aware remediation — with the governance receipts to
back it up.

*Repository and video links are placeholders — add before submission.*
