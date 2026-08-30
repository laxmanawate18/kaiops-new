#!/usr/bin/env python3
"""
Azure AKS & Log Analytics MCP Server

Provides tools for querying AKS pod logs and Azure Log Analytics data.
Uses kubectl for pod operations and Azure SDK for Log Analytics queries.
"""

import asyncio
import concurrent.futures
import json
import subprocess
import os
from typing import Optional

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types

# Initialize MCP Server
server = Server("azure-aks-mcp-server")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List all available AKS and Log Analytics tools."""
    return [
        types.Tool(
            name="list_pods",
            description="List pods in an AKS namespace using kubectl",
            inputSchema={
                "type": "object",
                "properties": {
                    "namespace": {
                        "type": "string",
                        "description": "Kubernetes namespace (default: kaiops-ns)"
                    }
                },
                "required": [],
            },
        ),
        types.Tool(
            name="get_pod_logs",
            description="Get logs from a specific pod in AKS",
            inputSchema={
                "type": "object",
                "properties": {
                    "pod_name": {
                        "type": "string",
                        "description": "Name of the pod"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Kubernetes namespace (default: kaiops-ns)"
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of log lines to retrieve (default: 100)"
                    }
                },
                "required": ["pod_name"],
            },
        ),
        types.Tool(
            name="get_pod_events",
            description="Get events for a specific pod in AKS",
            inputSchema={
                "type": "object",
                "properties": {
                    "pod_name": {
                        "type": "string",
                        "description": "Name of the pod"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Kubernetes namespace (default: kaiops-ns)"
                    }
                },
                "required": ["pod_name"],
            },
        ),
        types.Tool(
            name="get_pod_describe",
            description="Get detailed description of a pod in AKS",
            inputSchema={
                "type": "object",
                "properties": {
                    "pod_name": {
                        "type": "string",
                        "description": "Name of the pod"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Kubernetes namespace (default: kaiops-ns)"
                    }
                },
                "required": ["pod_name"],
            },
        ),
        types.Tool(
            name="query_log_analytics",
            description="Query Azure Log Analytics using KQL (Kusto Query Language)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "KQL query to execute"
                    },
                    "workspace_id": {
                        "type": "string",
                        "description": "Log Analytics Workspace ID"
                    },
                    "time_range": {
                        "type": "string",
                        "description": "Time range (default: 1h)"
                    }
                },
                "required": ["query", "workspace_id"],
            },
        ),
        types.Tool(
            name="get_ingress_logs",
            description="Get NGINX ingress logs from Azure Log Analytics",
            inputSchema={
                "type": "object",
                "properties": {
                    "workspace_id": {
                        "type": "string",
                        "description": "Log Analytics Workspace ID"
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of log entries (default: 50)"
                    }
                },
                "required": ["workspace_id"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None) -> list[types.TextContent]:
    """Handle tool calls from ADK."""
    arguments = arguments or {}

    if name == "list_pods":
        return await _list_pods(arguments)
    elif name == "get_pod_logs":
        return await _get_pod_logs(arguments)
    elif name == "get_pod_events":
        return await _get_pod_events(arguments)
    elif name == "get_pod_describe":
        return await _get_pod_describe(arguments)
    elif name == "query_log_analytics":
        return await _query_log_analytics(arguments)
    elif name == "get_ingress_logs":
        return await _get_ingress_logs(arguments)
    else:
        return [types.TextContent(type="text", text=f"Unknown tool '{name}'")]


async def _list_pods(arguments: dict) -> list[types.TextContent]:
    """List pods in a namespace."""
    namespace = arguments.get("namespace", "kaiops-ns")

    try:
        cmd = ["kubectl", "get", "pods", "-n", namespace, "-o", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            return [types.TextContent(type="text", text=f"kubectl error: {result.stderr}")]

        data = json.loads(result.stdout)
        pods = []
        for item in data.get("items", []):
            pod_name = item["metadata"]["name"]
            status = item["status"]["phase"]
            pods.append(f"  • {pod_name} ({status})")

        text = f"Pods in namespace '{namespace}':\n" + "\n".join(pods)
        return [types.TextContent(type="text", text=text)]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


async def _get_pod_logs(arguments: dict) -> list[types.TextContent]:
    """Get logs from a pod."""
    pod_name = arguments.get("pod_name")
    namespace = arguments.get("namespace", "kaiops-ns")
    lines = arguments.get("lines", 100)

    if not pod_name:
        return [types.TextContent(type="text", text="pod_name is required")]

    try:
        cmd = ["kubectl", "logs", pod_name, "-n", namespace, "--tail", str(lines)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            return [types.TextContent(type="text", text=f"kubectl error: {result.stderr}")]

        return [types.TextContent(type="text", text=result.stdout)]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


async def _get_pod_events(arguments: dict) -> list[types.TextContent]:
    """Get events for a pod."""
    pod_name = arguments.get("pod_name")
    namespace = arguments.get("namespace", "kaiops-ns")

    if not pod_name:
        return [types.TextContent(type="text", text="pod_name is required")]

    try:
        cmd = ["kubectl", "get", "events", "-n", namespace, "--field-selector", f"involvedObject.name={pod_name}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            return [types.TextContent(type="text", text=f"kubectl error: {result.stderr}")]

        return [types.TextContent(type="text", text=result.stdout)]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


async def _get_pod_describe(arguments: dict) -> list[types.TextContent]:
    """Get pod description."""
    pod_name = arguments.get("pod_name")
    namespace = arguments.get("namespace", "kaiops-ns")

    if not pod_name:
        return [types.TextContent(type="text", text="pod_name is required")]

    try:
        cmd = ["kubectl", "describe", "pod", pod_name, "-n", namespace]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            return [types.TextContent(type="text", text=f"kubectl error: {result.stderr}")]

        return [types.TextContent(type="text", text=result.stdout)]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


async def _query_log_analytics(arguments: dict) -> list[types.TextContent]:
    """Query Azure Log Analytics."""
    query = arguments.get("query")
    workspace_id = arguments.get("workspace_id")
    time_range = arguments.get("time_range", "1h")

    if not query or not workspace_id:
        return [types.TextContent(type="text", text="query and workspace_id are required")]

    try:
        # Note: This requires Azure CLI or SDK authentication
        # Using az cli if available
        cmd = [
            "az",
            "monitor",
            "log-analytics",
            "query",
            "-w",
            workspace_id,
            "--analytics-query",
            query
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            return [types.TextContent(type="text", text=f"Azure CLI error: {result.stderr}")]

        return [types.TextContent(type="text", text=result.stdout)]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


async def _get_ingress_logs(arguments: dict) -> list[types.TextContent]:
    """Get NGINX ingress logs."""
    workspace_id = arguments.get("workspace_id")
    lines = arguments.get("lines", 50)

    if not workspace_id:
        return [types.TextContent(type="text", text="workspace_id is required")]

    # KQL query for ingress logs
    query = f"""
