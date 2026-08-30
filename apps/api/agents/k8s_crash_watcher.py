"""Kubernetes crash-event watcher.

Watches cluster Events for crash/failure conditions and forwards a normalized
payload to the KaiOps deployment webhook so an autonomous RCA is auto-triggered.

This is the "auto-trigger on a failed/crashed deploy" piece: instead of a human
calling /webhooks/deploy, a watcher running on a schedule (Cloud Scheduler cron
or a Cloud Run job) scans cluster Events and fires the webhook when it sees
CrashLoopBackOff / ImagePullBackOff / OOMKilled / FailedScheduling / Back-off.

Cloud-aware: uses ``agents.k8s_executor._load_api()`` which credentials GKE
(ambient Google SA), EKS (boto3/awscli), or AKS (azure SDK/az) — so one watcher
serves all three clouds. The app's ``cloud_provider`` is resolved from the
application metadata (same helper the executor uses).

The watcher is idempotent: it only fires when it sees a NEW/updated crash event
for a given ``(namespace, object, reason)`` and won't re-fire the same incident
until it sees a distinct event (fingerprinted by event ``uid`` + ``lastTimestamp``).
"""

import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Incident reasons we care about (normalized -> incident_type).
_CRASH_REASONS = {
    "crashloopbackoff": "crashloopbackoff",
    "back-off": "crashloopbackoff",
    "imagepullbackoff": "imagepullbackoff",
    "errimagepull": "imagepullbackoff",
    "oomkilling": "oom_killed",
    "outofmemory": "oom_killed",
    "failedscheduling": "failed_scheduling",
    "failedmount": "failed_scheduling",
    "unhealthy": "unhealthy",
}

# A short-lived in-memory dedupe set so a burst of identical events doesn't
# spam the webhook. Reset on each process run; combined with the webhook's own
# incident_key dedupe this is belt-and-suspenders.
_seen: set = set()

DEFAULT_LOOKBACK_SECONDS = int(os.environ.get("K8S_WATCH_LOOKBACK_SECONDS", "300"))
DEFAULT_NAMESPACE = os.environ.get("K8S_WATCH_NAMESPACE", "")  # empty = all namespaces


def _normalize_reason(reason: str) -> Optional[str]:
    """Map a raw k8s event reason to an incident_type, or None if not a crash."""
    return _CRASH_REASONS.get(reason.strip().lower())


def _events_since(api, lookback_seconds: int, namespace: str) -> List[Dict[str, Any]]:
    """List recent Events (with a time filter) from the cluster."""
    import datetime
    now = datetime.datetime.utcnow()
    cutoff = now - datetime.timedelta(seconds=lookback_seconds)
    try:
        if namespace:
            events = api.list_namespaced_event(namespace=namespace)
        else:
            events = api.list_event_for_all_namespaces()
    except Exception as e:  # noqa: BLE001
        logger.error(f"[WATCHER] Failed to list events: {e}")
        return []

    out = []
    for ev in events.items:
        # Firestore/protobuf event fields: last_timestamp, involved_object, reason.
        ts = getattr(ev, "last_timestamp", None) or getattr(ev, "first_timestamp", None)
        ts_dt = None
        if ts is not None:
            try:
                ts_dt = ts.replace(tzinfo=datetime.timezone.utc).replace(tzinfo=None)
            except Exception:  # noqa: BLE001
                ts_dt = None
        if ts_dt and ts_dt < cutoff:
            continue
        obj = getattr(ev, "involved_object", None)
        out.append({
            "reason": getattr(ev, "reason", ""),
            "message": getattr(ev, "message", ""),
            "type": getattr(ev, "type", ""),
            "namespace": getattr(obj, "namespace", "") if obj else "",
            "name": getattr(obj, "name", "") if obj else "",
            "kind": getattr(obj, "kind", "") if obj else "",
            "uid": getattr(ev, "metadata", None) and getattr(ev.metadata, "uid", "") or "",
            "last_timestamp": ts_dt,
            "count": getattr(ev, "count", 0),
        })
    return out


def _event_fingerprint(ev: Dict[str, Any]) -> str:
    """Stable fingerprint for dedupe: object + reason + lastTimestamp bucket."""
    ts = ev.get("last_timestamp")
    ts_str = str(ts) if ts else ""
    return f"{ev.get('namespace')}::{ev.get('name')}::{ev.get('reason')}::{ts_str}"


def _event_incident_type(ev: Dict[str, Any]) -> Optional[str]:
    return _normalize_reason(ev.get("reason") or "")


def _resolve_cloud_provider(application: str) -> str:
    """Resolve the app's cloud_provider (falls back to gcp)."""
    from agents.executor import get_cloud_provider_from_app
    return get_cloud_provider_from_app(application)


