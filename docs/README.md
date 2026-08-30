# KaiOps Documentation

Centralized index for all project documentation. This preserves the full engineering
context (architecture, findings, specs) in one place so the repo is reviewable and
navigable.

## Index

| Doc | Purpose |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | **System architecture** — multi-cloud governed agent mesh, Gemini Enterprise components, location matrix, deployment topology, security model, known constraints. |
| [WEBHOOK_TRIGGER.md](WEBHOOK_TRIGGER.md) | Deployment-failure trigger + cloud-aware remediation — `/webhooks/deploy`, job dedupe, GKE/EKS/AKS executor, Slack deep-link. |
| [E2E_TEST_REPORT.md](E2E_TEST_REPORT.md) | Full end-to-end product/feature test report of the deployed mesh (auth, chat, autonomous loop, gateway, governance) + bugs/observations + resolutions. |
| [RAG_ENGINE_BRD.md](RAG_ENGINE_BRD.md) | Business Requirements Doc for the RAG Engine (Gemini Enterprise Agent Platform) grounding — corpus, retrieval, tooling. |
| [GATEWAY_FINDING.md](GATEWAY_FINDING.md) | Agent Gateway egress investigation — root cause (IAP AuthzPolicy target must use project NUMBER not ID) + resolution. |
| [aliased_A2A_topology.md](aliased_A2A_topology.md) | Governed A2A mesh topology (orchestrator → GCP/AWS/Azure specialists via Agent Gateway). |
| [FEATURE_PROGRESS.md](FEATURE_PROGRESS.md) | Feature push log (MCP Registry, Model Armor, Semantic Governance, gateway A2A routing) — what works & gotchas. |

## Other docs in the repo

- Root `README.md` — entry point / quickstart.
- `infrastructure/loadbalancer/README.md` — Phase 2 frontend HTTPS LB + Google-managed cert.
- `runbooks/` + `apps/api/runbooks/` — operation runbooks.
