"""
GCP Cloud Logging & Monitoring MCP Server

Standalone FastMCP server that wraps google-cloud-logging and
google-cloud-monitoring. Deployed to Cloud Run via mcp_proxy.py, exposing
tools over JSON-RPC.

Tools:
    get_pod_logs          - Fetch log entries from Cloud Logging for an app/pod
    get_cloud_monitoring  - Fetch Cloud Monitoring metric datapoints (CPU, mem, etc.)
    list_metrics          - List available Cloud Monitoring metric descriptors
    get_lb_logs           - Fetch Cloud Load Balancing access logs

Environment:
    GOOGLE_PROJECT_ID         - GCP project ID (required)
    GCP_CLUSTER_NAME          - GKE cluster name
    GCP_CLUSTER_ZONE          - GKE cluster zone
    GOOGLE_CLOUD_LOCATION     - Region (default us-central1)
    GCP_MOCK_MODE             - 'true' for mock/demo data (default: false)
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GCP_PROJECT_ID = os.getenv("GOOGLE_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
GCP_CLUSTER_NAME = os.getenv("GCP_CLUSTER_NAME", "log-agent-gke")
GCP_CLUSTER_ZONE = os.getenv("GCP_CLUSTER_ZONE", "us-central1-a")
GCP_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
GCP_MOCK_MODE = os.getenv("GCP_MOCK_MODE", "false").lower() == "true"

mcp = FastMCP("gcp-mcp-server")

# ---------------------------------------------------------------------------
# Client helpers (lazy-initialised)
# ---------------------------------------------------------------------------
_logging_client = None
_monitoring_client = None


def _get_credentials():
    """Resolve the GCP project + credentials from the environment (ADC)."""
    global GCP_PROJECT_ID
    from google.auth import default
    creds, project = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    if not GCP_PROJECT_ID:
        GCP_PROJECT_ID = project
    if not GCP_PROJECT_ID:
        raise RuntimeError("GOOGLE_PROJECT_ID / GOOGLE_CLOUD_PROJECT not set")
    return creds, GCP_PROJECT_ID


def _get_logging_client():
    global _logging_client
    if _logging_client is None:
        from google.cloud import logging as cloud_logging
        creds, project = _get_credentials()
        _logging_client = cloud_logging.Client(project=project, credentials=creds)
    return _logging_client


def _get_monitoring_client():
    global _monitoring_client
    if _monitoring_client is None:
        from google.cloud import monitoring_v3
        creds, project = _get_credentials()
        _monitoring_client = monitoring_v3.MetricServiceClient(credentials=creds)
    return _monitoring_client


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------
def _mock_logs(pod_name: str, namespace: str, lines: int) -> List[Dict[str, Any]]:
    """Return sample log entries for demos when GCP_MOCK_MODE is true."""
    entries = []
    now = datetime.utcnow()
    for i in range(min(lines, 20)):
        lvl = "ERROR" if i % 5 == 0 else "INFO"
        entries.append({
            "timestamp": (now - timedelta(seconds=i * 3)).isoformat() + "Z",
            "severity": lvl,
            "source": pod_name,
            "message": f"[{lvl}] {pod_name} (namespace={namespace}) sample log line {i}",
        })
    return entries


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@mcp.tool()
def get_pod_logs(pod_name: str, namespace: str = "", lines: int = 100) -> Dict[str, Any]:
    """Fetch log entries from Cloud Logging for a pod/application.

    Args:
        pod_name: The pod or application name to query logs for.
        namespace: Kubernetes namespace (optional).
        lines: Number of log lines to return (default 100).
    """
    if GCP_MOCK_MODE:
        return {"status": "success", "mock": True, "pod": pod_name,
                "namespace": namespace, "logs": _mock_logs(pod_name, namespace, lines)}

    try:
        client = _get_logging_client()
        filter_str = f'resource.labels.pod_name="{pod_name}"' if namespace else ""
        if namespace:
            filter_str += f' AND resource.labels.namespace_name="{namespace}"'
        entries = client.list_entries(filter_=filter_str, max_results=lines)
        logs = []
        for entry in entries:
            logs.append({
                "timestamp": getattr(entry.timestamp, "isoformat", lambda: str(entry.timestamp))() + "Z",
                "severity": getattr(entry, "severity", "INFO"),
                "source": getattr(entry, "resource", None),
                "message": entry.payload if isinstance(entry.payload, str) else json.dumps(entry.payload, default=str),
            })
        return {"status": "success", "pod": pod_name, "namespace": namespace,
                "log_count": len(logs), "logs": logs}
    except Exception as e:
        logger.warning(f"get_pod_logs failed: {e}")
        return {"status": "error", "error": str(e)}


@mcp.tool()
def get_cloud_monitoring(metric_type: str = "kubernetes.io/container/cpu/utilization",
                         resource_label: str = "", start_minutes: int = 15) -> Dict[str, Any]:
    """Fetch Cloud Monitoring datapoints for a metric over a recent window.

    Args:
        metric_type: The Monitoring metric type to query.
        resource_label: Optional label filter (e.g. pod name).
        start_minutes: Look-back window in minutes (default 15).
    """
    if GCP_MOCK_MODE:
        now = datetime.utcnow()
        pts = [{"time": (now - timedelta(minutes=i)).isoformat() + "Z",
                "value": round(0.4 + (i % 3) * 0.1, 2)} for i in range(10)]
        return {"status": "success", "mock": True, "metric": metric_type, "points": pts}

    try:
        client = _get_monitoring_client()
        from google.cloud.monitoring_v3 import TimeInterval, TimeSeries, TypedValue

        project_name = f"projects/{_get_credentials()[1]}"
        interval = TimeInterval(
            start_time=(datetime.utcnow() - timedelta(minutes=start_minutes)),
            end_time=datetime.utcnow(),
        )
        time_series = client.list_time_series(
            request={
                "name": project_name,
                "filter": f'metric.type="{metric_type}"',
                "interval": interval,
            }
        )
        points = []
        for ts in time_series:
            for pt in ts.points:
                points.append({
                    "resource": dict(ts.resource.labels),
                    "metric": dict(ts.metric.labels),
                    "time": pt.interval.start_time.isoformat() + "Z",
                    "value": pt.value.double_value,
                })
        return {"status": "success", "metric": metric_type,
                "points_returned": len(points), "points": points[:100]}
    except Exception as e:
        logger.warning(f"get_cloud_monitoring failed: {e}")
        return {"status": "error", "error": str(e)}


@mcp.tool()
def list_metrics() -> Dict[str, Any]:
    """List a subset of Cloud Monitoring metric descriptors available."""
    if GCP_MOCK_MODE:
        return {"status": "success", "mock": True,
                "metrics": ["kubernetes.io/container/cpu/utilization",
                            "kubernetes.io/container/memory/used_bytes",
                            "loadbalancing.googleapis.com/https/request_count"]}
    try:
        client = _get_monitoring_client()
        project_name = f"projects/{_get_credentials()[1]}"
        descriptors = client.list_metric_descriptors(name=project_name)
        metrics = [d.type for d in descriptors]
        return {"status": "success", "metric_count": len(metrics), "metrics": metrics[:200]}
    except Exception as e:
        logger.warning(f"list_metrics failed: {e}")
        return {"status": "error", "error": str(e)}


@mcp.tool()
def get_lb_logs(forwarding_rule: str = "", lines: int = 50) -> Dict[str, Any]:
    """Fetch Cloud Load Balancing access logs from Cloud Logging.

    Args:
        forwarding_rule: Optional forwarding rule name filter.
        lines: Number of log lines (default 50).
    """
    if GCP_MOCK_MODE:
        now = datetime.utcnow()
        return {"status": "success", "mock": True, "logs": [
            {"timestamp": (now - timedelta(seconds=i * 2)).isoformat() + "Z",
             "status": 200 if i % 4 != 0 else 500, "forwarding_rule": forwarding_rule or "default"}
            for i in range(min(lines, 10))
        ]}
    try:
        client = _get_logging_client()
        f = 'logName="projects/{}/logs/requests"' .format(_get_credentials()[1])
        filters = [f]
        if forwarding_rule:
            filters.append(f'jsonPayload.forwardingRule="{forwarding_rule}"')
        entries = client.list_entries(filter_=" AND ".join(filters), max_results=lines)
        logs = [{"timestamp": getattr(e.timestamp, "isoformat", lambda: str(e.timestamp))() + "Z",
                 "payload": e.payload if isinstance(e.payload, str) else json.dumps(e.payload, default=str)}
                for e in entries]
        return {"status": "success", "log_count": len(logs), "logs": logs}
    except Exception as e:
        logger.warning(f"get_lb_logs failed: {e}")
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    mcp.run()