ContainerLogV2
| where PodNamespace == "app-routing-system"
| extend msg = tostring(LogMessage)
| extend Method = extract(@"(GET|POST|PUT|DELETE|PATCH)", 1, msg)
| extend Path = extract(@"(GET|POST|PUT|DELETE|PATCH)\\s+([^\\s]+)", 2, msg)
| extend Status = extract(@"\\s(\\d{{3}})\\s", 1, msg)
| project TimeGenerated, Method, Path, Status, msg, PodName
| order by TimeGenerated desc
| take {lines}
"""

    try:
        cmd = [
            "az",
            "monitor",
            "log-analytics",
            "query",
            "-w",
            workspace_id,
            "--analytics-query",
            query
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)

        if result.returncode != 0:
            return [types.TextContent(type="text", text=f"Azure CLI error: {result.stderr}")]

        return [types.TextContent(type="text", text=result.stdout)]
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


def _run_coro_sync(coro):
    """Run a coroutine to completion, even if an event loop is already running."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _ex:
        return _ex.submit(asyncio.run, coro).result()


def list_pods(namespace: str = "kaiops-ns") -> str:
    """List pods in an AKS namespace using kubectl."""
    results = _run_coro_sync(_list_pods({"namespace": namespace}))
    return "\n".join(c.text for c in results)


def get_pod_logs(pod_name: str, namespace: str = "kaiops-ns", lines: int = 100) -> str:
    """Get logs from a specific pod in AKS."""
    results = _run_coro_sync(_get_pod_logs({"pod_name": pod_name, "namespace": namespace, "lines": lines}))
    return "\n".join(c.text for c in results)


def get_pod_events(pod_name: str, namespace: str = "kaiops-ns") -> str:
    """Get events for a specific pod in AKS."""
    results = _run_coro_sync(_get_pod_events({"pod_name": pod_name, "namespace": namespace}))
    return "\n".join(c.text for c in results)


def get_pod_describe(pod_name: str, namespace: str = "kaiops-ns") -> str:
    """Get detailed description of a pod in AKS."""
    results = _run_coro_sync(_get_pod_describe({"pod_name": pod_name, "namespace": namespace}))
    return "\n".join(c.text for c in results)


def query_log_analytics(query: str, workspace_id: str, time_range: str = "1h") -> str:
    """Query Azure Log Analytics using KQL (Kusto Query Language)."""
    results = _run_coro_sync(_query_log_analytics({"query": query, "workspace_id": workspace_id, "time_range": time_range}))
    return "\n".join(c.text for c in results)


def get_ingress_logs(workspace_id: str, lines: int = 50) -> str:
    """Get NGINX ingress logs from Azure Log Analytics."""
    results = _run_coro_sync(_get_ingress_logs({"workspace_id": workspace_id, "lines": lines}))
    return "\n".join(c.text for c in results)


async def run() -> None:
    """Run the MCP server over stdio."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="azure-aks-mcp-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(run())