def _post_webhook(payload: Dict[str, Any], webhook_url: str, token: str) -> bool:
    """POST a normalized payload to the deploy webhook. Returns True on 2xx."""
    import requests
    try:
        resp = requests.post(
            webhook_url,
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        if resp.ok:
            logger.info(f"[WATCHER] Webhook accepted: {resp.text[:120]}")
            return True
        logger.warning(f"[WATCHER] Webhook returned {resp.status_code}: {resp.text[:200]}")
        return False
    except Exception as e:  # noqa: BLE001
        logger.error(f"[WATCHER] Webhook post failed: {e}")
        return False


def _create_job_in_process(payload: Dict[str, Any]) -> bool:
    """Create an autonomous job directly in Firestore (in-process self-invocation).

    Used when the watcher runs inside the backend (via /runtime/webhooks/watch)
    instead of POSTing over HTTP. Mirrors the deploy webhook's dedupe + job
    creation logic so the behavior is identical to the HTTP path.
    """
    from app.runtime import jobs as job_store

    application = payload.get("application") or "unknown"
    incident_type = payload.get("incident_type") or "unknown"
    provider = payload.get("cloud_provider") or "gcp"
    incident_key = f"{application.lower()}::{incident_type.lower()}"

    try:
        existing = job_store.find_open_by_fingerprint(incident_key)
        if existing:
            logger.info(f"[WATCHER] Deduped in-process for {incident_key}")
            return True  # treated as handled (deduped)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[WATCHER] dedupe check failed: {e}")

    prompt = (
        f"An application deployment is unhealthy/incident. Autonomous RCA requested.\n"
        f"Application: {application}\n"
        f"Cloud provider: {provider}\n"
        f"Incident type: {incident_type}\n"
        f"Namespace: {payload.get('namespace', 'default')}\n"
        f"Message: {payload.get('message', '')}\n"
        "Investigate the root cause, then use search_knowledge for runbook guidance, "
        "and provide diagnosis + remediation steps."
    )
    try:
        job = job_store.create_job(
            source="crash_watcher",
            incident_name=f"[{incident_type}] {application}",
            prompt=prompt,
            severity=payload.get("severity", "P1"),
            metadata={
                "cloud_provider": provider,
                "incident_type": incident_type,
                "application": application,
                "namespace": payload.get("namespace", "default"),
                "pod_name": payload.get("pod_name", ""),
                "deployment": payload.get("deployment", ""),
                "incident_key": incident_key,
                "message": payload.get("message", ""),
            },
        )
        logger.info(f"[WATCHER] Created in-process job {job['id']} for {incident_key}")
        return True
    except Exception as e:  # noqa: BLE001
        logger.error(f"[WATCHER] In-process job creation failed: {e}")
        return False


def _dispatch(payload: Dict[str, Any], webhook_url: str, token: str) -> bool:
    """Dispatch a payload to either the HTTP webhook or in-process job creation."""
    if webhook_url:
        return _post_webhook(payload, webhook_url, token)
    return _create_job_in_process(payload)


def watch_for_crash_events(
    webhook_url: str = "",
    token: str = "",
    lookback_seconds: int = DEFAULT_LOOKBACK_SECONDS,
    namespace: str = DEFAULT_NAMESPACE,
    application: str = "",
    severity: str = "P1",
) -> Dict[str, Any]:
    """Scan recent cluster events and trigger an RCA for new crash conditions.

    When ``webhook_url`` is set, events are forwarded to the deploy webhook over
    HTTP. When it is empty, jobs are created directly in Firestore (in-process),
    which is how the ``/runtime/webhooks/watch`` scheduled endpoint drives it.

    Returns a summary of what was sent (and what was deduped).
    """
    from agents.k8s_executor import _load_api

    api = _load_api()
    events = _events_since(api, lookback_seconds, namespace)

    triggered = 0
    deduped = 0
    matched = []

    for ev in events:
        incident_type = _event_incident_type(ev)
        if not incident_type:
            continue
        fp = _event_fingerprint(ev)
        if fp in _seen:
            deduped += 1
            continue
        _seen.add(fp)

        # Resolve cloud provider. If the watcher is scoped to a known app use it,
        # else default the provider (the webhook validates gcp/aws/azure).
        provider = _resolve_cloud_provider(application) if application else None
        payload = {
            "cloud_provider": provider or "gcp",
            "incident_type": incident_type,
            "application": application or ev.get("name") or "unknown",
            "namespace": ev.get("namespace") or "default",
            "pod_name": ev.get("name") or "",
            "deployment": ev.get("name") or "",
            "severity": severity,
            "message": f"{ev.get('reason')}: {ev.get('message')}"[:500],
        }
        ok = _dispatch(payload, webhook_url, token)
        if ok:
            triggered += 1
            matched.append(incident_type)
        else:
            # Webhook/job rejected; don't keep it deduped so we retry next scan.
            _seen.discard(fp)
            deduped += 1

    logger.info(f"[WATCHER] Scan: {len(events)} events, {triggered} triggered, {deduped} deduped/skipped")
    return {
        "events_scanned": len(events),
        "triggered": triggered,
        "deduped": deduped,
        "incident_types": matched,
    }


def build_default_webhook_payload(application: str) -> Dict[str, Any]:
    """Convenience for a single-fire webhook call (synthetic test)."""
    return {
        "cloud_provider": _resolve_cloud_provider(application),
        "incident_type": "crashloopbackoff",
        "application": application,
        "namespace": "default",
        "pod_name": "",
        "deployment": application,
        "severity": "P1",
        "message": "CrashLoopBackOff detected by KaiOps crash-event watcher",
    }
