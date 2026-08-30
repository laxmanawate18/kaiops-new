"""ArgoCD status poller — the deployment-health trigger for the closed loop.

Polls ArgoCD (via the already-authenticated MCP server) for the status of every
tracked Application and, on a **transition to a failure state** (Degraded /
Failed / OutOfSync / Missing), triggers a KaiOps RCA job. On Healthy/ Synced it
emits a lightweight "deploy OK" notification.

Design (matches the user's spec):
- Source of truth = ArgoCD `Application.status` (health + sync), read through
  ``agents.argocd_agent.tools`` (which calls the argocd-mcp-server that holds creds).
- Poller runs on a schedule (Cloud Scheduler -> POST /runtime/argocd/check) or
  inline from a one-shot worker.
- Journalizes last-seen status per application in Firestore (``argocd_app_state``)
  so it only reacts to **changes**, not every poll.
- On failure: creates an autonomous RCA job (reuses ``job_store``) and posts a
  thread-aware Slack message (see ``app.slack.reporter``).
- On healthy: posts/replies a "✅ deployed successfully" update in the app thread.

Cloud-aware: ArgoCD is the deployment controller across GKE/EKS/AKS; the app's
``cloud_provider`` is resolved from Firestore application metadata.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional

from app.database.firestore_config import FirestoreConfig
from app.runtime import jobs as job_store

logger = logging.getLogger(__name__)

# Statuses that warrant an autonomous RCA + Slack alert.
_FAILURE_SYNC = {"OutOfSync", "Failed", "Unknown"}
_FAILURE_HEALTH = {"Degraded", "Failed", "Missing", "Unknown"}
_HEALTHY_HEALTH = {"Healthy"}
_HEALTHY_SYNC = {"Synced", "Healthy"}
# Statuses where we should ping the developer it's healthy.
_FAILURE_SENSITIVE = {"Degraded", "Failed", "OutOfSync", "Missing", "Progressing"}

DEFAULT_TRACKED_APPS = os.environ.get("ARGOCD_TRACKED_APPS", "").strip()
FRONTEND_URL = os.environ.get("KAI_OPS_FRONTEND_URL", "https://kaiops-sre.searceinc.net")


def _argocd_api() -> Optional[str]:
    """Return a valid ArgoCD session token (basic auth -> /api/v1/session)."""
    import requests, urllib3
    urllib3.disable_warnings()
    url = os.environ.get("ARGOCD_URL", "https://34.61.13.1").rstrip("/")
    user = os.environ.get("ARGOCD_USERNAME", "admin")
    pw = os.environ.get("ARGOCD_PASSWORD", "")
    try:
        r = requests.post(f"{url}/api/v1/session", json={"username": user, "password": pw}, verify=False, timeout=15)
        if r.status_code == 200:
            return r.json().get("token")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ARGOCD] session login failed: {e}")
    return None


def _argocd_request(path: str):
    """GET an ArgoCD API path with a valid session token; returns JSON or None."""
    import requests, urllib3
    urllib3.disable_warnings()
    url = os.environ.get("ARGOCD_URL", "https://34.61.13.1").rstrip("/")
    token = _argocd_api()
    if not token:
        return None
    try:
        r = requests.get(f"{url}{path}", headers={"Authorization": f"Bearer {token}"}, verify=False, timeout=20)
        if r.status_code == 200:
            return r.json()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ARGOCD] GET {path} failed: {e}")
    return None


def _list_applications() -> List[Dict[str, Any]]:
    """List all ArgoCD Applications (recommendations) via the ArgoCD REST API."""
    data = _argocd_request("/api/v1/applications")
    if data is None:
        # Fallback to MCP text parse.
        return _list_applications_mcp()
    items = data.get("items", [])
    result = []
    for it in items:
        meta = it.get("metadata", {})
        st = it.get("status", {})
        result.append({
            "name": meta.get("name"),
            "health": st.get("health", {}).get("status"),
            "sync": st.get("sync", {}).get("status"),
            "message": "",
        })
    return [r for r in result if r.get("name")]


async def _list_applications_mcp() -> List[Dict[str, Any]]:
    """Fallback: parse app names from MCP search_applications output."""
    from agents.argocd_agent.tools import search_applications
    try:
        raw = await search_applications(query="", limit=200)
        return _parse_app_names(raw)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ARGOCD] MCP search_applications failed: {e}")
        return []


def _parse_app_names(raw: str) -> List[Dict[str, Any]]:
    """Best-effort parse of ArgoCD search output into [{'name': ...}] list."""
    names = []
    seen = set()
    for line in (raw or "").splitlines():
        line = line.strip()
        for token in line.replace("|", " ").split():
            if token and ("http" not in token and len(token) > 3 and token not in seen):
                if not any(x in token.lower() for x in ("health", "sync", "status", "app")):
                    seen.add(token)
                    names.append({"name": token})
                    break
    return names


async def _get_app_status(app_name: str) -> Optional[Dict[str, Any]]:
    """Get one ArgoCD application's status via the structured REST API (preferred)."""
    # Try direct REST: /api/v1/applications/{name}
    data = _argocd_request(f"/api/v1/applications/{app_name}")
    if data and isinstance(data, dict):
        st = data.get("status", {})
        return {
            "name": data.get("metadata", {}).get("name", app_name),
            "health": st.get("health", {}).get("status", "Unknown"),
            "sync": st.get("sync", {}).get("status", "Unknown"),
            "message": "",
        }
    # Fallback: MCP text.
    from agents.argocd_agent.tools import get_application_status
    try:
        raw = await get_application_status(app_name)
        return _parse_status(raw, app_name)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ARGOCD] get_application_status({app_name}) failed: {e}")
        return None


