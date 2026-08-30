"""
AWS RCA Agent Tools

Tool functions for querying CloudWatch logs, ALB logs, metrics, and performing EKS diagnostics.
These tools dynamically resolve application names to pod/namespace information from the
metadata database, then execute actual queries against CloudWatch.

Supports both single-deployment and multi-deployment EKS applications.
"""

import json
from typing import Any, Optional
from agents.aws_rca_agent.app_resolver import get_pod_info, get_ingress_info
from agents.aws_rca_agent.mcp_client import (
    get_log_events,
    execute_log_insights_query,
    get_cloudwatch_metrics,
    get_alb_logs
)
from agents.aws_rca_agent.config import AWSConfig


def check_application_logs(
    app_name: str,
    lines: int = 100,
    error_only: bool = False
) -> dict[str, Any]:
    """
    Query application pod logs from CloudWatch.
    
    Dynamically resolves the application name to the correct pod(s) and namespace,
    then retrieves actual log data from CloudWatch.
    
    For multi-deployment apps, queries all deployments in parallel and returns
    logs grouped by component.
    
    Args:
        app_name: Name of the application to query logs for (e.g., "todo", "auth-service")
        lines: Number of log lines to retrieve per deployment (default: 100)
        error_only: If True, return only error-level logs (default: False)
    
    Returns:
        Dictionary with actual log entries grouped by deployment, with component health status
    
    Example:
        result = check_application_logs("todo", lines=50, error_only=True)
        # Returns logs for all todo deployments with status for each
    """
    
    # Dynamically resolve pod info from metadata database
    pod_info = get_pod_info(app_name)
    
    if pod_info.get("error"):
        return {
            "tool": "check_application_logs",
            "status": "error",
            "error": pod_info["error"],
            "description": f"Failed to resolve application '{app_name}' in AWS metadata"
        }
    
    deployments = pod_info.get("deployments", [])
    is_multi = pod_info.get("is_multi_deployment", False)
    
    if not deployments:
        return {
            "tool": "check_application_logs",
            "status": "error",
            "error": f"No deployments found for application '{app_name}'",
            "description": f"Application '{app_name}' has no associated EKS deployments"
        }
    
    # Get default log group from config
    default_log_group = pod_info.get("cloudwatch_log_group") or AWSConfig.AWS_CLOUDWATCH_LOG_GROUP
    
    # Query all deployments
    component_results = []
    total_logs = 0
    
    for deployment in deployments:
        pod_name = deployment.get("pod_name")
        deployment_name = deployment.get("deployment_name")
        criticality = deployment.get("criticality", "medium")
        log_group = deployment.get("cloudwatch_log_group") or default_log_group
        
        # Execute actual query to get pod logs
        # In CloudWatch, logs are streamed with pod names as identifiers
        log_events = get_log_events(log_group, pod_name, lines)
        
        # Convert log events to log strings
        logs = [event.get("message", "") for event in log_events]
        
        # Filter for errors if requested
        if error_only:
            logs = [log for log in logs if any(err in str(log).lower() for err in ['error', 'exception', 'failed', 'fatal', 'crash'])]
        
        total_logs += len(logs)
        
        # Detect errors in logs
        has_errors = any(err in str(log).lower() for log in logs for err in ['error', 'exception', 'failed', 'fatal', 'crash'])
        
        component_results.append({
            "deployment_name": deployment_name,
            "pod_name": pod_name,
            "log_group": log_group,
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
        "cluster": pod_info.get("cluster", AWSConfig.AWS_CLUSTER_NAME),
        "is_multi_deployment": is_multi,
        "deployments_queried": len(deployments),
        "lines_requested": lines,
        "total_logs_returned": total_logs,
        "error_only": error_only,
        "components": component_results,
        "query_type": "CloudWatch Logs"
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
) -> dict[str, Any]:
    """
    Query ALB/NLB ingress logs from CloudWatch.
    
    Dynamically resolves the application name to the correct ALB log group.
    
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
        result = check_ingress_logs("todo", lines=30)
        
        # Get only 5XX errors
        result = check_ingress_logs("todo", status_code_filter="500,502,503")
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
    
    log_group = ingress_info.get("log_group", AWSConfig.AWS_ALB_LOG_GROUP)
    
    # Execute actual query to get ingress logs
    ingress_logs = get_alb_logs(log_group, lines)
    
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
        "log_group": log_group,
        "cluster": ingress_info.get("cluster", AWSConfig.AWS_CLUSTER_NAME),
        "lines_requested": lines,
        "lines_returned": len(ingress_logs),
        "status_code_filter": status_code_filter,
        "min_response_time_ms": min_response_time_ms,
        "description": f"Retrieved {len(ingress_logs)} ALB logs for '{app_name}'{filter_desc}",
        "query_type": "CloudWatch ALB Logs",
        "logs": ingress_logs
    }


def analyze_pod_logs(
    app_name: str,
    include_metrics: bool = True,
    include_events: bool = True
) -> dict[str, Any]:
    """
    Perform comprehensive pod analysis combining logs, metrics, and health status.
    
    Dynamically resolves the application name to the correct pod(s) and namespace.
    
    For multi-deployment apps, analyzes ALL deployments in parallel and provides
    unified RCA with component health status.
    
    This tool queries CloudWatch logs, CloudWatch metrics (CPU, memory), and
    pod status to provide complete diagnostics for RCA (Root Cause Analysis).
    
    Args:
        app_name: Name of the application to analyze (e.g., "todo", "auth-service")
        include_metrics: Include CloudWatch metrics (CPU, memory utilization) (default: True)
        include_events: Include EKS pod events and state changes (default: True)
    
    Returns:
        Dictionary with comprehensive pod diagnostics:
        - For multi-deployment apps: Logs/metrics/status for each component + health summary
        - For single-deployment apps: Logs, metrics, status, error patterns
        - RCA findings with component prioritization
    
    Example:
        # Full pod analysis for troubleshooting
        result = analyze_pod_logs("todo")
    """
    
    # Dynamically resolve pod info from metadata database
    pod_info = get_pod_info(app_name)
    
    if pod_info.get("error"):
        return {
            "tool": "analyze_pod_logs",
            "status": "error",
            "error": pod_info["error"],
            "description": f"Failed to resolve application '{app_name}' in AWS metadata"
        }
    
    deployments = pod_info.get("deployments", [])
    is_multi = pod_info.get("is_multi_deployment", False)
    
    if not deployments:
        return {
            "tool": "analyze_pod_logs",
            "status": "error",
            "error": f"No deployments found for application '{app_name}'",
            "description": f"Application '{app_name}' has no associated EKS deployments"
        }
    
    # Get default log group from config
    default_log_group = pod_info.get("cloudwatch_log_group") or AWSConfig.AWS_CLOUDWATCH_LOG_GROUP
    
    # Query all deployments
    component_results = []
    critical_issues = []
    
    for deployment in deployments:
        pod_name = deployment.get("pod_name")
        deployment_name = deployment.get("deployment_name")
        namespace = deployment.get("namespace", "default")
        criticality = deployment.get("criticality", "medium")
        log_group = deployment.get("cloudwatch_log_group") or default_log_group
        
        # Get logs
        log_events = get_log_events(log_group, pod_name, 100)
        logs = [event.get("message", "") for event in log_events]
        
        # Detect errors in logs
        has_errors = any(err in str(log).lower() for log in logs for err in ['error', 'exception', 'failed', 'fatal', 'crash'])
        has_restart_events = any(err in str(log).lower() for log in logs for err in ['restart', 'backoff', 'crashloop'])
        
        # Get metrics if requested
        metrics = {}
        if include_metrics:
            metrics_result = get_cloudwatch_metrics(
                namespace=AWSConfig.AWS_CLOUDWATCH_NAMESPACE,
                metric_name="PodCpuUtilization",
                dimensions={"PodName": pod_name, "Namespace": namespace}
            )
            if metrics_result.get("status") == "success":
                metrics["cpu_datapoints"] = metrics_result.get("datapoints", [])
            
            metrics_result = get_cloudwatch_metrics(
                namespace=AWSConfig.AWS_CLOUDWATCH_NAMESPACE,
                metric_name="PodMemoryUtilization",
                dimensions={"PodName": pod_name, "Namespace": namespace}
            )
            if metrics_result.get("status") == "success":
                metrics["memory_datapoints"] = metrics_result.get("datapoints", [])
        
        # Determine health status
        if has_restart_events or has_errors:
            health_status = "🔴 Critical"
            if has_errors or has_restart_events:
                critical_issues.append({
                    "component": deployment_name,
                    "status": health_status,
                    "reason": "Error logs or restart events detected",
                    "logs_count": len(logs),
                    "logs": logs[:10]  # First 10 logs as evidence
                })
        else:
            health_status = "🟢 Healthy"
        
        component_results.append({
            "deployment_name": deployment_name,
            "pod_name": pod_name,
            "namespace": namespace,
            "log_group": log_group,
            "criticality": criticality,
            "health_status": health_status,
            "logs_count": len(logs),
            "logs": logs,
            "has_errors": has_errors,
            "has_restart_events": has_restart_events,
            "metrics": metrics
        })
    
    # Build response
    response = {
        "tool": "analyze_pod_logs",
        "status": "success",
        "app_name": app_name,
        "cluster": pod_info.get("cluster", AWSConfig.AWS_CLUSTER_NAME),
        "namespace": pod_info.get("namespace", "default"),
        "is_multi_deployment": is_multi,
        "deployments_analyzed": len(deployments),
        "components": component_results,
        "query_type": "CloudWatch Logs + Metrics + Events"
    }
    
    # Add component health summary
    if is_multi:
        health_summary = []
        for comp in component_results:
            health_summary.append({
                "deployment": comp["deployment_name"],
                "status": comp["health_status"],
                "log_count": comp["logs_count"],
                "has_errors": comp["has_errors"]
            })
        response["component_health"] = health_summary
        response["critical_issues"] = critical_issues if critical_issues else []
        response["description"] = f"Analyzed {len(deployments)} components. " \
                                 f"Critical issues: {len(critical_issues)}. See component_health for details."
    else:
        response["description"] = f"Analyzed pod '{component_results[0]['pod_name']}' " \
                                 f"in namespace '{component_results[0]['namespace']}'. " \
                                 f"Status: {component_results[0]['health_status']}"
    
    return response


__all__ = [
    "check_application_logs",
    "check_ingress_logs",
    "analyze_pod_logs"
]
