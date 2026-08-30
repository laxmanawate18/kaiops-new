"""
MCP Proxy Server

This script wraps a standard MCP Python server module and exposes an HTTP JSON-RPC API.
"""

import importlib
import importlib.util
import inspect
import json
import logging
import os
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_proxy")

MCP_SCRIPT = os.getenv("MCP_SCRIPT", "")
if not MCP_SCRIPT:
    raise RuntimeError("MCP_SCRIPT env var is required")

# Import the MCP server module using spec_from_file_location to gracefully
# handle namespace directories with hyphens (e.g. "aws-server")
parts = MCP_SCRIPT.split(".")
module_name = parts[-1]
file_path = os.path.join(*parts) + ".py"

spec = importlib.util.spec_from_file_location(module_name, file_path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Could not load module {MCP_SCRIPT} from {file_path}")

server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)
mcp_instance = getattr(server_module, "mcp", None)

app = FastAPI(title=f"MCP Proxy - {MCP_SCRIPT}")

def _jsonrpc_response(req_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}

def _jsonrpc_error(req_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

def _list_tools() -> Dict[str, Any]:
    tools = []
    if mcp_instance is not None:
        try:
            tm = getattr(mcp_instance, "_tool_manager", None)
            if tm is not None:
                for t in tm.list_tools():
                    tools.append({
                        "name": t.name,
                        "description": t.description or "",
                        "inputSchema": getattr(t, "parameters", {}) or {},
                    })
        except Exception as e:
            pass

    if not tools:
        for name, fn in vars(server_module).items():
            if name.startswith("_") or not callable(fn) or inspect.isclass(fn) or inspect.ismodule(fn):
                continue
            if getattr(fn, "__module__", "") != server_module.__name__:
                continue
            sig = inspect.signature(fn)
            properties = {}
            required = []
            for pname, p in sig.parameters.items():
                prop: Dict[str, Any] = {}
                ann = p.annotation
                if ann is int or ann == "int":
                    prop["type"] = "integer"
                elif ann is bool or ann == "bool":
                    prop["type"] = "boolean"
                else:
                    prop["type"] = "string"
                if p.default is inspect.Parameter.empty:
                    required.append(pname)
                properties[pname] = prop
            tools.append({
                "name": name,
                "description": (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else "",
                "inputSchema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })
    return {"tools": tools}

def _call_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    fn = getattr(server_module, tool_name, None)
    if not (callable(fn) and not inspect.isclass(fn)):
        fn = None
    elif mcp_instance is not None:
        tm = getattr(mcp_instance, "_tool_manager", None)
        if tm is not None:
            async def _async_call():
                return await tm.call_tool(tool_name, arguments)
            return _async_call()  # type: ignore[return-value]

    if fn is None:
        raise KeyError(f"Tool '{tool_name}' not found")

    filtered = {k: v for k, v in (arguments or {}).items() if k in inspect.signature(fn).parameters}
    out = fn(**filtered)
    text = out if isinstance(out, str) else json.dumps(out)

    if isinstance(text, str) and text.lstrip().startswith("Error"):
        payload = json.dumps({"error": text.strip()})
        return {"content": [{"type": "text", "text": payload}], "isError": True}
    try:
        parsed = json.loads(text)
    except Exception:
        return {"content": [{"type": "text", "text": text}]}
    else:
        return {"content": [{"type": "text", "text": text}], "isError": isinstance(parsed, dict) and "error" in parsed}

@app.post("/mcp")
@app.post("/")
async def rpc_endpoint(req: Request) -> JSONResponse:
    try:
        payload = await req.json()
    except Exception:
        return JSONResponse(_jsonrpc_error(None, -32700, "Parse error"))

    method = payload.get("method")
    req_id = payload.get("id")

    try:
        if method in ("tools/list", "list_tools"):
            return JSONResponse(_jsonrpc_response(req_id, _list_tools()))
        if method in ("tools/call", "call_tool"):
            params = payload.get("params") or {}
            result = _call_tool(params.get("name"), params.get("arguments") or {})
            if inspect.iscoroutine(result):
                raw = await result
                content = getattr(raw, "content", None)
                if content is not None:
                    texts = [{"type": "text", "text": getattr(c, "text", str(c))} for c in content]
                    return JSONResponse(_jsonrpc_response(req_id, {"content": texts}))
                if isinstance(raw, tuple) and len(raw) == 2:
                    return JSONResponse(_jsonrpc_response(req_id, raw[0]))
                return JSONResponse(_jsonrpc_response(req_id, raw))
            return JSONResponse(_jsonrpc_response(req_id, result))
        if method == "ping":
            return JSONResponse(_jsonrpc_response(req_id, {}))
        return JSONResponse(_jsonrpc_error(req_id, -32601, f"Method not supported: {method}"))
    except KeyError as e:
        return JSONResponse(_jsonrpc_response(req_id, {"content": [{"type": "text", "text": json.dumps({"error": str(e)})}]}))
    except Exception as e:
        logger.exception("Tool execution failed")
        return JSONResponse(_jsonrpc_response(req_id, {"content": [{"type": "text", "text": json.dumps({"error": f"{type(e).__name__}: {e}"})}]}))

@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "healthy", "script": MCP_SCRIPT}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    logger.info("Starting MCP proxy for %s on port %s", MCP_SCRIPT, port)
    uvicorn.run(app, host="0.0.0.0", port=port)
