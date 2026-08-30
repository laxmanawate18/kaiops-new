"""Azure RCA data client — REAL Log Analytics (KQL) first, mock auto-fallback.

Flow per tool call:
  1. AZURE_MOCK_MODE=true  -> straight to demo mock (explicit override).
  2. Otherwise try the REAL Azure Monitor path (service principal from env:
     AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET):
       - pod logs / events / inventory / arbitrary KQL -> Log Analytics
       - ingress logs  -> App Gateway / ALB access-log tables (honest empty
         when the tables don't exist)
  3. Any failure (auth, network, malformed, empty-critical) -> fall back to
     the legacy mock so demos never break, tagged source='mock-fallback'.
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

AZURE_MOCK_MODE = os.getenv("AZURE_MOCK_MODE", "false").strip().lower() == "true"

_TENANT = os.getenv("AZURE_TENANT_ID", "")
_CLIENT = os.getenv("AZURE_CLIENT_ID", "")
_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
_WS_ID = os.getenv("AZURE_LOG_ANALYTICS_WORKSPACE_ID", "")
_SUB = os.getenv("AZURE_SUBSCRIPTION_ID", "")
_RG = os.getenv("AZURE_RESOURCE_GROUP", "")
_CLUSTER = os.getenv("AZURE_AKS_CLUSTER_NAME", "")

_TOKEN_CACHE: Dict[str, tuple] = {}  # scope -> (token, expires_at)
_LA_TIMEOUT = 20


# --------------------------------------------------------------------- auth
def _get_token(scope: str) -> Optional[str]:
    cached = _TOKEN_CACHE.get(scope)
    if cached and cached[1] > time.time() + 60:
        return cached[0]
    if not (_TENANT and _CLIENT and _SECRET):
        logger.warning("Azure SP env incomplete (tenant/client/secret)")
        return None
    try:
        r = requests.post(
            f"https://login.microsoftonline.com/{_TENANT}/oauth2/v2.0/token",
            data={"grant_type": "client_credentials", "client_id": _CLIENT,
                  "client_secret": _SECRET, "scope": scope},
            timeout=15,
        )
        j = r.json()
        tok = j.get("access_token")
        if not tok:
            logger.warning("Azure token error: %s", str(j.get("error_description", j))[:200])
            return None
        _TOKEN_CACHE[scope] = (tok, time.time() + 3300)
        return tok
    except Exception as e:  # noqa: BLE001
        logger.warning("Azure token request failed: %s", e)
        return None


def _kql(query: str, timespan: str = "P7D") -> Optional[List[Dict[str, Any]]]:
    """Run KQL against the workspace. Returns list of row dicts, None on failure."""
    tok = _get_token("https://api.loganalytics.io/.default")
    if not tok:
        return None
    try:
        r = requests.post(
            f"https://api.loganalytics.io/v1/workspaces/{_WS_ID}/query",
            headers={"Authorization": f"Bearer {tok}",
                     "Content-Type": "application/json"},
            json={"query": query, "timespan": timespan},
            timeout=_LA_TIMEOUT,
        )
        if not r.ok:
            logger.warning("LA query failed %s: %s", r.status_code, r.text[:200])
            return None
        table = (r.json().get("tables") or [{}])[0]
        cols = [c.get("name") for c in table.get("columns", [])]
        return [dict(zip(cols, row)) for row in table.get("rows", [])]
    except Exception as e:  # noqa: BLE001
        logger.warning("LA query exception: %s", e)
        return None


def _fallback(mock_fn, args: Dict[str, Any], source_tag: str):
    result = mock_fn(args)
    # Tag mock-fallback results so demo viewers know provenance.
    try:
        if isinstance(result, list) and result and isinstance(result[0], dict):
            for item in result[:1]:
                item["data_source"] = "mock-fallback"
        elif isinstance(result, dict):
            result["data_source"] = "mock-fallback"
    except Exception:  # noqa: BLE001
        pass
    logger.info("[AZURE] real path unavailable (%s) -> mock fallback", source_tag)
    return result


# ------------------------------------------------------------------ helpers
def _discover_pods(namespace_hint: str = "") -> List[Dict[str, str]]:
    """Distinct pods — ContainerLogV2 first (has PodName/PodNamespace), then
    KubePodInventory whose pod column is 'Name' and ns column is 'Namespace'."""
    cl2_ns = f"| where PodNamespace =~ '{namespace_hint}' " if namespace_hint else ""
    rows = _kql(
        "ContainerLogV2 "
        f"{cl2_ns}| where TimeGenerated > ago(7d) "
        "| summarize LastLog=max(TimeGenerated) by PodName, PodNamespace "
        "| top 100 by LastLog desc"
    )
    if rows:
        inv = {r.get("Name", ""): r for r in (_kql(
            "KubePodInventory | where TimeGenerated > ago(7d) "
            "| summarize arg_max(TimeGenerated, *) by Name, Namespace "
            "| project Name, Namespace, PodStatus, ContainerStatus, Computer, ContainerRestartCount "
            "| take 200"
        ) or [])}
        out = []
        for r in rows:
            inv_row = inv.get(r.get("PodName", ""), {})
            out.append({
                "pod_name": r.get("PodName", ""),
                "namespace": r.get("PodNamespace", ""),
                "status": inv_row.get("PodStatus") or inv_row.get("ContainerStatus") or "",
                "node": inv_row.get("Computer", ""),
                "restarts": inv_row.get("ContainerRestartCount", 0),
            })
        return out

    ki_ns = f"| where Namespace =~ '{namespace_hint}' " if namespace_hint else ""
    rows = _kql(
        "KubePodInventory "
        f"{ki_ns}| where TimeGenerated > ago(7d) "
        "| summarize arg_max(TimeGenerated, *) by Name, Namespace "
        "| project Name, Namespace, PodStatus, ContainerStatus, Computer "
        "| take 100"
    ) or []
    return [{"pod_name": r.get("Name", ""), "namespace": r.get("Namespace", ""),
             "status": r.get("PodStatus") or r.get("ContainerStatus") or "",
             "node": r.get("Computer", "")} for r in rows]


# ---------------------------------------------------------------- public API
def call_mcp_tool(tool_name: str, arguments: dict, use_cache: bool = True) -> Dict[str, Any]:
    """Compatibility shim for anything still using the old dispatcher shape."""
    fn = {
        "get_pod_logs": get_pod_logs,
        "get_pod_events": get_pod_events,
        "get_pod_description": get_pod_description,
        "query_log_analytics": query_log_analytics,
        "get_ingress_logs": get_ingress_logs,
    }.get(tool_name)
    if fn is None:
        return {"error": f"Unknown azure tool: {tool_name}"}
    try:
        data = fn(**(arguments or {}))
        return {"result": data}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def _pick_live_pods(token: str, limit: int = 3, exclude_ns=("kube-system", "aks-command", "app-routing-system")) -> List[Dict[str, Any]]:
    """Cluster-wide live pod discovery with fuzzy token matching against the
    registry-provided name — the registry often calls the app differently
    than the actual AKS pods (e.g. 'azure-to-do' vs 'todo-backend-…')."""
    import re as _re
    pods = _discover_pods() or []
    app_pods = [p for p in pods
                if p.get("pod_name") and p.get("namespace", "") not in exclude_ns
                and not str(p.get("pod_name", "")).startswith(("ama-", "oms", "metrics"))]
    tokens = [t for t in _re.split(r"[^a-z0-9]+", (token or "").lower()) if len(t) >= 4]
    scored = []
    for p in app_pods:
        pname = p["pod_name"].lower()
        score = sum(1 for t in tokens if t in pname)
        scored.append((score, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    # Prefer any token match; otherwise take the busiest/most relevant apps first.
    matched = [p for s, p in scored if s > 0]
    return (matched or [p for _, p in scored])[:limit]


def get_pod_logs(pod_name: str, namespace: str, lines: int = 100) -> List[str]:
    args = {"pod_name": pod_name, "namespace": namespace, "lines": lines}
    if AZURE_MOCK_MODE:
        return _mock_get_pod_logs(args)

    pod = pod_name or ""
    ns = namespace or ""
    rows = None
    if pod:
        rows = _kql(
            "ContainerLogV2 "
            f"| where PodName startswith '{pod}' "
            + (f"and PodNamespace =~ '{ns}' " if ns else "")
            + "| order by TimeGenerated desc "
            f"| take {int(lines)} | project TimeGenerated, LogMessage, PodName"
        )
    if rows is None:
        # Try inventory-first discovery (pod name may differ in AKS)
        pods = _discover_pods(ns)
        match = next((p for p in pods if p["pod_name"] and p["pod_name"].startswith(pod[:12])), None) if pods else None
        if match:
            rows = _kql(
                f"ContainerLogV2 | where PodName =~ '{match['pod_name']}' "
                f"| order by TimeGenerated desc | take {int(lines)} "
                "| project TimeGenerated, LogMessage, PodName"
            )
    # Registry/app-name mismatch: pull logs for the cluster's real live pods.
    if rows is not None and len(rows) == 0:
        live = _pick_live_pods(pod, limit=3)
        combined: List[str] = []
        per = max(5, int(lines) // max(1, len(live)))
        for p in live:
            prows = _kql(
                f"ContainerLogV2 | where PodName =~ '{p['pod_name']}' "
                f"| order by TimeGenerated desc | take {per} "
                "| project TimeGenerated, LogMessage, PodName"
            ) or []
            for r in reversed(prows):
                combined.append(f"[{r.get('TimeGenerated')}] [{p['pod_name']}] {r.get('LogMessage', '')}".rstrip())
        if combined:
            logger.info("[AZURE] get_pod_logs via live-discovery: %d lines across %d pods",
                        len(combined), len(live))
            return combined[:lines]
    if rows is None:
        return _fallback(_mock_get_pod_logs, args, "get_pod_logs")

    if not rows:
        logger.info("[AZURE] no ContainerLogV2 rows for %s (cluster quiet)", pod)
        return [f"[azure] No container log rows found in Log Analytics for pod '{pod_name}' in the last 7 days."]

    logs = [
        f"[{r.get('TimeGenerated')}] {r.get('LogMessage', '')}".rstrip()
        for r in reversed(rows)
    ]
    logger.info("[AZURE] get_pod_logs real: %d lines for %s", len(logs), pod)
    return logs[:lines]


def get_pod_events(pod_name: str, namespace: str) -> List[Dict[str, str]]:
    args = {"pod_name": pod_name, "namespace": namespace}
    if AZURE_MOCK_MODE:
        return _mock_get_pod_events(args)

    name = pod_name or ""
    rows = _kql(
        "KubeEvents "
        f"{('| where Name contains ' + chr(39) + (name[:20] or '~none~') + chr(39)) if name else ''} "
        "| order by TimeGenerated desc | take 30"
    )
    if rows is None:
        return _fallback(_mock_get_pod_events, args, "get_pod_events")

    events = [{
        "timestamp": str(r.get("TimeGenerated", "")),
        "name": str(r.get("Name", "") or r.get("ObjectKind", "") or ""),
        "reason": str(r.get("Reason", "") or ""),
        "message": str(r.get("Message", "") or ""),
    } for r in rows]
    if not events:
        return [{"name": pod_name, "reason": "NoRecentEvents",
                 "message": "No Kubernetes events found in Log Analytics (last 7 days).",
                 "data_source": "azure-loganalytics"}]
    logger.info("[AZURE] get_pod_events real: %d events for %s", len(events), name)
    return events


def get_pod_description(pod_name: str, namespace: str) -> Dict[str, Any]:
    args = {"pod_name": pod_name, "namespace": namespace}
    if AZURE_MOCK_MODE:
        return _mock_get_pod_describe(args)

    pod = pod_name or ""
    rows = _kql(
        "KubePodInventory "
        f"| where Name startswith '{pod}' "
        "| summarize arg_max(TimeGenerated, *) by Name, Namespace "
        "| project Name, Namespace, PodStatus, ContainerStatus, ContainerID, Computer, "
        "ContainerRestartCount, PodStartTime"
    )
    if rows is None:
        return _fallback(_mock_get_pod_describe, args, "get_pod_description")

    if not rows:
        # Registry/app-name mismatch — describe the cluster's real live pods.
        live = _pick_live_pods(pod, limit=3)
        if live:
            return {
                "requested_pod": pod,
                "data_source": "azure-loganalytics",
                "note": (f"Pod '{pod}' not found by that name in AKS; these are the "
                         "live application pods discovered via Log Analytics."),
                "pods": [
                    {"pod_name": p["pod_name"], "namespace": p["namespace"],
                     "status": p.get("status") or "Unknown", "node": p.get("node", ""),
                     "restarts": p.get("restarts", 0)}
                    for p in live
                ],
                "summary": (
                    f"{len(live)} live app pod(s) found: "
                    + ", ".join(f"{p['pod_name']} ({p.get('status') or 'Unknown'}, "
                                f"{p.get('restarts', 0)} restarts)" for p in live)
                ),
            }
        return {"error": f"Pod '{pod}' not found in AKS Log Analytics (KubePodInventory).",
                "data_source": "azure-loganalytics"}

    r = rows[0]
    real_name = r.get("Name", pod)
    real_ns = r.get("Namespace", namespace)
    describe = {
        "pod_name": real_name,
        "namespace": real_ns,
        "status": r.get("PodStatus") or r.get("ContainerStatus") or "Unknown",
        "node": r.get("Computer", ""),
        "restarts": r.get("ContainerRestartCount", 0),
        "container_id": r.get("ContainerID", ""),
        "pod_start_time": str(r.get("PodStartTime", "") or ""),
        "data_source": "azure-loganalytics",
        "summary": (
            "Derived from Azure Log Analytics KubePodInventory (not kubectl). "
            f"Pod {real_name} in {real_ns} is "
            f"{r.get('PodStatus') or r.get('ContainerStatus')}."
        ),
    }
    logger.info("[AZURE] get_pod_description real for %s", pod)
    return describe


def query_log_analytics(query: str, workspace_id: str = "", time_range: str = "1h") -> Dict[str, Any]:
    args = {"query": query, "workspace_id": workspace_id or _WS_ID, "time_range": time_range}
    if AZURE_MOCK_MODE:
        return _mock_query_log_analytics(args)

    ws = workspace_id or _WS_ID
    if not ws:
        return _fallback(_mock_query_log_analytics, args, "query_log_analytics(no workspace)")
    rows = _kql(query, timespan={"1h": "PT1H", "6h": "PT6H", "24h": "P1D"}.get(time_range, "PT1H"))
    if rows is None:
        return _fallback(_mock_query_log_analytics, args, "query_log_analytics")

    cols = list(rows[0].keys()) if rows else []
    logger.info("[AZURE] query_log_analytics real: %d rows", len(rows))
    return {"status": "success", "data_source": "azure-loganalytics",
            "row_count": len(rows), "columns": cols, "rows": rows[:50]}


def get_ingress_logs(workspace_id: str = "", lines: int = 50) -> List[Dict[str, str]]:
    args = {"workspace_id": workspace_id or _WS_ID, "lines": lines}
    if AZURE_MOCK_MODE:
        return _mock_get_ingress_logs(args)

    for table in ("AGCAccessLog", "AzureNetworkApplicationGatewayAccessLog",
                  "AzureLoadBalancerAccessLog"):
        rows = _kql(
            f"{table} | where TimeGenerated > ago(1h) "
            "| order by TimeGenerated desc "
            f"| take {int(lines)}"
        )
        if rows:
            out = [{
                "time": str(r.get("TimeGenerated", "")),
                "method": str(r.get("Method", r.get("httpMethod", "")) or ""),
                "path": str(r.get("Path", r.get("requestUri", "")) or ""),
                "status": str(r.get("Status", r.get("httpStatus_d", "")) or ""),
                "backend": str(r.get("Backend", r.get("backendHostName", "")) or ""),
                "data_source": f"azure-loganalytics:{table}",
            } for r in rows]
            logger.info("[AZURE] get_ingress_logs real via %s: %d rows", table, len(out))
            return out

    # No ingress log table populated — honest empty rather than fake 200s.
    return [{"time": "", "method": "", "path": "", "status": "N/A", "backend": "",
             "data_source": "azure-loganalytics",
             "message": ("No Application Gateway / Load Balancer access-log tables "
                         "found with data in Log Analytics (last 1h). Ingress logging "
                         "may not be enabled for this cluster.")}]


# ------------------------------------------------------------------- mocks
def _mock_get_pod_logs(arguments: dict) -> List[str]:
    pod = (arguments or {}).get("pod_name", "")
    ns = (arguments or {}).get("namespace", "kaiops-ns")
    if "backend" in pod or "api" in pod:
        return [
            f"[2024-11-24T10:15:23Z] INFO Starting {pod} application (demo data)",
            f"[2024-11-24T10:15:24Z] ERROR Exception in thread 'main' java.lang.OutOfMemoryError: Java heap space",
            f"[2024-11-24T10:15:25Z] FATAL Exiting due to OOM (demo fallback data)",
        ]
    return [f"[2024-11-24T10:15:2{i}Z] INFO {pod} healthy (demo data)" for i in range(3)]


def _mock_get_pod_events(arguments: dict) -> List[Dict[str, str]]:
    pod = (arguments or {}).get("pod_name", "demo-pod")
    return [{"name": pod, "reason": "BackOff",
             "message": "Demo fallback: Back-off restarting failed container (mock data).",
             "data_source": "mock-fallback"}]


def _mock_get_pod_describe(arguments: dict) -> Dict[str, Any]:
    pod = (arguments or {}).get("pod_name", "demo-pod")
    return {"pod_name": pod, "namespace": (arguments or {}).get("namespace", "demo"),
            "status": "CrashLoopBackOff", "restarts": 42,
            "summary": "Demo fallback describe (mock data).",
            "data_source": "mock-fallback"}


def _mock_query_log_analytics(arguments: dict) -> Dict[str, Any]:
    return {"status": "success", "data_source": "mock-fallback", "row_count": 0,
            "columns": [], "rows": [],
            "message": "Demo fallback: query not executed against real workspace."}


def _mock_get_ingress_logs(arguments: dict) -> List[Dict[str, str]]:
    return [{"time": "2024-11-24T10:15:23Z", "method": "GET", "path": "/api/health",
             "status": "200", "backend": "demo-backend", "data_source": "mock-fallback"}]
