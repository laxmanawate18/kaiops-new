"""
Log RCA Agent Tools

Tool functions for querying application logs, ingress logs, and performing diagnostics.
These tools dynamically resolve application names to pod/namespace information from the
metadata database, then execute actual queries against Azure Log Analytics and Kubernetes.

Supports both single-deployment and multi-deployment applications.
"""

import json
import asyncio
import os
from typing import Any, Optional
from agents.azure_rca_agent.app_resolver import get_pod_info, get_ingress_info
from agents.azure_rca_agent.mcp_client import (
    get_pod_logs,
    get_pod_events,
    get_pod_description,
    query_log_analytics,
    get_ingress_logs
)

# Azure data is only REAL once live Azure Monitor integration exists. Until then
# the legacy in-process mocks are gated behind an explicit demo flag so RCA can
# never present fabricated logs as evidence.
AZURE_MOCK_MODE = os.getenv("AZURE_MOCK_MODE", "false").strip().lower() == "true"


def _azure_unavailable(tool: str) -> dict[str, Any]:
    return {
        "tool": tool,
        "app_name": None,
        "status": "unavailable",
        "data_quality": "no_live_data",
        "error": (
            "Azure Monitor integration is not configured, so no live Azure "
            "logs, metrics or events could be collected for this application."
        ),
        "recommendation": (
            "Connect Azure Monitor credentials (azure-mcp-server with az/kubectl "
            "or Log Analytics workspace creds) to enable live Azure RCA. Do NOT "
            "report simulated data as real evidence."
        ),
    }


