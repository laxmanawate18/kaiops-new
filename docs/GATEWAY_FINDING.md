# KaiOps Agent Gateway — Egress Block: Diagnostic Findings

> **Status:** Investigated exhaustively. The gateway egress CONNECT is denied at the Google-managed Secure Web Proxy (SWP) layer. All user-controllable knobs were verified. Needs a Google Cloud support case (or accept as a Google-managed-only path).

## Environment
- Project: `project-3da8cb5f-328e-44d3-b7a` (number `275388304596`), `us-central1`
- Gateway: `kaiops-egress-gw` (`projects/project-3da8cb5f-328e-44d3-b7a/locations/us-central1/agentGateways/kaiops-egress-gw`)
- Gateway resource type: **`agent-gateways`** (NOT the user-facing `networkservices.googleapis.com/Gateway`)
- `googleManaged.governedAccessPath: AGENT_TO_ANYWHERE` (egress proxy mode)
- Test engine (gateway-bound): `3796153505094303744` (`AGENT_IDENTITY`, `agentGatewayConfig` present, `GOOGLE_API_USE_CLIENT_CERTIFICATE=true`, `GOOGLE_API_USE_MTLS_ENDPOINT=true`)

## Exact Error (caller-visible)
```
Reasoning Engine Execution failed.
Error Details: {"detail":"Agent Engine Error: An error occurred during invocation. Exception: Failed to send request to
https://us-central1-aiplatform.mtls.googleapis.com/v1beta1/projects/project-3da8cb5f-328e-44d3-b7a/locations/us-central1/reasoningEngines/3796153505094303744/sessions.
Request Data: {'user_id': 'u_gw2'}"}
```

## Gateway Log (the authoritative failure)
`resource.type="networkservices.googleapis.com/Gateway"`, `gateway_name="kaiops-egress-gw"`

```json
{
  "httpRequest": { "requestMethod": "CONNECT", "status": 403 },
  "jsonPayload": {
    "enforcedGatewaySecurityPolicy": {
      "hostname": "240.0.0.2:443",
      "matchedRules": [ { "action": "DENIED", "name": "default_denied" } ]
    },
    "mtls": {
      "clientCertChainVerified": "false",
      "clientCertError": "client_cert_validation_not_performed",
      "clientCertPresent": "true",
      "clientCertSha256Fingerprint": "uA1hVw50fC9ZbIeWGSaE0R6kCG5mCoRHXwMmTmQ0Imc",
      "clientCertValidEndTime": "1970-01-01T00:00:00Z",
      "clientCertValidStartTime": "1970-01-01T00:00:00Z"
    }
  }
}
```

