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
        dest = data.get("spec", {}).get("destination", {})
        return {
            "name": data.get("metadata", {}).get("name", app_name),
            "health": st.get("health", {}).get("status", "Unknown"),
            "sync": st.get("sync", {}).get("status", "Unknown"),
            "message": "",
            "namespace": dest.get("namespace", ""),
            "cluster": dest.get("server", "").split("//")[-1] or "",
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


def _app_metadata_exists(app_name: str) -> bool:
    """Return True if the app is already registered in KaiOps application metadata."""
    try:
        from app.applications.database_firestore import application_db
        return application_db.get_application_by_name(app_name) is not None
    except Exception:  # noqa: BLE001
        return False


def _infer_cloud_provider(cluster: str) -> str:
    """Infer the cloud provider from an ArgoCD destination server / cluster name.

    AKS control-plane DNS ends in ``*.azmk8s.io`` or ``*.hcp.*.azmk8s.io``;
    EKS hosts are ``*.eks.amazonaws.com`` and kubeconfig contexts are
    ``arn:aws:eks:...``. Anything else (``kubernetes.default.svc`` = in-cluster
    GKE) defaults to ``gcp``.
    """
    c = (cluster or "").lower()
    if "azmk8s" in c or ".azure." in c:
        return "azure"
    if ".eks.amazonaws.com" in c or "arn:aws:eks" in c or ":cluster/" in c:
        return "aws"
    return "gcp"


def _auto_register_app(app_name: str, state: Dict[str, Any]) -> None:
    """Auto-register an ArgoCD-discovered app into KaiOps metadata (zero-touch).

    Driven by CI/CD: the app is authored in a Git repo + deployed via ArgoCD,
    and this poller syncs it into the KaiOps Firestore ``applications`` collection
    so routing (cloud_provider) and RCA work without any manual entry.

    - ``cloud_provider`` is inferred from the ArgoCD Application destination
      server (AKS -> azure, EKS -> aws, else gcp), so a cross-cloud app
      self-registers with the right routing without manual Firestore edits.
    - namespace/cluster are taken from the ArgoCD Application spec destination.
    """
    try:
        from app.applications.database_firestore import application_db
        if _app_metadata_exists(app_name):
            return
        # Compute a best-effort cloud_provider + namespace.
        namespace = state.get("namespace") or ""
        cluster = state.get("cluster") or os.environ.get("GKE_CLUSTER_NAME", "")
        cloud = _infer_cloud_provider(state.get("cluster") or cluster)
        # Auto-provision a Grafana dashboard + alert rule for the app so the RCA
        # flow has a first-class observability surface to reference. Best-effort.
        grafana = {}
        try:
            from agents.grafana_agent.provision import provision_app
            grafana = provision_app(app_name, namespace) or {}
        except Exception as gerr:  # noqa: BLE001
            logger.warning(f"[ARGOCD] grafana provisioning failed for {app_name}: {gerr}")
        app_data = {
            "application_name": app_name,
            "application_owner": "kaiops-auto",
            "cloud_provider": cloud,
            "namespace": namespace,
            "gke_cluster_name": cluster,
            "argocd_app_name": app_name,
            "status": "ACTIVE",
            "grafana_dashboard": grafana.get("grafana_dashboard", ""),
            "grafana_dashboard_url": grafana.get("grafana_dashboard_url", ""),
            "grafana_alert": grafana.get("grafana_alert", ""),
            "custom_metadata": [{"key": "source", "value": "argocd_auto_register"}],
        }
        application_db.create_application(app_data)
        logger.info(f"[ARGOCD] Auto-registered app '{app_name}' into KaiOps metadata (cloud={cloud}, grafana={grafana.get('grafana_dashboard','')})")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ARGOCD] auto-register failed for {app_name}: {e}")


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

        # Auto-register the app into KaiOps metadata if it's not there yet
        # (zero-touch: CI/CD -> ArgoCD -> this poller -> Firestore).
        if not _app_metadata_exists(resolved):
            _auto_register_app(resolved, state)

        # Always ensure the app has a real, resolvable KaiOps console session
        # (runtime-kaiops-{app_name}) so the Slack "Open console" deep-link never
        # 404s, even when there's no status transition to report.
        try:
            from app.chat.agent_service import get_session_service
            get_session_service().ensure_app_session(app_name)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[ARGOCD] ensure_app_session for {app_name} failed: {e}")

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
    grafana_dash = ""
    grafana_url = ""
    grafana_alert = ""
    try:
        from app.applications.database_firestore import application_db
        app = application_db.get_application_by_name(app_name)
        provider = (app or {}).get("cloud_provider") or provider
        grafana_dash = (app or {}).get("grafana_dashboard") or ""
        grafana_url = (app or {}).get("grafana_dashboard_url") or ""
        grafana_alert = (app or {}).get("grafana_alert") or ""
    except Exception:  # noqa: BLE001
        pass

    # Fall back to constructing the URL from the env GRAFANA_URL when metadata
    # doesn't carry one, so the report's dashboard link is always clickable.
    if not grafana_url:
        base = os.environ.get("GRAFANA_URL", "").rstrip("/")
        if base and grafana_dash:
            grafana_url = f"{base}/d/{grafana_dash}"
        elif base:
            grafana_url = f"{base}/d/kaiops-{app_name}"

    prompt = (
        f"ArgoCD reports application `{app_name}` is unhealthy/degraded. "
        f"Health: {state.get('health')}. Sync: {state.get('sync')}. "
        f"Cloud provider: {provider}. "
        "Investigate the root cause, determine if it is application-related or "
        "infrastructure-related, and provide diagnosis + remediation steps.\n"
        # Grafana observability: surface the app's dashboard + alert rules in the RCA.
        f"\nOBSERVABILITY: Use the Grafana tools (search_dashboards, list_alert_rules, "
        f"get_dashboard_summary, query_prometheus) to pull metrics and alert state for `{app_name}`. "
        f"The app's Grafana dashboard uid is `{grafana_dash or 'kaiops-'+(app_name.lower().replace(' ','-'))}` "
        f"and its dashboard URL is `{grafana_url or 'not-configured'}`. "
        f"The app's Grafana alert rule uid (if any) is `{grafana_alert or 'not-configured'}`. "
        "Include in your report: the dashboard name/link/uid, any firing/alarming alert rules, "
        "and 2-3 Prometheus metrics (CPU/memory/error rate or pod restarts) that support your diagnosis. "
        "Use the exact dashboard URL above (never a placeholder like grafana.internal).\n"
        "After the RCA, send the summary to Slack with the status header "
        "[App_Name] Failed and tag SRE team if it is infra-related."
    )
    job_id = ""
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
        job_id = job["id"]
        logger.info(f"[ARGOCD] Created job {job_id} for {app_name}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[ARGOCD] create job failed: {e}")

    # Post the Slack alert: parent thread = status header + details + session link.
    # The detailed RCA is appended as a subthread reply when the worker completes.
    session_link = f"{FRONTEND_URL}/console/runtime-{job_id}" if job_id else ""
    details = {
        "cloud_provider": provider,
        "cluster": state.get("cluster") or os.environ.get("GKE_CLUSTER_NAME", ""),
        "namespace": state.get("namespace") or "default",
        "health": state.get("health"),
        "sync": state.get("sync"),
        "env": "production",
    }
    try:
        await report_app_status(
            app_name=app_name, status="Failed",
            detail=f"ArgoCD health: *{state.get('health')}* | sync: *{state.get('sync')}*.\n"
                   f"RCA in progress — the full report will follow in this thread.",
            cloud_provider=provider,
            session_link=session_link, details=details,
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"[ARGOCD] Slack report failed: {e}")