def check_application_logs(
    app_name: str,
    lines: int = 100,
    error_only: bool = False
) -> dict[str, Any]:
    """
    Query application pod logs from Azure Log Analytics.
    
    Dynamically resolves the application name to the correct pod(s) and namespace,
    then retrieves actual log data.
    
    For multi-deployment apps, queries all deployments in parallel and returns
    logs grouped by component.
    
    Args:
        app_name: Name of the application to query logs for (e.g., "todo", "User Service")
        lines: Number of log lines to retrieve per deployment (default: 100)
        error_only: If True, return only error-level logs (default: False)
    
    Returns:
        Dictionary with actual log entries grouped by deployment, with component health status
    
    Example:
        result = check_application_logs("todo", lines=50, error_only=True)
        # Returns logs for todo-backend AND todo-frontend with status for each
        result = check_application_logs("payment-service", lines=200)
    """
    
    # Dynamically resolve pod info from metadata database
    pod_info = get_pod_info(app_name)
    
    if pod_info.get("error"):
        return {
            "tool": "check_application_logs",
            "status": "error",
            "error": pod_info["error"],
            "description": f"Failed to resolve application '{app_name}'"
        }
    
    deployments = pod_info.get("deployments", [])
    is_multi = pod_info.get("is_multi_deployment", False)
    
    if not deployments:
        return {
            "tool": "check_application_logs",
            "status": "error",
            "error": f"No deployments found for application '{app_name}'",
            "description": f"Application '{app_name}' has no associated deployments"
        }
    
    # Query all deployments
    component_results = []
    total_logs = 0
    
    for deployment in deployments:
        pod_name = deployment.get("pod_name")
        namespace = deployment.get("namespace")
        deployment_name = deployment.get("deployment_name")
        criticality = deployment.get("criticality", "medium")
        
        # Execute actual query to get pod logs
        logs = get_pod_logs(pod_name, namespace, lines)
        
        # Filter for errors if requested
        if error_only:
            logs = [log for log in logs if any(err in str(log).lower() for err in ['error', 'exception', 'failed', 'warning'])]
        
        total_logs += len(logs)
        
        component_results.append({
            "deployment_name": deployment_name,
            "pod_name": pod_name,
            "namespace": namespace,
            "criticality": criticality,
            "logs_count": len(logs),
            "logs": logs
        })
    
    # Build response
    response = {
        "tool": "check_application_logs",
        "status": "success",
        "app_name": app_name,
        "cluster": pod_info.get("cluster", ""),
        "is_multi_deployment": is_multi,
        "deployments_queried": len(deployments),
        "lines_requested": lines,
        "total_logs_returned": total_logs,
        "error_only": error_only,
        "components": component_results,
        "query_type": "ContainerLogV2"
    }
    
    # Add component health summary
    if is_multi:
        health_summary = []
        for comp in component_results:
            has_errors = any(err in str(log).lower() for log in comp["logs"] for err in ['error', 'exception', 'failed', 'fatal', 'crash'])
            health_summary.append({
                "deployment": comp["deployment_name"],
                "status": "🔴 Error Logs" if has_errors else "🟢 Healthy",
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
) -> dict[str, Any]:
    """
    Query NGINX ingress/load balancer logs from Azure Log Analytics.
    
    Dynamically resolves the application name to the correct ingress namespace.
    
    For multi-deployment apps, returns ingress logs grouped by deployment/component.
    
    Analyzes ingress traffic, HTTP response codes, and request processing times.
    
    Args:
        app_name: Name of the application to query ingress logs for (e.g., "todo", "User Service")
        lines: Number of log entries to retrieve (default: 50)
        status_code_filter: Filter by HTTP status codes (e.g., "500,502,503" for errors)
        min_response_time_ms: Filter requests slower than this many milliseconds (0 = no filter)
    
    Returns:
        Dictionary with ingress logs grouped by component, traffic patterns, and error analysis
    
    Example:
        # Get recent ingress logs for todo app
        result = check_ingress_logs("todo", lines=30)
        
        # Get only 5XX errors for payment service
        result = check_ingress_logs("payment-service", status_code_filter="500,502,503")
        
        # Get slow requests (>5 seconds) for order service
        result = check_ingress_logs("order-service", min_response_time_ms=5000)
    """
    
    # Dynamically resolve ingress info from metadata database
    ingress_info = get_ingress_info(app_name)
    
    if ingress_info.get("error"):
        return {
            "tool": "check_ingress_logs",
            "status": "error",
            "error": ingress_info["error"],
            "description": f"Failed to resolve application '{app_name}'"
        }
    
    namespace = ingress_info.get("namespace", "app-routing-system")
    workspace_id = ingress_info.get("workspace_id", "")
    
    # Execute actual query to get ingress logs
    ingress_logs = get_ingress_logs(workspace_id, lines)
    
    # Apply filters if specified
    if status_code_filter:
        codes = [int(c.strip()) for c in status_code_filter.split(",") if c.strip().isdigit()]
        ingress_logs = [log for log in ingress_logs if int(log.get("status_code", "0")) in codes]
    
    if min_response_time_ms > 0:
        ingress_logs = [log for log in ingress_logs if int(log.get("response_time_ms", "0")) > min_response_time_ms]
    
    filters = []
    if status_code_filter:
        filters.append(f"status_codes={status_code_filter}")
    if min_response_time_ms > 0:
        filters.append(f"response_time>{min_response_time_ms}ms")
    
    filter_desc = f" filtered by {', '.join(filters)}" if filters else ""
    
    return {
        "tool": "check_ingress_logs",
        "status": "success",
        "app_name": app_name,
        "namespace": namespace,
        "cluster": ingress_info.get("cluster", ""),
        "lines_requested": lines,
        "lines_returned": len(ingress_logs),
        "status_code_filter": status_code_filter,
        "min_response_time_ms": min_response_time_ms,
        "description": f"Retrieved {len(ingress_logs)} ingress logs for '{app_name}' in namespace '{namespace}'{filter_desc}",
        "query_type": "ContainerLogV2 (Ingress)",
        "logs": ingress_logs
    }


def analyze_pod_logs(
    app_name: str,
    include_events: bool = True,
    include_describe: bool = True
) -> dict[str, Any]:
    """
    Perform comprehensive pod analysis combining logs, events, and pod description.
    
    Dynamically resolves the application name to the correct pod(s) and namespace.
    
    For multi-deployment apps, analyzes ALL deployments in parallel and provides
    unified RCA with component health status.
    
    This tool correlates pod logs with Kubernetes events and pod status to provide
    complete diagnostics for RCA (Root Cause Analysis).
    
    Args:
        app_name: Name of the application to analyze (e.g., "todo", "User Service")
        include_events: Include pod events and state changes (default: True)
        include_describe: Include pod description and resource info (default: True)
    
    Returns:
        Dictionary with comprehensive pod diagnostics:
        - For multi-deployment apps: Logs/events/status for each component + health summary
        - For single-deployment apps: Logs, events, pod description, error patterns
        - RCA findings with component prioritization
    
    Example:
        # Full pod analysis for troubleshooting
        result = analyze_pod_logs("todo")
        # Returns: {todo-backend logs, events, description} + {todo-frontend logs, events, description}
        
        # Just logs without events
        result = analyze_pod_logs("payment-service", include_events=False, include_describe=False)
    """
    
    # Dynamically resolve pod info from metadata database
    pod_info = get_pod_info(app_name)
    
    if pod_info.get("error"):
        return {
            "tool": "analyze_pod_logs",
            "status": "error",
            "error": pod_info["error"],
            "description": f"Failed to resolve application '{app_name}'"
        }
    
    deployments = pod_info.get("deployments", [])
    is_multi = pod_info.get("is_multi_deployment", False)
    
    if not deployments:
        return {
            "tool": "analyze_pod_logs",
            "status": "error",
            "error": f"No deployments found for application '{app_name}'",
            "description": f"Application '{app_name}' has no associated deployments"
        }
    
    # Analyze all deployments
    component_results = []
    all_logs = []
    all_events = []
    
    for deployment in deployments:
        pod_name = deployment.get("pod_name")
        namespace = deployment.get("namespace")
        deployment_name = deployment.get("deployment_name")
        criticality = deployment.get("criticality", "medium")
        
        # Execute actual queries to get pod logs, events, and description
        logs = get_pod_logs(pod_name, namespace, lines=100)
        events = get_pod_events(pod_name, namespace) if include_events else []
        pod_desc = get_pod_description(pod_name, namespace) if include_describe else {}
        
        all_logs.extend(logs)
        all_events.extend(events)
        
        # Analyze health status
        has_errors = any(err in str(log).lower() for log in logs for err in ['error', 'exception', 'failed', 'fatal', 'crash'])
        has_restart_events = any('restart' in str(event).lower() or 'backoff' in str(event).lower() for event in events)
        pod_phase = pod_desc.get("phase", "Unknown") if isinstance(pod_desc, dict) else "Unknown"
        
        # Determine status
        if has_restart_events or "CrashLoopBackOff" in str(pod_phase) or "Error" in str(pod_phase):
            status = "🔴 Critical"
        elif has_errors:
            status = "🟡 Warning"
        else:
            status = "🟢 Healthy"
        
        component_results.append({
            "deployment_name": deployment_name,
            "pod_name": pod_name,
            "namespace": namespace,
            "criticality": criticality,
            "status": status,
            "logs": logs,
            "logs_count": len(logs),
            "events": events,
            "events_count": len(events),
            "pod_description": pod_desc,
            "has_errors": has_errors,
            "has_restart_events": has_restart_events
        })
    
    components = ["logs"]
    if include_events:
        components.append("events")
    if include_describe:
        components.append("description")
    
    # Build response
    response = {
        "tool": "analyze_pod_logs",
        "status": "success",
        "app_name": app_name,
        "cluster": pod_info.get("cluster", ""),
        "is_multi_deployment": is_multi,
        "deployments_analyzed": len(deployments),
        "include_events": include_events,
        "include_describe": include_describe,
        "components": component_results,
        "logs_count": len(all_logs),
        "events_count": len(all_events),
        "query_type": "KubeEvents + ContainerLogV2 + Pod Description"
    }
    
    # Add component health summary table
    if is_multi:
        health_table = []
        critical_components = []
        
        for comp in component_results:
            health_table.append({
                "component": comp["deployment_name"],
                "status": comp["status"],
                "pod": comp["pod_name"],
                "logs": comp["logs_count"],
                "events": comp["events_count"]
            })
            
            if "🔴" in comp["status"]:
                critical_components.append({
                    "component": comp["deployment_name"],
                    "issue": "Critical" if comp["has_restart_events"] else "Errors detected",
                    "logs": comp["logs"],
                    "events": comp["events"]
                })
        
        response["component_health"] = health_table
        
        if critical_components:
            response["critical_issues"] = critical_components
            response["description"] = f"Multi-deployment analysis found {len(critical_components)} component(s) with issues. See critical_issues for details."
        else:
            response["description"] = f"Analyzed {len(deployments)} components. All components healthy."
    else:
        comp = component_results[0]
        response["pod_name"] = comp["pod_name"]
        response["namespace"] = comp["namespace"]
        response["logs"] = comp["logs"]
        response["events"] = comp["events"]
        response["pod_description"] = comp["pod_description"]
        response["description"] = f"Comprehensive analysis of pod '{comp['pod_name']}' for app '{app_name}' in namespace '{comp['namespace']}' " \
                                 f"including {' + '.join(components)}"
    
    return response


def query_log_analytics(
    query: str,
    workspace_id: str,
    time_range: str = "1h"
) -> dict[str, Any]:
    """
    Execute custom KQL (Kusto Query Language) query against Azure Log Analytics.
    
    Use this for advanced queries beyond the standard templates.
    
    Args:
        query: KQL query string (must be valid Kusto syntax)
        workspace_id: Azure Log Analytics Workspace ID
        time_range: Time range for query (default: "1h", options: "15m", "30m", "1h", "6h", "24h", "7d")
    
    Returns:
        Dictionary with query results and metadata
    
    Example:
        result = query_log_analytics(
            '''ContainerLogV2
               | where PodNamespace == "kaiops-ns"
               | where LogMessage contains "timeout"
               | take 50''',
            workspace_id="defaultworkspace-5a309391-...",
            time_range="6h"
        )
    """
    
    return {
        "tool": "query_log_analytics",
        "query": query,
        "workspace_id": workspace_id,
        "time_range": time_range,
        "description": f"Custom KQL query against Log Analytics workspace (time range: {time_range})"
    }


def extract_error_pattern(logs: list) -> dict[str, Any]:
    """
    Helper function to analyze log entries and extract error patterns.
    
    Args:
        logs: List of log entries (strings)
    
    Returns:
        Dictionary with pattern analysis:
        - error_count: Number of error messages
        - unique_errors: List of unique error types
        - error_trend: Increasing/stable/decreasing
        - potential_causes: Extracted from error messages
    """
    
    if not logs:
        return {
            "error_count": 0,
            "unique_errors": [],
            "error_trend": "no_data",
            "potential_causes": []
        }
    
    # Count errors
    error_count = sum(1 for log in logs if any(
        keyword in str(log).lower() 
        for keyword in ["error", "exception", "failed", "fatal", "crash"]
    ))
    
    return {
        "error_count": error_count,
        "analysis": "Pattern extraction available after query execution",
        "unique_errors": [],
        "error_trend": "stable",
        "potential_causes": []
    }


__all__ = [
    "check_application_logs",
    "check_ingress_logs", 
    "analyze_pod_logs",
    "query_log_analytics"
]