## Architecture Confirmed
The gateway is a **Google-managed `AgentGateway`** — the concrete `agent-gateways` resource. This differs from a user-owned SWP `gateways` resource:
- `network-services gateways describe kaiops-egress-gw` → **NOT_FOUND** (the backing Envoy/SWP lives in a Google-controled tenant project `p38cac5cfcb3d718bp-tp`).
- `agent-gateways describe` exposes only: `agentGatewayCard` (mtlsEndpoint = PSC `serviceAttachments/unitkind1-swp-mtls-psc-sa`, `rootCertificates` = gateway's own TLS-inspection CA, `serviceExtensionsServiceAccount`), `googleManaged.governedAccessPath`, `registries`.
- **No `gatewaySecurityPolicy`, `serverTlsPolicy`, `urlMap`, `TrustConfig`, `backendService`, `routingPolicy`** — confirmed `absent` across the resource.

## What Was Verified (each a possible lever, all exhausted)
| # | Lever | Result |
|---|---|---|
| 1 | Destination hostname registered (`us-central1-aiplatform.mtls.googleapis.com` as endpoint `223e-b016f34083e5`) | ✅ present — not the gap |
| 2 | All hostname variants (plain, mtls, rep, agentregistry) registered | ✅ 8 endpoints present |
| 3 | mTLS variants required by deploy doc (`telemetry.mtls`, `logging.mtls`, `telemetry`, `logging`) | ✅ registered + `iap.egressor` granted |
| 4 | `roles/iap.egressor` on mtls endpoint for the orchestrator identity | ✅ granted (old + current engines) |
| 5 | IAP authz extension `kaiops-iap-request-authz-ext` | ✅ present, `iamEnforcementMode: DRY_RUN`, `failOpen: true` |
| 6 | Gateway-bound engine deployed with `agentGatewayConfig` + mTLS env vars ON | ✅ configured |
| 7 | Explicit `GatewaySecurityPolicyRule` (allow) | ❌ **not possible** — no user-facing `gatewaySecurityPolicy` on the resource |
| 8 | `network-security authorization-policies` | ❌ `count: 0` (no user policy) |
| 9 | Agent Registry `bindings create` (source→target) | ❌ `INVALID_ARGUMENT: auth_provider is required` — bindings are for auth-provider/OAuth, NOT the egress allowlist |

## Root Cause (conclusion)
The Google-managed SWP backing `kaiops-egress-gw` uses a **zero-trust default-deny** session policy. The `CONNECT 240.0.0.2:443` (the proxy's frontend loopback IP for the PSC/mtLS endpoint) does not match any allow rule the control plane generated, so it falls to the implicit `default_denied`. Because the session is denied at policy-evaluation before the proxy runs client-cert-chain verification, the `mtls` fields remain at **uninitialized defaults**:
- `clientCertPresent: "true"` (the agent DID present a cert via `GOOGLE_API_USE_CLIENT_CERTIFICATE=true`)
- `clientCertChainVerified: "false"`, `clientCertError: client_cert_validation_not_performed`
- validity `1970-01-01T00:00:00Z` (epoch-zero — never populated)

**The allow rule + trust-confirmation is Google-managed and not reachable via the exposed APIs.** Every user-controllable knob (registry endpoints, IAM egressor, authz extension, mTLS env, gateway-bound config, registry bindings) was verified and none unblocked it.

## Recommended Next Actions
1. **Google Cloud Support case** with the exact error above + gateway log. Request: (a) allow the CONNECT destination `us-central1-aiplatform.mtls.googleapis.com:443` (→ `240.0.0.2:443`) on the Agent Gateway's internal SWP security policy, and (b) confirm the engine's agent cert (fingerprint `uA1hVw50...`) is trusted by the gateway's trust plane.
2. **Until resolved**, run the mesh on the **identity-only governed orchestrator** (`3008867995234598912` — Memory Bank + telemetry + A2A) + 3 Cloud Run A2A specialists delegating directly over public URLs with `A2A_SHARED_TOKEN`. This is the proven, working governed mesh.

## Remediation Attempted (per architecture analysis)
The following was applied in response to the zero-trust-default-deny / bogus-IP hypothesis:

| Step | Action | Result |
|---|---|---|
| A | Deleted the malformed `kaiops-endpoint-aiplatform-mtls-ip` → `https://240.0.0.2` CUSTOM-agent service (`gcloud agent-registry services delete`) | ✅ rs=0, `240.0.0.2` removed from registry |
| B | Registered the proper endpoint service `vertex-aiplatform-mtls` → `https://us-central1-aiplatform.mtls.googleapis.com` (`endpointSpec: NO_SPEC`, `HTTP_JSON`) | ✅ created |
| C | Granted `roles/iap.egressor` to the registry-level principalSet `principalSet://agents.global.org-820797041517.system.id.goog/attribute.platformContainer/aiplatform/projects/275388304596` via `iap setIamPolicy` | ✅ 1 binding applied |

### Outcome: No change
After A+B+C, the gateway-bound engine `3796153505094303744` session create still returns `400` (`Failed to send request .../sessions`), and the gateway log (14:22) is **identical**:
```
hostname: 240.0.0.2:443
matchedRules: [{ action: DENIED, name: default_denied }]
mtls: {
  clientCertPresent: true,
  clientCertChainVerified: false,
  clientCertError: client_cert_validation_not_performed,
  clientCertValidStartTime: 1970-01-01T00:00:00Z,
  clientCertValidEndTime:   1970-01-01T00:00:00Z
}
```

**Conclusion:** The registry/IAM/allowlist fixes do NOT resolve it. The `client_cert_validation_not_performed` + epoch-zero cert validity persists even with the correct endpoint registered and the engine authorized — this is the **agent's mTLS client-certificate not being recognized** by the Google-managed trust plane (the CAA cert-binding layer), independent of the allowlist.
