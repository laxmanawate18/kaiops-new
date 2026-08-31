"""Grafana dashboard + alert-rule provisioning for KaiOps applications.

Every KaiOps-registered application gets a per-app Grafana dashboard (and a
Prometheus alert rule) so the RCA flow has a first-class observability surface
to reference. This module talks to the Grafana HTTP API directly (admin basic
auth) — the Grafana MCP server is read-only, so creation is done here.

Idempotent: if a dashboard/alert for an app already exists, it is skipped and
the existing uid is returned.
"""
import os
import json
import logging
import base64
import uuid

import requests

logger = logging.getLogger(__name__)

GRAFANA_URL = os.getenv("GRAFANA_URL", "").rstrip("/")
GRAFANA_USERNAME = os.getenv("GRAFANA_USERNAME", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_PASSWORD", "")
# The Prometheus datasource UID (discovered on first use).
_PROM_DS_UID = os.getenv("GRAFANA_PROM_DS_UID", "ffwg1nl67w4xsd")
KAI_OPS_FOLDER_UID = "kaiops"

# PromQL used to build per-app panels. Scoped by namespace (the app's k8s ns).
def _panel_exprs(namespace: str) -> dict:
    return {
        "cpu": f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[5m]))',
        "memory": f'sum(container_memory_working_set_bytes{{namespace="{namespace}"}})',
        "pods": f'count(kube_pod_status_phase{{namespace="{namespace}"}} and kube_pod_status_phase{{namespace="{namespace}"}})',
        "errors": f'sum(rate(container_cpu_usage_seconds_total{{namespace="{namespace}"}}[5m]))',  # placeholder
    }


def _headers() -> dict:
    auth = base64.b64encode(f"{GRAFANA_USERNAME}:{GRAFANA_PASSWORD}".encode()).decode()
    return {"Authorization": "Basic " + auth, "Content-Type": "application/json"}


def _grafana_reachable() -> bool:
    return bool(GRAFANA_URL and GRAFANA_PASSWORD)


def _discover_prom_uid() -> str:
    """Find the Prometheus datasource UID (idempotent, cached in module)."""
    global _PROM_DS_UID
    if _PROM_DS_UID:
        return _PROM_DS_UID
    try:
        r = requests.get(f"{GRAFANA_URL}/api/datasources", headers=_headers(), timeout=10)
        for ds in r.json():
            if ds.get("type") == "prometheus":
                _PROM_DS_UID = ds.get("uid")
                return _PROM_DS_UID
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[GRAFANA] discover prom datasource failed: {e}")
    return _PROM_DS_UID


def _ensure_kaiops_folder() -> str:
    """Create the KaiOps dashboard folder if missing; return its uid."""
    try:
        r = requests.get(f"{GRAFANA_URL}/api/folders", headers=_headers(), timeout=10)
        for f in r.json():
            if f.get("uid") == KAI_OPS_FOLDER_UID:
                return KAI_OPS_FOLDER_UID
    except Exception:  # noqa: BLE001
        pass
    try:
        r = requests.post(f"{GRAFANA_URL}/api/folders",
                          data=json.dumps({"title": "KaiOps", "uid": KAI_OPS_FOLDER_UID}),
                          headers=_headers(), timeout=10)
        if r.ok:
            return r.json().get("uid", KAI_OPS_FOLDER_UID)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[GRAFANA] create folder failed: {e}")
    return KAI_OPS_FOLDER_UID