async def _handle_healthy(app_name: str, state: Dict[str, Any]) -> None:
    """Post/reply a healthy deploy confirmation in the app's thread."""
    from app.slack.reporter import report_app_status
    logger.info(f"[ARGOCD] HEALTHY: {app_name} health={state['health']} sync={state['sync']}")
    provider = "gcp"
    try:
        from app.applications.database_firestore import application_db
        app = application_db.get_application_by_name(app_name)
        provider = (app or {}).get("cloud_provider") or provider
    except Exception:  # noqa: BLE001
        pass
    details = {
        "cloud_provider": provider,
        "cluster": state.get("cluster") or os.environ.get("GKE_CLUSTER_NAME", ""),
        "namespace": state.get("namespace") or "default",
        "env": "production",
    }
    # Always resolve (and if needed create) a REAL KaiOps session for the app so
    # the console link never 404s. The canonical id is runtime-kaiops-{app_name}.
    session_link = ""
    try:
        from app.chat.agent_service import get_session_service
        svc = get_session_service()
        sess = svc.get_runtime_session_for_app(app_name)
        if not sess:
            sess = svc.ensure_app_session(app_name)
        session_link = f"{FRONTEND_URL}/console/{sess['id']}"
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ARGOCD] resolve runtime session for {app_name} failed: {e}")
    if not session_link:
        session_link = f"{FRONTEND_URL}/console/kaiops-{app_name}"
    try:
        await report_app_status(
            app_name=app_name, status="Healthy",
            detail="✅ Application deployed successfully.",
            cloud_provider=provider, details=details,
            session_link=session_link,
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"[ARGOCD] healthy report failed: {e}")
