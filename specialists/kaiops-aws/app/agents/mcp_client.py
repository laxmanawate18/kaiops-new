"""
Centralized MCP Client (Cloud Run / HTTP version)

Handles communication with all MCP servers (ArgoCD, GitHub, Grafana, Azure).
Provides a unified interface for calling MCP tools from any agent.
Sends JSON-RPC requests via HTTP POST to the Cloud Run proxy endpoints.
"""

import base64
import json
import os
import time
import aiohttp
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)
load_dotenv()

# MCP Server URLs (Cloud Run endpoints)
MCP_SERVERS = {
    'argocd': os.getenv('MCP_URL_ARGOCD', 'https://argocd-mcp-server-rkapewlsyq-uc.a.run.app'),
    'github': os.getenv('MCP_URL_GITHUB', 'https://github-mcp-server-rkapewlsyq-uc.a.run.app'),
    'grafana': os.getenv('MCP_URL_GRAFANA', 'https://grafana-mcp-server-rkapewlsyq-uc.a.run.app'),
    'azure': os.getenv('MCP_URL_AZURE', 'https://azure-mcp-server-rkapewlsyq-uc.a.run.app')
}

# ---------------------------------------------------------------------------
# Google ID-token auth for Cloud Run MCP services
#
# The MCP Cloud Run services are deployed with --no-allow-unauthenticated (see
# infrastructure/k8s/deploy-all-mcp-cloudrun.ps1), so every request must carry
# a Google-signed ID token whose audience is the MCP service URL. The backend
# service account needs roles/run.invoker on each MCP service.
# ---------------------------------------------------------------------------
_ID_TOKEN_CACHE: Dict[str, Tuple[str, float]] = {}  # audience -> (token, exp_epoch)
_ID_TOKEN_SKEW_SECONDS = 60  # refresh this long before actual expiry


def _decode_jwt_exp(token: str) -> float:
    """Read the `exp` claim from a JWT without verifying the signature."""
    try:
        payload_b64 = token.split('.')[1]
        payload_b64 += '=' * (-len(payload_b64) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload_b64))
        return float(claims.get('exp', 0))
    except Exception:
        return 0.0


def _fetch_google_id_token(audience: str) -> Optional[str]:
    """
    Fetch a Google-signed ID token for `audience` using ambient credentials
    (metadata server on Cloud Run/GCE, GOOGLE_APPLICATION_CREDENTIALS locally).
    """
    try:
        import google.auth.transport.requests
        from google.oauth2 import id_token as google_id_token

        request = google.auth.transport.requests.Request()
        token = google_id_token.fetch_id_token(request, audience)
        if token:
            exp = _decode_jwt_exp(token) or (time.time() + 3600)
            _ID_TOKEN_CACHE[audience] = (token, exp)
        return token
    except Exception as e:
        logger.warning(f"Could not fetch Google ID token for audience '{audience}': {e}")
        return None


def _get_mcp_id_token(audience: str) -> Optional[str]:
    """Return a cached (or freshly fetched) ID token for the MCP service URL."""
    # Explicit override for local testing against secured services.
    override = os.getenv('MCP_ID_TOKEN')
    if override:
        return override

    cached = _ID_TOKEN_CACHE.get(audience)
    if cached and cached[1] > time.time() + _ID_TOKEN_SKEW_SECONDS:
        return cached[0]
    return _fetch_google_id_token(audience)


async def call_mcp_tool(server_name: str, tool_name: str, **kwargs) -> Dict[str, Any]:
    """
    Call a tool on an MCP server over HTTP.
    
    Args:
        server_name: Name of the server ('argocd', 'github', 'grafana', 'azure')
        tool_name: Name of the tool to call
        **kwargs: Tool arguments
    
    Returns:
        Tool response as dictionary
    """
    if server_name not in MCP_SERVERS:
        raise ValueError(f"Unknown MCP server: {server_name}")
        
    base_url = MCP_SERVERS[server_name].rstrip('/')
    url = f"{base_url}/mcp"
    
    request_id = int(os.urandom(4).hex(), 16)
    
    # Create JSON-RPC request matching MCP protocol
    request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": kwargs
        }
    }
    
    logger.debug(f"Calling MCP server '{server_name}' at {url} (Tool: {tool_name})")
    
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Content-Type": "application/json"}

            # Cloud Run IAM: MCP services require a Google ID token whose
            # audience is the service URL. Fail closed if we cannot obtain one.
            id_token = _get_mcp_id_token(base_url)
            if id_token:
                headers["Authorization"] = f"Bearer {id_token}"
            else:
                logger.error(
                    f"No Google ID token available for MCP server '{server_name}' "
                    f"(audience={base_url}). Request will likely be rejected with 403."
                )

            async with session.post(url, json=request, headers=headers, timeout=30.0) as response:
                response.raise_for_status()
                response_data = await response.json()
                
                if 'result' in response_data:
                    return response_data['result']
                elif 'error' in response_data:
                    raise Exception(f"MCP Error from {server_name}: {response_data['error']}")
                else:
                    return response_data
    except Exception as e:
        logger.error(f"Failed to communicate with MCP server '{server_name}': {e}")
        return {"error": str(e)}


def parse_mcp_response(result: Dict[str, Any]) -> Dict[str, Any]:
    """Parse MCP response format and extract actual data."""
    if "error" in result:
        logger.warning(f"MCP returned error: {result}")
        return result
    
    logger.debug(f"MCP raw result: {json.dumps(result)[:500]}")
    
    content = result.get("content", [])
    if content and len(content) > 0:
        text_content = content[0].get("text", "{}")
        try:
            parsed = json.loads(text_content)
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from MCP text: {e}")
            logger.error(f"Raw text was: {text_content[:500]}")
            return {}
    
    logger.warning("No content in MCP response")
    return {}
