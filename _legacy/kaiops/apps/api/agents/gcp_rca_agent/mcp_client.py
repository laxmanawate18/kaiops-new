import os
import requests
import json
import logging
from typing import Dict, Any, Optional

from agents.mcp_client import _get_mcp_id_token

logger = logging.getLogger(__name__)

class GCPLoggingClient:
    @classmethod
    def get_log_entries(cls, pod_name: str, namespace: str, lines: int = 100, error_only: bool = False) -> Dict[str, Any]:
        return _call_mcp_tool("get_log_entries", {
            "pod_name": pod_name,
            "namespace": namespace,
            "lines": lines,
            "error_only": error_only
        })

class GCPMonitoringClient:
    @classmethod
    def get_monitoring_metrics(cls, pod_name: str, namespace: str, container_name: Optional[str] = None) -> Dict[str, Any]:
        return _call_mcp_tool("get_monitoring_metrics", {
            "pod_name": pod_name,
            "namespace": namespace,
            "container_name": container_name or ""
        })

class GCPLoadBalancerClient:
    @classmethod
    def get_load_balancer_logs(cls, lines: int = 50, status_code_filter: str = "", min_response_time_ms: int = 0) -> Dict[str, Any]:
        return _call_mcp_tool("get_load_balancer_logs", {
            "lines": lines,
            "status_code_filter": status_code_filter,
            "min_response_time_ms": min_response_time_ms
        })

def _call_mcp_tool(tool_name: str, kwargs: dict) -> Dict[str, Any]:
    # Mock fallback for local testing without server
    if os.getenv("GCP_MOCK_MODE", "false").lower() == "true":
        return _mock_response(tool_name, kwargs)
        
    mcp_url = os.getenv("GCP_MCP_URL", "http://localhost:8083/mcp")
    try:
        headers = {"Content-Type": "application/json"}
        # Cloud Run IAM: the token audience must be the service ROOT URL,
        # not the /mcp path (GCP_MCP_URL conventionally ends with /mcp).
        audience = mcp_url.rstrip("/")
        if audience.endswith("/mcp"):
            audience = audience[:-4]
        id_token = _get_mcp_id_token(audience)
        if id_token:
            headers["Authorization"] = f"Bearer {id_token}"
        else:
            logger.error(
                f"No Google ID token available for gcp-mcp-server "
                f"(audience={audience}). Request will likely be rejected with 403."
            )
        response = requests.post(
            mcp_url,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": kwargs
                },
                "id": 1
            },
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            return {"status": "error", "error": str(data["error"])}
            
        result_str = data.get("result", "{}")
        
        # Handle complex ADK/MCP response shapes
        if isinstance(result_str, dict):
            if "content" in result_str and isinstance(result_str["content"], list):
                if len(result_str["content"]) > 0 and "text" in result_str["content"][0]:
                    result_str = result_str["content"][0]["text"]
            elif "text" in result_str:
                result_str = result_str["text"]
            else:
                return result_str  # It's already the parsed JSON object
                
        # Parse the JSON string from the MCP tool
        if isinstance(result_str, str):
            return json.loads(result_str)
        return result_str
        
    except Exception as e:
        logger.error(f"Error calling GCP MCP tool {tool_name} at {mcp_url}: {e}")
        return {"status": "error", "error": str(e)}

def _mock_response(tool_name: str, kwargs: dict) -> dict:
    if tool_name == "get_log_entries":
        return {"status": "success", "logs": [{"severity": "INFO", "textPayload": "Mock GCP log entry", "timestamp": "2024-01-01T00:00:00Z"}]}
    elif tool_name == "get_monitoring_metrics":
        return {"status": "success", "cpu_usage_percent": 45.2, "memory_usage_percent": 62.1}
    elif tool_name == "get_load_balancer_logs":
        return {"status": "success", "logs": []}
    return {"status": "error", "error": "Unknown tool"}
