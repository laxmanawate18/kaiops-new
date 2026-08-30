"""
GCP RCA Agent Tools

Tool functions for querying Cloud Logging, Cloud Monitoring metrics, and performing GKE diagnostics.
These tools dynamically resolve application names to pod/namespace information from the
metadata database, then execute actual queries against GCP APIs.

Supports both single-deployment and multi-deployment GKE applications.
"""

import logging
from typing import Any, Dict
from agents.gcp_rca_agent.app_resolver import get_pod_info, get_ingress_info
from agents.gcp_rca_agent.mcp_client import (
    GCPLoggingClient,
    GCPMonitoringClient,
    GCPLoadBalancerClient
)
from agents.gcp_rca_agent.config import GCPConfig

logger = logging.getLogger(__name__)


def check_application_logs(
    app_name: str,
    lines: int = 100,
    error_only: bool = False
) -> Dict[str, Any]:
    """
    Query application pod logs from Google Cloud Logging.
    
    Dynamically resolves the application name to the correct pod(s) and namespace,
    then retrieves actual log data from Cloud Logging.
    
    For multi-deployment apps, queries all deployments and returns
    logs grouped by component.
    
    Args:
        app_name: Name of the application to query logs for (e.g., "gcptodoapp")
        lines: Number of log lines to retrieve per deployment (default: 100)
        error_only: If True, return only error-level logs (default: False)
    
    Returns:
        Dictionary with actual log entries grouped by deployment, with component health status
    
    Example:
        result = check_application_logs("gcptodoapp", lines=50, error_only=True)
        # Returns logs for all gcptodoapp deployments with status for each
    """
    
    # Dynamically resolve pod info from metadata database
    pod_info = get_pod_info(app_name)
    
    if pod_info.get("error"):
        return {
            "tool": "check_application_logs",
            "status": "error",
            "error": pod_info["error"],
            "description": f"Failed to resolve application '{app_name}' in GCP metadata"
        }
    
    deployments = pod_info.get("deployments", [])
    is_multi = pod_info.get("is_multi_deployment", False)
    
    if not deployments:
        return {
            "tool": "check_application_logs",
            "status": "error",
            "error": f"No deployments found for application '{app_name}'",
            "description": f"Application '{app_name}' has no associated GKE deployments"
        }
    
    # Query all deployments
    component_results = []
    total_logs = 0
    
    for deployment in deployments:
        pod_name = deployment.get("pod_name")
        namespace = deployment.get("namespace", "default")
        deployment_name = deployment.get("deployment_name")
        criticality = deployment.get("criticality", "medium")
        
        # Use deployment_name for search if available (more reliable for finding pods)
        # Metadata might have placeholder pod names like "todo-frontend-xxx"
        search_pod_name = deployment_name if deployment_name and deployment_name != "unknown" else pod_name
        
        # Execute actual query to get pod logs from Cloud Logging
        logs_result = GCPLoggingClient.get_log_entries(
            pod_name=search_pod_name,
            namespace=namespace,
            lines=lines,
            error_only=error_only
        )
        
        logs = logs_result.get("logs", []) if logs_result.get("status") == "success" else []
        total_logs += len(logs)
        
        # Detect errors in logs
        has_errors = any(
            log.get("severity") in ["ERROR", "CRITICAL", "EMERGENCY"] 
            for log in logs
        )
        
        component_results.append({
            "deployment_name": deployment_name,
            "pod_name": pod_name,
            "namespace": namespace,
            "criticality": criticality,
            "logs_count": len(logs),
            "logs": logs,
            "has_errors": has_errors
        })
    
    # Build response
    response = {
        "tool": "check_application_logs",
        "status": "success",
        "app_name": app_name,
        "gke_cluster": pod_info.get("gke_cluster", GCPConfig.get_cluster_name()),
        "is_multi_deployment": is_multi,
        "deployments_queried": len(deployments),
        "lines_requested": lines,
        "total_logs_returned": total_logs,
        "error_only": error_only,
        "components": component_results,
        "query_type": "Cloud Logging"
    }
    
    # Add component health summary
    if is_multi:
        health_summary = []
        for comp in component_results:
            status = "🔴 Error Logs" if comp["has_errors"] else "🟢 Healthy"
            health_summary.append({
                "deployment": comp["deployment_name"],
                "status": status,
                "log_count": comp["logs_count"]
            })
        response["component_health"] = health_summary
        response["description"] = f"Retrieved logs from {len(deployments)} components. See component_health for summary."
    else:
        response["description"] = f"Retrieved {total_logs} log lines from pod '{component_results[0]['pod_name']}'" \
                                 f"{' (errors only)' if error_only else ''}"
    
    return response


