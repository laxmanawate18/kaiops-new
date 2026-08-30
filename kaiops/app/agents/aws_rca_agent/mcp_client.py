"""
AWS MCP Client - HTTP JSON-RPC client for the AWS MCP Server

Replaces the old mock-based CloudWatchMCPClient with real HTTP calls to
the aws-mcp-server deployed on Cloud Run (or running locally).

Environment:
    AWS_MCP_URL  - URL of the AWS MCP server (default: http://localhost:8084/mcp)
"""

import json
import logging
import os
import requests
from typing import Any, Dict, List
from datetime import datetime, timedelta

from agents.mcp_client import _get_mcp_id_token

logger = logging.getLogger(__name__)

AWS_MCP_URL = os.getenv("AWS_MCP_URL", "http://localhost:8084/mcp")

_request_id = 0


def _call_mcp(method: str, tool_name: str, arguments: dict) -> Dict[str, Any]:
    """Send a JSON-RPC request to the AWS MCP server."""
    global _request_id
    _request_id += 1

    payload = {
        "jsonrpc": "2.0",
        "id": _request_id,
        "method": method,
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }

    try:
        headers = {"Content-Type": "application/json"}
        # Cloud Run IAM: the token audience must be the service ROOT URL,
        # not the /mcp path (AWS_MCP_URL conventionally ends with /mcp).
        audience = AWS_MCP_URL.rstrip("/")
        if audience.endswith("/mcp"):
            audience = audience[:-4]
        id_token = _get_mcp_id_token(audience)
        if id_token:
            headers["Authorization"] = f"Bearer {id_token}"
        else:
            logger.error(
                f"No Google ID token available for aws-mcp-server "
                f"(audience={audience}). Request will likely be rejected with 403."
            )
        resp = requests.post(AWS_MCP_URL, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        body = resp.json()

        # Extract result from JSON-RPC response. Different MCP proxies return
        # different shapes:
        #   a) a plain JSON string:  {"jsonrpc":"2.0","id":N,"result":"<json>"}
        #   b) a wrapped dict:       {"jsonrpc":"2.0","id":N,"result":{"content":[{"type":"text","text":"<json>"}]}}
        # Normalize both to a dict so downstream .get() never hits a str.
        result = body.get("result", {})

        if isinstance(result, str):
            try:
                return json.loads(result)
            except (json.JSONDecodeError, TypeError):
                return {"status": "success", "raw": result}

        if isinstance(result, dict):
            content = result.get("content", [])
            if isinstance(content, list) and content and isinstance(content[0], dict):
                text = content[0].get("text", "{}")
                try:
                    return json.loads(text)
                except (json.JSONDecodeError, TypeError):
                    return {"status": "success", "raw": text}
            return result

        return result

    except requests.exceptions.ConnectionError:
        logger.warning(f"AWS MCP server not reachable at {AWS_MCP_URL}, using empty response")
        return {"status": "error", "error": f"AWS MCP server not reachable at {AWS_MCP_URL}"}
    except Exception as e:
        logger.error(f"AWS MCP call failed: {e}")
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Public API (same signatures as the old mock client)
# ---------------------------------------------------------------------------

def get_log_events(log_group: str, log_stream: str, lines: int = 100) -> List[Dict[str, str]]:
    """Get CloudWatch log events and return as list of dicts."""
    result = _call_mcp("tools/call", "get_log_events", {
        "log_group": log_group,
        "log_stream": log_stream,
        "lines": lines,
    })

    if result.get("status") == "success":
        return result.get("events", [])
    else:
        return [{"timestamp": datetime.now().isoformat(), "message": f"Error: {result.get('error', 'Unknown error')}"}]


def execute_log_insights_query(
    log_group: str,
    query: str,
    start_time: int = None,
    end_time: int = None,
) -> Dict[str, Any]:
    """Execute CloudWatch Logs Insights query."""
    time_range = 60  # default 1 hour
    if start_time and end_time:
        time_range = max(1, int((end_time - start_time) / 60000))

    result = _call_mcp("tools/call", "execute_log_insights", {
        "log_group": log_group,
        "query": query,
        "time_range_minutes": time_range,
    })

    return result


def get_cloudwatch_metrics(
    namespace: str,
    metric_name: str,
    dimensions: dict,
    start_time: int = None,
    end_time: int = None,
) -> Dict[str, Any]:
    """Get CloudWatch metrics."""
    time_range = 60
    if start_time and end_time:
        time_range = max(1, int((end_time - start_time) / 60000))

    result = _call_mcp("tools/call", "get_cloudwatch_metrics", {
        "namespace": namespace,
        "metric_name": metric_name,
        "dimensions": json.dumps(dimensions),
        "time_range_minutes": time_range,
    })

    return result


def get_alb_logs(log_group: str, lines: int = 50) -> List[Dict[str, str]]:
    """Get ALB logs and return as list of dicts."""
    result = _call_mcp("tools/call", "get_alb_logs", {
        "log_group": log_group,
        "lines": lines,
    })

    if result.get("status") == "success":
        return result.get("logs", [])
    else:
        return []


__all__ = [
    "get_log_events",
    "execute_log_insights_query",
    "get_cloudwatch_metrics",
    "get_alb_logs",
]
