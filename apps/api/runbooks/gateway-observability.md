# Gateway & Specialists Observability Runbook

> Live governed mesh: gateway-bound orchestrator `3796153505094303744` → Agent Gateway `kaiops-egress-gw` → Cloud Run A2A specialists.
> Project `project-3da8cb5f-328e-44d3-b7a` (number `275388304596`), `us-central1`.

This runbook is the single place for observing the **Agent Gateway** and the **A2A specialists**. It turns the ad-hoc queries that were critical during debugging into reusable, copy-paste views.

## 1. Gateway egress decision log (the authoritative signal)

This is the exact log that unblocked the gateway. It shows whether the gateway is `ALLOW`/`DENY`ing a CONNECT, and — crucially — whether the IAP authz extension was invoked (`authzInfo` populated vs empty).

**Log Explorer query (Cloud Logging):**

```sql
resource.type="networkservices.googleapis.com/Gateway"
resource.labels.gateway_name="kaiops-egress-gw"
httpRequest.requestMethod="CONNECT"
```

**Key fields to read:**
| Field | Meaning |
|---|---|
| `httpRequest.status` | `403` = denied, `200`/`204` = allowed |
| `jsonPayload.enforcedGatewaySecurityPolicy.matchedRules` | Which rule matched; `default_denied` = fell through to zero-trust default |
| `jsonPayload.mtls.clientCertChainVerified` | `true` = agent cert validated; `false` = not performed |
| `jsonPayload.mtls.clientCertError` | `client_cert_validation_not_performed` = cert never verified |
| `jsonPayload.mtls.clientCertValidStartTime/EndTime` | `1970-01-01` = epoch-zero (unverifiable) |
| `jsonPayload.authzInfo` | **Empty `{}` = extension NOT invoked (broken chain); populated = IAP decision ran** |

> ✅ **Healthy state:** `status=200`, cert verified, `authzInfo` populated (extension running in PASS-through/DRY_RUN).

## 2. Authz policy / extension bind check (what the gateway routes through)

**Policy** `kaiops-iap-request-authz-policy` must target the gateway + extension by **project NUMBER** (not project ID):

```bash
gcloud network-security authz-policies describe kaiops-iap-request-authz-policy \
  --project=project-3da8cb5f-328e-44d3-b7a --location=us-central1
```

Expected: `action: CUSTOM`, `policyProfile: REQUEST_AUTHZ`,
`target.resources = ["projects/275388304596/locations/us-central1/agentGateways/kaiops-egress-gw"]`,
`customProvider.authzExtension.resources = ["projects/275388304596/locations/us-central1/authzExtensions/kaiops-iap-request-authz-ext"]`.

**Extension** `kaiops-iap-request-authz-ext` (failOpen=true):

```bash
gcloud service-extensions authz-extensions describe kaiops-iap-request-authz-ext --project=project-3da8cb5f-328e-44d3-b7a --location=us-central1
```

## 3. Or is the gateway not even being hit? (session-level failure)

If a gateway-bound engine's session create fails, first confirm the gateway is receiving traffic. If there's **no gateway log entry**, the request failed *before* the gateway — check the engine itself.

**Engine query (Async Create Session):**

```bash
curl -s -X POST "https://us-central1-aiplatform.googleapis.com/v1beta1/projects/275388304596/locations/us-central1/reasoningEngines/3796153505094303744:query" \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  -d '{"class_method":"async_create_session","input":{"user_id":"probe"}}'
```

- `200` with `{output:{id,...}}` = session created through the gateway ✅
- `400 Failed to send request .../sessions` = engine reachable but egress/session subcall failed (check step 1)

## 4. Specialist telemetry (Cloud Trace)

All 3 Cloud Run A2A specialists have `GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=true` → they auto-init the OTel/Cloud Trace exporter on startup.

**Trace Explorer query:**
- Service: `kaiops-gcp-a2a` / `kaiops-aws-a2a` / `kaiops-azure-a2a`
- Region: `us-central1`
- Look for the A2A `message/send` spans showing the delegating specialist's reasoning.

**Per-specialist env sanity (via Cloud Run describe):**

| var | value |
|---|---|
| `GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY` | `true` |
| `GEMINI_MODEL` | `gemini-3.6-flash` |
| `APP_URL` | the real Cloud Run URL (matches advertised card) |
| `A2A_SHARED_TOKEN` | shared Bearer token |

## 5. Agent Registry / Gateway allowlist view

The gateway's destination allowlist is synthesized from the **regional** registry (`us-central1`). Verify reachable hosts only:

```bash
# Regional registry services (gateway uses us-central1)
gcloud agent-registry services list --location=us-central1 --project=project-3da8cb5f-328e-44d3-b7a
```

All entries should point at real, reachable hostnames. There should be **no bogus IP registrations** (e.g. `240.0.0.2`).

## 6. Full delegation chain check

To prove the whole governed path end-to-end (orchestrator → gateway → specialist), send an RCA query and confirm `transfer_to_agent` fires + the specialist card resolves (no `Failed to resolve AgentCard`): see `GATEWAY_FINDING.md` and `aliased_A2A_topology.md`.

---

## Fast triage matrix

| Symptom | Read | Likely cause |
|---|---|---|
| `status=403`, `default_denied`, `authzInfo:{}` | §1 | Gateway→policy→extension chain broken (policy target must use project **NUMBER**) |
| `client_cert_validation_not_performed`, epoch-zero | §1 | mTLS cert not presented/validated (shouldn't happen now the chain is correct) |
| `400 Failed to send request .../sessions` entry | §3 | Egress proxy / destination not allowlisted |
| `no gateway log` but session fails | §3 | Request never reached gateway — engine-layer issue |
| Specialist slow / cold | §4 + topology | Warm-start (`min-instances=1`) + concurrency (36) already set |