def _parse_status(raw: str, app_name: str) -> Dict[str, Any]:
    """Turn ArgoCD status text into {name, health, sync, message}."""
    health = "Unknown"
    sync = "Unknown"
    message = raw or ""
    low = (raw or "").lower()
    if "healthy" in low:
        health = "Healthy"
    elif "degraded" in low:
        health = "Degraded"
    elif "progressing" in low:
        health = "Progressing"
    elif "missing" in low:
        health = "Missing"
    if "synced" in low:
        sync = "Synced"
    elif "outofsync" in low or "out-of-sync" in low:
        sync = "OutOfSync"
    elif "failed" in low:
        sync = "Failed"
    return {"name": app_name, "health": health, "sync": sync, "message": message}


def _state_ref():
    return FirestoreConfig.get_client().collection("argocd_app_state")


def _get_last_state(app_name: str) -> Optional[Dict[str, Any]]:
    try:
        doc = _state_ref().document(app_name).get()
        return doc.to_dict() if doc.exists else None
    except Exception:  # noqa: BLE001
        return None


def _save_state(app_name: str, state: Dict[str, Any]) -> None:
    try:
        _state_ref().document(app_name).set({
            **state,
            "checked_at": __import__("datetime").datetime.utcnow().isoformat(),
        })
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ARGOCD] save_state failed: {e}")


def _resolve_app_name(candidate: str) -> str:
    """ArgoCD app name may differ from Firestore application_name; here we use
    the same name by convention (deploy settings set application_name = argocd app)."""
    return candidate


def _is_failure(state: Dict[str, Any]) -> bool:
    return (state.get("health") in _FAILURE_HEALTH) or (state.get("sync") in _FAILURE_SYNC)


def _is_healthy(state: Dict[str, Any]) -> bool:
    return state.get("health") in _HEALTHY_HEALTH


async def check_and_trigger(application: str = "", dry_run: bool = False) -> Dict[str, Any]:
    """Poll tracked ArgoCD apps and trigger RCA/Slack on status transitions.

    Returns a summary count. ``dry_run`` only logs, doesn't create jobs/Slack.
    """
    triggered = 0
    healthy_updates = 0
    unchanged = 0

    if application:
        names = [{"name": application}]
    else:
        names = _list_applications()
        if not names and DEFAULT_TRACKED_APPS:
            names = [{"name": n.strip()} for n in DEFAULT_TRACKED_APPS.split(",") if n.strip()]

    for item in names:
        app_name = item.get("name")
        if not app_name:
            continue
        resolved = _resolve_app_name(app_name)
        state = await _get_app_status(app_name)
        if not state:
            continue

        last = _get_last_state(resolved)
        changed = (last is None) or (last.get("health") != state.get("health")) or (last.get("sync") != state.get("sync"))

        if not changed:
            unchanged += 1
            continue

        _save_state(resolved, state)

        if dry_run:
            logger.info(f"[ARGOCD DRY] {resolved}: health={state['health']} sync={state['sync']} changed={changed}")
            continue

        if _is_failure(state):
            triggered += 1
            await _handle_failure(resolved, state)
        elif _is_healthy(state):
            healthy_updates += 1
            await _handle_healthy(resolved, state)

    return {"apps": len(names), "triggered": triggered, "healthy_updates": healthy_updates, "unchanged": unchanged}


async def _handle_failure(app_name: str, state: Dict[str, Any]) -> None:
    """Create an RCA job + Slack alert for a failed/degraded ArgoCD app."""
    from app.slack.reporter import report_app_status
    logger.info(f"[ARGOCD] FAILURE: {app_name} health={state['health']} sync={state['sync']}")

    incident_type = (state.get("sync") or state.get("health") or "failed").lower()
    provider = "gcp"
    try:
        from app.applications.database_firestore import application_db
        app = application_db.get_application_by_name(app_name)
        provider = (app or {}).get("cloud_provider") or provider
    except Exception:  # noqa: BLE001
        pass

    prompt = (
        f"ArgoCD reports application `{app_name}` is unhealthy/degraded. "
        f"Health: {state.get('health')}. Sync: {state.get('sync')}. "
        f"Cloud provider: {provider}. "
        "Investigate the root cause, determine if it is application-related or "
        "infrastructure-related, and provide diagnosis + remediation steps. "
        "After the RCA, send the summary to Slack with the status header "
        "[App_Name] Failed and tag SRE team if it is infra-related."
    )
    try:
        job = job_store.create_job(
            source="argocd_poller",
            incident_name=f"[{state.get('sync')}] {app_name}",
            prompt=prompt,
            severity="P1",
            metadata={"cloud_provider": provider, "argocd_app": app_name,
                      "health": state.get("health"), "sync": state.get("sync"),
                      "incident_type": incident_type},
        )
        logger.info(f"[ARGOCD] Created job {job['id']} for {app_name}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[ARGOCD] create job failed: {e}")

    # Post the Slack alert (reporter creates/replies to per-app thread).
    try:
        await report_app_status(
            app_name=app_name, status="Failed", detail=state.get("message", ""),
            cloud_provider=provider,
            session_link=f"{FRONTEND_URL}/console/runtime-{job.get('id')}" if job.get("id") else "",
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"[ARGOCD] Slack report failed: {e}")


async def _handle_healthy(app_name: str, state: Dict[str, Any]) -> None:
    """Post/reply a healthy deploy confirmation in the app's thread."""
    from app.slack.reporter import report_app_status
    logger.info(f"[ARGOCD] HEALTHY: {app_name} health={state['health']} sync={state['sync']}")
    try:
        await report_app_status(app_name=app_name, status="Healthy", detail="Application deployed successfully.", cloud_provider="gcp")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[ARGOCD] healthy report failed: {e}")