def check_ingress_logs(
    app_name: str,
    lines: int = 50,
    status_code_filter: str = "",
    min_response_time_ms: int = 0
) -> Dict[str, Any]:
    """
    Query Cloud Load Balancer logs from Cloud Logging.
    
    Analyzes ingress traffic, HTTP response codes, and request processing times.
    
    Args:
        app_name: Name of the application to query ingress logs for
        lines: Number of log entries to retrieve (default: 50)
        status_code_filter: Filter by HTTP status codes (e.g., "500,502,503" for errors)
        min_response_time_ms: Filter requests slower than this many milliseconds (0 = no filter)
    
    Returns:
        Dictionary with ingress logs, traffic patterns, and error analysis
    
    Example:
        # Get recent ingress logs
        result = check_ingress_logs("gcptodoapp", lines=30)
        
        # Get only 5XX errors
        result = check_ingress_logs("gcptodoapp", status_code_filter="500,502,503")
    """
    
    # Check if LB logs are enabled
    if not GCPConfig.GCP_LB_LOGS_ENABLED:
        return {
            "tool": "check_ingress_logs",
            "status": "info",
            "message": "Load Balancer logging is not enabled for this project",
            "description": "Set GCP_LB_LOGS_ENABLED=true in .env to enable"
        }
    
    # Dynamically resolve ingress info from metadata database
    ingress_info = get_ingress_info(app_name)
    
    if ingress_info.get("error"):
        return {
            "tool": "check_ingress_logs",
            "status": "error",
            "error": ingress_info["error"],
            "description": f"Failed to resolve application '{app_name}'"
        }
    
    # Execute actual query to get ingress logs
    lb_logs_result = GCPLoadBalancerClient.get_load_balancer_logs(
        lines=lines,
        status_code_filter=status_code_filter,
        min_response_time_ms=min_response_time_ms
    )
    
    if lb_logs_result.get("status") != "success":
        return {
            "tool": "check_ingress_logs",
            "status": "error",
            "error": lb_logs_result.get("error", "Unknown error"),
            "description": "Failed to retrieve Load Balancer logs"
        }
    
    logs = lb_logs_result.get("logs", [])
    
    # Build filter description
    filters = []
    if status_code_filter:
        filters.append(f"status codes: {status_code_filter}")
    if min_response_time_ms > 0:
        filters.append(f"response time > {min_response_time_ms}ms")
    
    # Analyze traffic patterns
    status_counts = {}
    total_latency = 0
    for log in logs:
        status = str(log.get("status", 0))
        status_counts[status] = status_counts.get(status, 0) + 1
        total_latency += log.get("latency_ms", 0)
    
    avg_latency = total_latency / len(logs) if logs else 0
    
    response = {
        "tool": "check_ingress_logs",
        "status": "success",
        "app_name": app_name,
        "gke_cluster": ingress_info.get("gke_cluster", ""),
        "log_count": len(logs),
        "logs": logs,
        "filters_applied": filters if filters else ["none"],
        "traffic_summary": {
            "status_code_distribution": status_counts,
            "average_latency_ms": round(avg_latency, 2),
            "total_requests": len(logs)
        },
        "query_type": "Cloud Load Balancer Logs"
    }
    
    # Add health assessment
    error_count = sum(count for code, count in status_counts.items() if code.startswith("5"))
    if error_count > 0:
        error_rate = (error_count / len(logs)) * 100 if logs else 0
        response["health_assessment"] = {
            "status": "🔴 Unhealthy" if error_rate > 10 else "🟡 Warning",
            "error_rate_percent": round(error_rate, 2),
            "error_count": error_count
        }
    else:
        response["health_assessment"] = {
            "status": "🟢 Healthy",
            "error_rate_percent": 0,
            "error_count": 0
        }
    
    return response


