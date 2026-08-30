"""
Agent Platform Runtime contract server for the KaiOps ADK agent.

Implements the Agent Platform runtime contract for a custom container (BYOC):
    - POST /api/reasoning_engine        (unary query)
    - POST /api/stream_reasoning_engine  (streaming query)

The container must listen on 0.0.0.0:8080. It wraps the AdkApp (which wraps
the KaiOps root_agent) and exposes the managed Sessions + Memory Bank via the
platform's VertexAiSessionService / VertexAiMemoryBankService (auto-built by
AdkApp on Agent Engine when GOOGLE_GENAI_USE_ENTERPRISE=TRUE).
"""

import inspect
import json
import logging
import os

import uvicorn
from fastapi import FastAPI, encoders, responses
from pydantic import BaseModel
from typing import Any, Dict, Optional

from runtime_app import runtime_app  # the AdkApp wrapping root_agent

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="KaiOps SRE Agent — Agent Platform Runtime")

# Ensure the AdkApp runner/services are initialized.
runtime_app.set_up()
logger.info("[RUNTIME] AdkApp set_up() complete")


class ContractRequest(BaseModel):
    """Runtime-contract request body: { class_method, input }."""
    input: Optional[Dict[str, Any]] = None
    class_method: str


def _get_session_and_user(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extract user_id / message from the Agent Runtime contract input.

    Agent Platform sends `input` as the kwargs for the class method. For a
    KaiOps ADK query that is `message`, plus optional `user_id`/`session_id`.
    """
    payload = payload or {}
    message = payload.get("message")
    user_id = payload.get("user_id", "")
    session_id = payload.get("session_id")
    return {"message": message, "user_id": user_id, "session_id": session_id}


def _encode_chunk_to_json(chunk: Any):
    try:
        return json.dumps(encoders.jsonable_encoder(chunk)) + "\n"
    except Exception:
        logger.exception("Failed to encode chunk")
        return None


@app.post("/api/reasoning_engine")
async def query_endpoint(request: ContractRequest) -> responses.Response:
    """Unary query endpoint (class_method: query / async)."""
    if request.class_method not in ("query", "async"):
        return responses.JSONResponse(
            status_code=400,
            content={"error": f"Unsupported class_method '{request.class_method}'"},
        )
    ctx = _get_session_and_user(request.input or {})
    if not ctx["message"]:
        return responses.JSONResponse(status_code=400, content={"error": "input.message is required"})

    try:
        output = []
        async for event in runtime_app.async_stream_query(
            message=ctx["message"],
            user_id=ctx["user_id"],
            session_id=ctx["session_id"],
        ):
            output.append(event)
        # Assemble a human-readable final answer from the event stream.
        text = _events_to_text(output)
        return responses.JSONResponse(content={"output": text})
    except Exception as e:  # noqa: BLE001
        logger.exception("[RUNTIME] query failed")
        return responses.JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/api/stream_reasoning_engine")
async def stream_query_endpoint(request: ContractRequest) -> responses.StreamingResponse:
    """Streaming query endpoint (class_method: stream / async_stream)."""
    if request.class_method not in ("stream", "async_stream"):
        return responses.StreamingResponse(
            content=iter([json.dumps({"error": f"Unsupported class_method '{request.class_method}'"})]),
            status_code=400,
            media_type="application/json",
        )
    ctx = _get_session_and_user(request.input or {})
    if not ctx["message"]:
        return responses.StreamingResponse(
            content=iter([json.dumps({"error": "input.message is required"})]),
            status_code=400,
            media_type="application/json",
        )

    async def gen():
        try:
            async for event in runtime_app.async_stream_query(
                message=ctx["message"],
                user_id=ctx["user_id"],
                session_id=ctx["session_id"],
            ):
                chunk = _encode_chunk_to_json({"output": _event_to_text(event)})
                if chunk:
                    yield chunk
        except Exception as e:  # noqa: BLE001
            logger.exception("[RUNTIME] stream failed")
            yield json.dumps({"error": str(e)}) + "\n"

    return responses.StreamingResponse(content=gen(), media_type="application/json")


def _event_to_text(event: Dict[str, Any]) -> str:
    """Extract text from a dumped ADK event dict (content.parts[].text)."""
    try:
        content = event.get("content") or {}
        parts = content.get("parts") or []
        return "".join(
            p.get("text", "") for p in parts if isinstance(p, dict) and p.get("text")
        )
    except Exception:
        return ""


def _events_to_text(events: list) -> str:
    """Join all event texts, deduping empty/duplicate final responses."""
    parts = [_event_to_text(e) for e in events]
    non_empty = [p for p in parts if p]
    # Return the last meaningful chunk as the final answer.
    return non_empty[-1] if non_empty else ""


if __name__ == "__main__":
    # Runtime contract: listen on 0.0.0.0, port 8080 (PORT env override).
    port = int(os.environ.get("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
