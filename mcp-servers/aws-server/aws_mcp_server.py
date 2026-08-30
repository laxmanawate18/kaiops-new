"""
AWS CloudWatch MCP Server

Standalone FastMCP server that wraps boto3 CloudWatch Logs and CloudWatch Metrics
APIs. Deployed to Cloud Run via mcp_proxy.py, exposing tools over JSON-RPC.

Tools:
    get_log_events          - Fetch log events from a CloudWatch log group/stream
    execute_log_insights    - Run a CloudWatch Logs Insights query
    get_cloudwatch_metrics  - Fetch CloudWatch metric datapoints
    get_alb_logs            - Fetch ALB access logs from CloudWatch

Environment:
    AWS_ACCESS_KEY_ID       - AWS access key
    AWS_SECRET_ACCESS_KEY   - AWS secret key
    AWS_REGION              - AWS region (default: ap-southeast-2)
    AWS_MOCK_MODE           - Set to 'true' for mock/demo data (default: false)
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
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-2")
AWS_MOCK_MODE = os.getenv("AWS_MOCK_MODE", "false").lower() == "true"

mcp = FastMCP("aws-mcp-server")

# ---------------------------------------------------------------------------
# boto3 client helpers (lazy-initialised)
# ---------------------------------------------------------------------------
_logs_client = None
_cw_client = None


def _get_logs_client():
    global _logs_client
    if _logs_client is None:
        import boto3
        _logs_client = boto3.client(
            "logs",
            region_name=AWS_REGION,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
    return _logs_client


def _get_cw_client():
    global _cw_client
    if _cw_client is None:
        import boto3
        _cw_client = boto3.client(
            "cloudwatch",
            region_name=AWS_REGION,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
    return _cw_client


# ---------------------------------------------------------------------------
# Tool 1: get_log_events
# ---------------------------------------------------------------------------
@mcp.tool()
def get_log_events(
    log_group: str,
    log_stream: str,
    lines: int = 100,
) -> str:
    """Fetch recent log events from a CloudWatch Logs log group.

    Args:
        log_group: CloudWatch log group name (e.g. /aws/containerinsights/log-agent-eks/application)
        log_stream: Log stream name or pod name prefix to search for
        lines: Maximum number of log events to return (default 100)

    Returns:
        JSON with status, events list, and metadata
    """
    if AWS_MOCK_MODE:
        return json.dumps(_mock_get_log_events(log_group, log_stream, lines))

    try:
        client = _get_logs_client()

        # First, find matching log streams (pod names contain the stream prefix)
        streams_resp = client.describe_log_streams(
            logGroupName=log_group,
            logStreamNamePrefix=log_stream,
            orderBy="LastEventTime",
            descending=True,
            limit=5,
        )

        streams = streams_resp.get("logStreams", [])
        if not streams:
            # Fallback: search without prefix (some setups use different naming)
            streams_resp = client.describe_log_streams(
                logGroupName=log_group,
                orderBy="LastEventTime",
                descending=True,
                limit=10,
            )
            streams = [
                s for s in streams_resp.get("logStreams", [])
                if log_stream.lower() in s.get("logStreamName", "").lower()
            ]

        if not streams:
            return json.dumps({
                "status": "success",
                "log_group": log_group,
                "log_stream": log_stream,
                "events_count": 0,
                "events": [],
                "message": f"No log streams found matching '{log_stream}'"
            })

        # Get events from the most recent matching stream
        target_stream = streams[0]["logStreamName"]
        events_resp = client.get_log_events(
            logGroupName=log_group,
            logStreamName=target_stream,
            limit=lines,
            startFromHead=False,  # Most recent first
        )

        events = []
        for event in events_resp.get("events", []):
            events.append({
                "timestamp": datetime.fromtimestamp(
                    event["timestamp"] / 1000
                ).isoformat() + "Z",
                "message": event.get("message", ""),
            })

        return json.dumps({
            "status": "success",
            "log_group": log_group,
            "log_stream": target_stream,
            "events_count": len(events),
            "events": events,
        })

    except Exception as e:
        logger.error(f"get_log_events failed: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "log_group": log_group,
            "log_stream": log_stream,
        })


# ---------------------------------------------------------------------------
# Tool 2: execute_log_insights
# ---------------------------------------------------------------------------
@mcp.tool()
def execute_log_insights(
    log_group: str,
    query: str,
    time_range_minutes: int = 60,
) -> str:
    """Run a CloudWatch Logs Insights query.

    Args:
        log_group: CloudWatch log group name
        query: Logs Insights query string (e.g. 'fields @timestamp, @message | filter @message like /ERROR/')
        time_range_minutes: How many minutes back to search (default 60)

    Returns:
        JSON with query results
    """
    if AWS_MOCK_MODE:
        return json.dumps({
            "status": "success",
            "log_group": log_group,
            "query": query,
            "results_count": 0,
            "results": [],
        })

    try:
        import time as _time
        client = _get_logs_client()

        end_time = int(datetime.utcnow().timestamp())
        start_time = int((datetime.utcnow() - timedelta(minutes=time_range_minutes)).timestamp())

        start_resp = client.start_query(
            logGroupName=log_group,
            startTime=start_time,
            endTime=end_time,
            queryString=query,
            limit=100,
        )
        query_id = start_resp["queryId"]

        # Poll until complete (max 30s)
        for _ in range(30):
            result_resp = client.get_query_results(queryId=query_id)
            if result_resp["status"] == "Complete":
                break
            _time.sleep(1)

        results = []
        for row in result_resp.get("results", []):
            entry = {}
            for field in row:
                entry[field["field"]] = field["value"]
            results.append(entry)

        return json.dumps({
            "status": "success",
            "log_group": log_group,
            "query": query[:200],
            "query_status": result_resp["status"],
            "results_count": len(results),
            "results": results,
        })

    except Exception as e:
        logger.error(f"execute_log_insights failed: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "log_group": log_group,
            "query": query[:200],
        })


# ---------------------------------------------------------------------------
# Tool 3: get_cloudwatch_metrics
# ---------------------------------------------------------------------------
@mcp.tool()
def get_cloudwatch_metrics(
    namespace: str,
    metric_name: str,
    dimensions: str = "{}",
    time_range_minutes: int = 60,
    period_seconds: int = 300,
    stat: str = "Average",
) -> str:
    """Fetch CloudWatch metric datapoints.

    Args:
        namespace: CloudWatch namespace (e.g. ContainerInsights)
        metric_name: Metric name (e.g. pod_cpu_utilization, pod_memory_utilization)
        dimensions: JSON-encoded dimensions dict (e.g. '{"PodName":"my-pod","Namespace":"default"}')
        time_range_minutes: How many minutes back to fetch (default 60)
        period_seconds: Aggregation period in seconds (default 300)
        stat: Statistic to retrieve (Average, Sum, Maximum, Minimum, SampleCount)

    Returns:
        JSON with datapoints
    """
    if AWS_MOCK_MODE:
        return json.dumps(_mock_get_cloudwatch_metrics(namespace, metric_name, dimensions))

    try:
        client = _get_cw_client()

        dims_dict = json.loads(dimensions) if isinstance(dimensions, str) else dimensions
        cw_dimensions = [{"Name": k, "Value": v} for k, v in dims_dict.items()]

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=time_range_minutes)

        resp = client.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=cw_dimensions,
            StartTime=start_time,
            EndTime=end_time,
            Period=period_seconds,
            Statistics=[stat],
        )

        datapoints = []
        for dp in sorted(resp.get("Datapoints", []), key=lambda x: x["Timestamp"]):
            datapoints.append({
                "timestamp": dp["Timestamp"].isoformat(),
                "value": dp.get(stat, 0),
                "unit": dp.get("Unit", "None"),
            })

        return json.dumps({
            "status": "success",
            "namespace": namespace,
            "metric_name": metric_name,
            "dimensions": dims_dict,
            "datapoints_count": len(datapoints),
            "datapoints": datapoints,
        })

    except Exception as e:
        logger.error(f"get_cloudwatch_metrics failed: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "namespace": namespace,
            "metric_name": metric_name,
        })


# ---------------------------------------------------------------------------
# Tool 4: get_alb_logs
# ---------------------------------------------------------------------------
@mcp.tool()
def get_alb_logs(
    log_group: str,
    lines: int = 50,
) -> str:
    """Fetch ALB/ELB access logs from CloudWatch.

    Args:
        log_group: CloudWatch log group for ALB logs
        lines: Number of log entries to retrieve (default 50)

    Returns:
        JSON with parsed ALB log entries
    """
    if AWS_MOCK_MODE:
        return json.dumps(_mock_get_alb_logs(log_group, lines))

    try:
        client = _get_logs_client()

        # Use Logs Insights to parse ALB log format
        end_time = int(datetime.utcnow().timestamp())
        start_time = int((datetime.utcnow() - timedelta(hours=1)).timestamp())

        # ALB logs have a specific format; use Insights to parse them
        query = """
            fields @timestamp, @message
            | parse @message '"*" * * * *:* *:* * * * * "*" "*" * * * * *' as
                type, timestamp_field, elb, client_port, target_port,
                request_processing_time, target_processing_time,
                response_processing_time, elb_status_code,
                target_status_code, received_bytes, sent_bytes,
                request, user_agent, ssl_cipher, ssl_protocol,
                target_group_arn, trace_id
            | sort @timestamp desc
            | limit @lines
        """.replace("@lines", str(lines))

        try:
            import time as _time
            start_resp = client.start_query(
                logGroupName=log_group,
                startTime=start_time,
                endTime=end_time,
                queryString=query,
                limit=lines,
            )
            query_id = start_resp["queryId"]

            for _ in range(15):
                result_resp = client.get_query_results(queryId=query_id)
                if result_resp["status"] == "Complete":
                    break
                _time.sleep(1)

            logs = []
            for row in result_resp.get("results", []):
                entry = {}
                for field in row:
                    entry[field["field"]] = field["value"]
                logs.append({
                    "timestamp": entry.get("@timestamp", ""),
                    "method": _extract_method(entry.get("request", "")),
                    "path": _extract_path(entry.get("request", "")),
                    "status_code": entry.get("elb_status_code", "0"),
                    "response_time_ms": str(int(
                        float(entry.get("target_processing_time", "0")) * 1000
                    )),
                    "upstream": entry.get("target_port", ""),
                })

        except Exception:
            # Fallback: just get raw log events
            streams_resp = client.describe_log_streams(
                logGroupName=log_group,
                orderBy="LastEventTime",
                descending=True,
                limit=1,
            )
            streams = streams_resp.get("logStreams", [])
            logs = []
            if streams:
                events_resp = client.get_log_events(
                    logGroupName=log_group,
                    logStreamName=streams[0]["logStreamName"],
                    limit=lines,
                    startFromHead=False,
                )
                for event in events_resp.get("events", []):
                    logs.append({
                        "timestamp": datetime.fromtimestamp(
                            event["timestamp"] / 1000
                        ).isoformat() + "Z",
                        "message": event.get("message", ""),
                    })

        return json.dumps({
            "status": "success",
            "log_group": log_group,
            "logs_count": len(logs),
            "logs": logs,
        })

    except Exception as e:
        logger.error(f"get_alb_logs failed: {e}")
        return json.dumps({
            "status": "error",
            "error": str(e),
            "log_group": log_group,
        })


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def _extract_method(request_str: str) -> str:
    """Extract HTTP method from ALB request field like 'GET https://...'."""
    parts = request_str.strip().split(" ")
    return parts[0] if parts else "UNKNOWN"


def _extract_path(request_str: str) -> str:
    """Extract path from ALB request field like 'GET https://host/path HTTP/1.1'."""
    parts = request_str.strip().split(" ")
    if len(parts) >= 2:
        url = parts[1]
        # Strip protocol and host, keep path
        if "://" in url:
            path_start = url.index("://") + 3
            slash_idx = url.find("/", path_start)
            return url[slash_idx:] if slash_idx >= 0 else "/"
        return url
    return "/"


# ---------------------------------------------------------------------------
# Mock implementations (for demos / testing)
# ---------------------------------------------------------------------------
def _mock_get_log_events(log_group: str, log_stream: str, lines: int) -> dict:
    if "backend" in log_stream.lower() or "api" in log_stream.lower():
        events = [
            {"timestamp": "2024-11-24T10:15:23Z", "message": "[INFO] Starting API pod"},
            {"timestamp": "2024-11-24T10:15:24Z", "message": "[INFO] Database connection established"},
            {"timestamp": "2024-11-24T10:15:25Z", "message": "[INFO] Server listening on port 5000"},
            {"timestamp": "2024-11-24T10:15:26Z", "message": "[ERROR] Failed to load configuration from ConfigMap"},
            {"timestamp": "2024-11-24T10:15:27Z", "message": "[ERROR] java.lang.NullPointerException: Config is null"},
            {"timestamp": "2024-11-24T10:15:28Z", "message": "[ERROR] Stack trace: at com.app.config.ConfigLoader.load()"},
            {"timestamp": "2024-11-24T10:15:29Z", "message": "[ERROR] Application startup failed"},
            {"timestamp": "2024-11-24T10:15:30Z", "message": "[FATAL] Exiting due to configuration error"},
        ]
    elif "frontend" in log_stream.lower() or "web" in log_stream.lower():
        events = [
            {"timestamp": "2024-11-24T10:15:23Z", "message": "[INFO] Starting frontend pod"},
            {"timestamp": "2024-11-24T10:15:24Z", "message": "[INFO] Loading environment: production"},
            {"timestamp": "2024-11-24T10:15:25Z", "message": "[INFO] Webpack compilation complete"},
            {"timestamp": "2024-11-24T10:15:26Z", "message": "[INFO] Server listening on port 3000"},
            {"timestamp": "2024-11-24T10:15:27Z", "message": "[INFO] Ready to accept requests"},
            {"timestamp": "2024-11-24T10:16:00Z", "message": "[INFO] GET /api/health 200"},
        ]
    else:
        events = [
            {"timestamp": "2024-11-24T10:15:23Z", "message": "[INFO] Starting pod"},
            {"timestamp": "2024-11-24T10:15:24Z", "message": "[INFO] Database connection established"},
            {"timestamp": "2024-11-24T10:15:25Z", "message": "[INFO] Server listening on port 5000"},
            {"timestamp": "2024-11-24T10:15:26Z", "message": "[INFO] Ready to accept connections"},
            {"timestamp": "2024-11-24T10:16:00Z", "message": "[INFO] Received request: GET /api/todos"},
            {"timestamp": "2024-11-24T10:16:01Z", "message": "[INFO] Request completed successfully"},
        ]
    return {
        "status": "success",
        "log_group": log_group,
        "log_stream": log_stream,
        "events_count": min(len(events), lines),
        "events": events[:lines],
    }


def _mock_get_cloudwatch_metrics(namespace: str, metric_name: str, dimensions: str) -> dict:
    dims = json.loads(dimensions) if isinstance(dimensions, str) else dimensions
    component = dims.get("PodName", "unknown")
    if "backend" in component.lower() or "api" in component.lower():
        datapoints = [
            {"timestamp": "2024-11-24T10:15:00Z", "value": 75, "unit": "Percent"},
            {"timestamp": "2024-11-24T10:16:00Z", "value": 88, "unit": "Percent"},
            {"timestamp": "2024-11-24T10:17:00Z", "value": 92, "unit": "Percent"},
        ]
    else:
        datapoints = [
            {"timestamp": "2024-11-24T10:15:00Z", "value": 20, "unit": "Percent"},
            {"timestamp": "2024-11-24T10:16:00Z", "value": 25, "unit": "Percent"},
            {"timestamp": "2024-11-24T10:17:00Z", "value": 22, "unit": "Percent"},
        ]
    return {
        "status": "success",
        "namespace": namespace,
        "metric_name": metric_name,
        "dimensions": dims,
        "datapoints_count": len(datapoints),
        "datapoints": datapoints,
    }


def _mock_get_alb_logs(log_group: str, lines: int) -> dict:
    logs = [
        {"timestamp": "2024-11-24T10:16:00Z", "method": "GET", "path": "/api/todos", "status_code": "200", "response_time_ms": "45", "upstream": "10.0.1.15:5000"},
        {"timestamp": "2024-11-24T10:16:05Z", "method": "POST", "path": "/api/todos", "status_code": "201", "response_time_ms": "82", "upstream": "10.0.1.15:5000"},
        {"timestamp": "2024-11-24T10:16:10Z", "method": "GET", "path": "/api/todos/123", "status_code": "200", "response_time_ms": "38", "upstream": "10.0.1.15:5000"},
        {"timestamp": "2024-11-24T10:16:15Z", "method": "DELETE", "path": "/api/todos/456", "status_code": "500", "response_time_ms": "5000", "upstream": "10.0.1.15:5000"},
    ]
    return {
        "status": "success",
        "log_group": log_group,
        "logs_count": min(len(logs), lines),
        "logs": logs[:lines],
    }