def analyze_pod_logs(
    app_name: str,
    include_metrics: bool = True,
    include_events: bool = True
) -> Dict[str, Any]:
    """
    Comprehensive RCA analysis: logs + metrics + health status.
    
    Performs full root cause analysis including:
    - Pod logs from Cloud Logging
    - CPU/Memory metrics from Cloud Monitoring
    - Health status per component
    
    For multi-deployment apps, analyzes all components and identifies critical issues.
    
    Args:
        app_name: Name of the application to analyze (e.g., "gcptodoapp")
        include_metrics: Include Cloud Monitoring CPU/Memory metrics (default: True)
        include_events: Include pod events analysis (default: True)
    
    Returns:
        Comprehensive RCA data with logs, metrics, health status, and critical issues
    
    Example:
        result = analyze_pod_logs("gcptodoapp")
        # Returns full RCA with component_health table and critical_issues
    """
    
    # Resolve pod info
    pod_info = get_pod_info(app_name)
    
    if pod_info.get("error"):
        return {
            "tool": "analyze_pod_logs",
            "status": "error",
            "error": pod_info["error"],
            "description": f"Failed to resolve application '{app_name}' in GCP metadata"
        }
    
    deployments = pod_info.get("deployments", [])
    is_multi_deployment = pod_info.get("is_multi_deployment", False)
    
    # Analyze each deployment
    components = []
    component_health = []
    critical_issues = []
    
    for deployment in deployments:
        pod_name = deployment.get("pod_name")
        namespace = deployment.get("namespace", "default")
        deployment_name = deployment.get("deployment_name")
        criticality = deployment.get("criticality", "normal")
        
        # Use deployment_name for search if available (more reliable for finding pods)
        search_pod_name = deployment_name if deployment_name and deployment_name != "unknown" else pod_name
        
        # Get logs from Cloud Logging (this also caches container_name)
        logs_result = GCPLoggingClient.get_log_entries(
            pod_name=search_pod_name,
            namespace=namespace,
            lines=100
        )
        
        logs = logs_result.get("logs", []) if logs_result.get("status") == "success" else []
        has_errors = any(log.get("severity") in ["ERROR", "CRITICAL", "EMERGENCY"] for log in logs)
        
        # Extract container_name from logs for faster metric queries
        container_name = logs_result.get("container_name")
        
        # Get metrics if requested
        metrics = {}
        if include_metrics and GCPConfig.GCP_MONITORING_ENABLED:
            metrics_result = GCPMonitoringClient.get_monitoring_metrics(
                pod_name=search_pod_name,
                namespace=namespace,
                container_name=container_name  # Pass container_name for direct lookup
            )
            
            if metrics_result.get("status") == "success":
                metrics = {
                    "cpu_usage_percent": metrics_result.get("cpu_usage_percent", 0),
                    "memory_usage_percent": metrics_result.get("memory_usage_percent", 0)
                }
        
        # Determine health status (multi-factor)
        has_high_cpu = metrics.get("cpu_usage_percent", 0) > 90
        has_high_memory = metrics.get("memory_usage_percent", 0) > 90
        
        if has_errors or has_high_cpu or has_high_memory:
            status = "Critical"
            health_symbol = "🔴"
        elif metrics.get("cpu_usage_percent", 0) > 70 or metrics.get("memory_usage_percent", 0) > 70:
            status = "Warning"
            health_symbol = "🟡"
        else:
            status = "Healthy"
            health_symbol = "🟢"
        
        # Build component data
        component_data = {
            "deployment_name": deployment_name,
            "pod_name": pod_name,
            "namespace": namespace,
            "criticality": criticality,
            "status": status,
            "health_symbol": health_symbol,
            "logs_count": len(logs),
            "logs": logs[:20],  # Limit to 20 most recent
            "has_errors": has_errors,
            "metrics": metrics
        }
        
        components.append(component_data)
        
        # Add to health summary
        component_health.append({
            "deployment": deployment_name,
            "status": f"{health_symbol} {status}",
            "cpu_percent": metrics.get("cpu_usage_percent", 0),
            "memory_percent": metrics.get("memory_usage_percent", 0),
            "logs": len(logs),
            "has_errors": has_errors
        })
        
        # Track critical issues
        if status == "Critical":
            critical_issues.append({
                "deployment": deployment_name,
                "issues": [],
                "logs": logs[:10]  # Include recent logs for context
            })
            
            if has_errors:
                critical_issues[-1]["issues"].append("Error logs detected")
            if has_high_cpu:
                critical_issues[-1]["issues"].append(f"High CPU: {metrics.get('cpu_usage_percent', 0):.1f}%")
            if has_high_memory:
                critical_issues[-1]["issues"].append(f"High Memory: {metrics.get('memory_usage_percent', 0):.1f}%")
    
    # Build response
    response = {
        "tool": "analyze_pod_logs",
        "status": "success",
        "app_name": app_name,
        "gke_cluster": pod_info.get("gke_cluster", GCPConfig.get_cluster_name()),
        "is_multi_deployment": is_multi_deployment,
        "deployments_analyzed": len(deployments),
        "components": components,
        "component_health": component_health,
        "critical_issues": critical_issues,
        "gcp_project_id": GCPConfig.get_project_id(),
        "query_type": "Cloud Logging + Cloud Monitoring"
    }
    
    # Add summary
    critical_count = len([c for c in component_health if "Critical" in c["status"]])
    warning_count = len([c for c in component_health if "Warning" in c["status"]])
    healthy_count = len([c for c in component_health if "Healthy" in c["status"]])
    
    response["summary"] = {
        "total_components": len(components),
        "critical": critical_count,
        "warning": warning_count,
        "healthy": healthy_count,
        "overall_status": "🔴 Critical" if critical_count > 0 else ("🟡 Warning" if warning_count > 0 else "🟢 Healthy")
    }
    
    if is_multi_deployment:
        response["description"] = f"Analyzed {len(deployments)} components. " \
                                  f"{critical_count} critical, {warning_count} warning, {healthy_count} healthy."
    else:
        response["description"] = f"Analyzed deployment '{deployments[0]['deployment_name']}'. " \
                                  f"Status: {response['summary']['overall_status']}"
    
    return response


async def restart_pod(pod_name: str, namespace: str = "default", app_name: str = "") -> str:
    """
    Restart a pod by deleting it (its controller recreates it).
    DESTRUCTIVE: requires user confirmation via the HITL gate.

    Cloud-aware: if ``app_name`` is provided, the action is dispatched to the
    application's cloud (gcp/aws/azure) via the multi-cloud executor; otherwise
    it falls back to the GKE implementation (back-compat).
    """
    import asyncio
    if app_name:
        from agents.executor import execute
        # kubernetes/cloud clients are blocking; run in a thread.
        return await asyncio.to_thread(execute, app_name, "restart", namespace, pod_name, "")
    from agents.k8s_executor import restart_pod_real
    # kubernetes client is blocking; run in a thread so we don't block the loop
    return await asyncio.to_thread(restart_pod_real, pod_name, namespace)


__all__ = [
    "check_application_logs",
    "check_ingress_logs",
    "analyze_pod_logs",
    "restart_pod"
]
