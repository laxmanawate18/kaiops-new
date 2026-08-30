"""Remediation guidance + app-vs-infra classifier for the KaiOps agent.

Implements two user requirements:
1. A **HITL action catalog** that lists available remediation actions up-front and
   tells the agent to only surface the specific action needed for the situation.
2. An **app-vs-infra classifier** that categorizes an incident's root cause so the
   Slack reporter tags SRE team only when it is infrastructure-related.

The agent calls these helpers as tools, so the LLM uses deterministic guidance
rather than guessing.
"""

# --------------------------------------------------------------------------- #
# HITL action catalog (shown to the agent once)
# --------------------------------------------------------------------------- #
HITL_ACTION_CATALOG = {
    "restart_pod": {
        "tool": "restart_pod",
        "summary": "Delete a pod so its controller recreates it (quick recovery).",
        "when_to_use": "CrashLoopBackOff, OOMKilled transient, stuck/not-ready pod.",
        "risk": "Low - brief impact only that pod.",
    },
    "rollback_application": {
        "tool": "rollback_application",
        "summary": "Roll the ArgoCD application back to a previous revision.",
        "when_to_use": "A bad code/image release caused the failure.",
        "risk": "Medium - reverts the deploy to an older build.",
    },
    "sync_application": {
        "tool": "sync_application",
        "summary": "Re-sync the ArgoCD application to the desired Git state.",
        "when_to_use": "OutOfSync / partially-applied manifest; reconcile config.",
        "risk": "Medium - reapplies manifests.",
    },
}


def list_hitl_actions(reason: str = "") -> str:
    """Return the HITL action catalog as text for the agent prompt."""
    lines = ["Available HITL remediation actions (only surface the ONE that fits):"]
    for key, info in HITL_ACTION_CATALOG.items():
        lines.append(
            f"- **{key}**: {info['summary']}\n"
            f"  - Use when: {info['when_to_use']}\n"
            f"  - Risk: {info['risk']}"
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# App-vs-infra classifier
# --------------------------------------------------------------------------- #
_APP_SIGNALS = [
    "exit code", "crashloop", "crash loop", "runtimeerror", "exception",
    "app error", "nil pointer", "connection refused (app", "application error",
    "config error", "migration failed", "dependency error", "panic", "bad request",
]
_INFRA_SIGNALS = [
    "node", "cluster", "oomexceeded", "oomkilled", "disk", "storage", "volume",
    "networkpolicy", "dns", "pullerror", "imagepullbackoff", "failedpull",
    "insufficient cpu", "insufficient memory", "quota", "limitrange",
    "unschedulable", "failedmount", "apiserver", "etcd", "loadbalancer",
    "ingress", "cert", "secretmount", "tls", "timeout (infra)", "conn refused (infra)",
]


def classify_root_cause(rca_text: str) -> str:
    """Classify an RCA as 'app' or 'infra' based on signal keywords.

    Returns 'infra' if infra signals dominate, else 'app'. Defaults to 'app'
    (most incidents are change-related). The agent uses this to decide whether
    to tag SRE team in the Slack thread.
    """
    text = (rca_text or "").lower()
    infra_hits = sum(1 for s in _INFRA_SIGNALS if s.lower() in text)
    app_hits = sum(1 for s in _APP_SIGNALS if s.lower() in text)
    # If infra signals clearly present, classify infra.
    if infra_hits > app_hits:
        return "infra"
    if infra_hits > 0 and infra_hits >= 1:
        # A single strong infra signal (e.g. OOMKilled, node, imagepullbackoff)
        # that isn't obviously an app bug -> infra.
        return "infra"
    return "app"


def classify_tool(rca_text: str) -> str:
    """Agent-facing tool wrapper around classify_root_cause."""
    return f"Classification: **{classify_root_cause(rca_text)}**"


__all__ = ["list_hitl_actions", "classify_root_cause", "classify_tool", "HITL_ACTION_CATALOG"]