def create_app_dashboard(app_name: str, namespace: str = "") -> str:
    """Create (or fetch) a per-app Grafana dashboard; return its uid.

    Idempotent by uid = `kaiops-{app_name}`. Returns "" on failure so callers
    degrade gracefully.
    """
    if not _grafana_reachable():
        logger.warning("[GRAFANA] not reachable; skipping dashboard")
        return ""
    uid = f"kaiops-{app_name}"
    title = f"KaiOps {app_name}"
    ds = _discover_prom_uid()
    try:
        # If it already exists, return the uid.
        check = requests.get(f"{GRAFANA_URL}/api/dashboards/uid/{uid}", headers=_headers(), timeout=10)
        if check.ok:
            return uid
    except Exception:  # noqa: BLE001
        pass

    folder_uid = _ensure_kaiops_folder()
    panel_common = {"datasource": {"type": "prometheus", "uid": ds},
                    "targets": [{"expr": "", "refId": "A", "datasource": {"type": "prometheus", "uid": ds}}]}
    panels = [
        {"id": 1, "title": "CPU Usage", "type": "timeseries", "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
         **panel_common, "targets": [{"expr": _panel_exprs(namespace)["cpu"], "refId": "A", "datasource": {"type": "prometheus", "uid": ds}}]},
        {"id": 2, "title": "Memory Usage", "type": "timeseries", "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
         **panel_common, "targets": [{"expr": _panel_exprs(namespace)["memory"], "refId": "A", "datasource": {"type": "prometheus", "uid": ds}}]},
        {"id": 3, "title": "Pods by Phase", "type": "stat", "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8},
         **panel_common, "targets": [{"expr": _panel_exprs(namespace)["pods"], "refId": "A", "datasource": {"type": "prometheus", "uid": ds}}]},
    ]
    dash = {
        "dashboard": {
            "uid": uid, "title": title, "tags": ["kaiops", app_name],
            "schemaVersion": 39, "version": 0, "timezone": "browser",
            "panels": panels, "templating": {"list": []},
            "annotations": {"list": []}, "editable": True,
            "refresh": "30s", "time": {"from": "now-1h", "to": "now"},
        },
        "overwrite": True,
        "folderUid": folder_uid,
    }
    try:
        r = requests.post(f"{GRAFANA_URL}/api/dashboards/db", data=json.dumps(dash),
                          headers=_headers(), timeout=15)
        if r.ok:
            logger.info(f"[GRAFANA] created dashboard '{title}' (uid={uid})")
            return uid
        logger.warning(f"[GRAFANA] dashboards/db failed: {r.status_code} {r.text[:200]}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[GRAFANA] create dashboard error: {e}")
    return ""


def create_app_alert(app_name: str, namespace: str = "") -> str:
    """Create a Prometheus alert rule for an app (fires when restarts/errors).

    Returns the rule UID, or "" on failure. Idempotent by title.
    Grafana 11 provisioning API requires the rule posted directly (not group
    wrapped), with a query chain: A = prometheus query, B = reduce, C = math
    (threshold), and ``condition`` = "C".
    """
    if not _grafana_reachable():
        return ""
    ds = _discover_prom_uid()
    title = f"KaiOps {app_name} App Down"
    try:
        r = requests.get(f"{GRAFANA_URL}/api/v1/provisioning/alert-rules", headers=_headers(), timeout=10)
        for rule in (r.json() or []):
            if rule.get("title") == title:
                return rule.get("uid", "")
    except Exception:  # noqa: BLE001
        pass

    expr = f'kube_pod_container_status_restarts_total{{namespace="{namespace}"}}'
    data = [
        {"refId": "A", "datasourceUid": ds, "relativeTimeRange": {"from": 5, "to": 0},
         "model": {"expr": expr, "refId": "A", "queryType": "range", "range": True,
                   "instant": False, "datasource": {"type": "prometheus", "uid": ds},
                   "intervalMs": 1000, "maxDataPoints": 43200, "legendFormat": "__auto"}},
        {"refId": "B", "datasourceUid": "__expr__", "relativeTimeRange": {"from": 0, "to": 0},
         "model": {"type": "reduce", "refId": "B", "expression": "A", "reducer": "last",
                   "datasource": {"type": "__expr__", "uid": "__expr__"}}},
        {"refId": "C", "datasourceUid": "__expr__", "relativeTimeRange": {"from": 0, "to": 0},
         "model": {"type": "math", "refId": "C", "expression": "B > 0",
                   "datasource": {"type": "__expr__", "uid": "__expr__"}}},
    ]
    rule = {
        "uid": f"kaiops-{app_name}-alert",
        "title": title,
        "condition": "C",
        "data": data,
        "noDataState": "NoData", "execErrState": "Error",
        "for": "1m", "annotations": {"summary": f"{app_name} restarts detected"},
        "labels": {"app": app_name, "severity": "critical", "kaiops": "true"},
        "folderUID": _ensure_kaiops_folder(),
        "orgID": 1, "ruleGroup": "kaiops", "ruleGroupInterval": "1m",
    }
    try:
        r = requests.post(f"{GRAFANA_URL}/api/v1/provisioning/alert-rules", data=json.dumps(rule),
                          headers=_headers(), timeout=15)
        if r.ok:
            logger.info(f"[GRAFANA] created alert '{title}'")
            return rule["uid"]
        logger.warning(f"[GRAFANA] create alert failed: {r.status_code} {r.text[:200]}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[GRAFANA] create alert error: {e}")
    return ""


def provision_app(app_name: str, namespace: str = "") -> dict:
    """Provision a Grafana dashboard + alert for an app; return metadata."""
    dash_uid = create_app_dashboard(app_name, namespace)
    alert_uid = create_app_alert(app_name, namespace)
    return {
        "grafana_dashboard": dash_uid,
        "grafana_dashboard_url": f"{GRAFANA_URL}/d/{dash_uid}" if dash_uid else "",
        "grafana_alert": alert_uid,
    }
