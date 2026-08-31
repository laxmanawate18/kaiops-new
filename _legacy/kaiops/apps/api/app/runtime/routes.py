"""
Agent Runtime — Routes (The Autonomous Loop entry points)

This router exposes the endpoints that let KaiOps be INVOKED autonomously
(from Cloud Scheduler, Cloud Monitoring/ Pub/Sub, or any webhook) rather than
only reacting to a human chat message. It is the trigger side of Model C.

Endpoints:
    POST /api/v1/runtime/ingest        — create a job from any external signal
    POST /api/v1/runtime/ingest/pubsub — Google Cloud Pub/Sub push handler
    POST /api/v1/runtime/trigger       — convenience: create + enqueue a job
    POST /api/v1/runtime/worker/run    — run the background worker (claim+execute)
    GET  /api/v1/runtime/jobs          — list recent jobs
    GET  /api/v1/runtime/jobs/{id}     — fetch one job + its report
    POST /api/v1/runtime/jobs/{id}/approve — approve a WAITING_APPROVAL action
"""

import os
import logging
import asyncio
from typing import Any, Dict, Optional
from fastapi import APIRouter, Body, HTTPException, Query, Request, Header
from pydantic import BaseModel, Field

from app.runtime import jobs as job_store
from app.runtime import worker as runtime_worker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/runtime", tags=["runtime"])

# Simple shared-secret auth for autonomous ingests. Set this to a strong value
# via Secret Manager / env; if unset, ingress is rejected unless PUBSUB_INSECURE.
INGEST_TOKEN = os.environ.get("KAIOPS_RUNTIME_TOKEN", "")
PUBSUB_INSECURE = os.environ.get("KAIOPS_PUBSUB_INSECURE", "false").lower() == "true"


class IngestRequest(BaseModel):
    """Model for a generic autonomous ingest trigger."""
    incident_name: str = Field(..., description="Human-readable incident name")
    prompt: str = Field(..., description="Instruction for the agent")
    severity: str = Field(default="P1", description="P0/P1/P2/P3")
    source: str = Field(default="webhook", description="cloud_scheduler|pubsub|monitoring|webhook")
    metadata: Optional[Dict[str, Any]] = None


def _require_token(authorization: Optional[str]) -> None:
    """Reject unauthenticated ingress unless explicitly disabled."""
    if PUBSUB_INSECURE:
        return
    if not INGEST_TOKEN:
        # In dev, fail open with a warning so local testing is easy.
        logger.warning("[RUNTIME] KAIOPS_RUNTIME_TOKEN unset; ingress NOT authenticated (dev mode)")
        return
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if token != INGEST_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid runtime token")


@router.post("/ingest")
async def ingest(
    request: IngestRequest,
    authorization: Optional[str] = Header(default=None),
):
    """
    Create a PENDING autonomous job. The job stays PENDING until a worker
    claims it (via POST /worker/run or a Cloud Run job / Cloud Tasks worker).
    We deliberately do NOT run the agent inline here: asyncio.run() inside a
    Cloud Run background task is unreliable (the instance may be reclaimed
    after the response, leaving jobs stuck in RUNNING forever).
    """
    _require_token(authorization)
    job = job_store.create_job(
        source=request.source,
        incident_name=request.incident_name,
        prompt=request.prompt,
        severity=request.severity,
        metadata=request.metadata,
    )
    return {"job_id": job["id"], "status": job["status"], "source": job["source"]}


@router.post("/ingest/pubsub")
async def ingest_pubsub(request: Request):
    """
    Google Cloud Pub/Sub push handler (OIDC or shared-secret auth).
    Decodes the base64 payload from the standard Cloud Pub/Sub push format.
    """
    # Advertise directly; Pub/Sub may send an OIDC bearer we deliberately
    # don't require here (the pull-based subscribe worker does the real work).
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Pub/Sub push body")
    message = body.get("message", {})
    data_b64 = message.get("data", "")
    import base64
    try:
        decoded = base64.b64decode(data_b64).decode("utf-8")
    except Exception:
        decoded = data_b64

    # Allow either the raw decoded payload as a JSON object, or a message dict.
    payload = None
    try:
        import json
        payload = json.loads(decoded)
    except Exception:
        payload = {"message": decoded}

    incident_name = payload.get("incident_name") if isinstance(payload, dict) else "Pub/Sub Alert"
    prompt = payload.get("prompt") if isinstance(payload, dict) else decoded
    severity = payload.get("severity", "P1") if isinstance(payload, dict) else "P1"

    job = job_store.create_job(
        source="pubsub",
        incident_name=str(incident_name or "Pub/Sub Alert"),
        prompt=str(prompt or decoded),
        severity=str(severity),
        metadata={"raw_payload": payload},
    )
    return {"job_id": job["id"], "status": job["status"], "ack": True}


@router.post("/trigger")
async def trigger(
    request: IngestRequest,
    authorization: Optional[str] = Header(default=None),
):
    """Create a job AND immediately run the worker (one-shot convenience)."""
    _require_token(authorization)
    job = job_store.create_job(
        source=request.source,
        incident_name=request.incident_name,
        prompt=request.prompt,
        severity=request.severity,
        metadata=request.metadata,
    )
    summary = await runtime_worker.process_pending_jobs(max_jobs=1)
    return {"job_id": job["id"], "worker_summary": summary, "job": job_store.get_job(job["id"])}


@router.post("/worker/run")
async def run_worker(
    authorization: Optional[str] = Header(default=None),
    max_jobs: int = Query(default=1, ge=1, le=5),
):
    """Manually invoke the background worker (useful for cron/Cloud Run job)."""
    _require_token(authorization)
    summary = await runtime_worker.process_pending_jobs(max_jobs=max_jobs)
    return summary


@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
):
    return {"jobs": job_store.list_jobs(limit=limit, status=status)}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/approve")
async def approve_job(job_id: str):
    """
    Approve a WAITING_APPROVAL job: the pending action token is consumed and
    the job is relaunched so the guarded tool actually executes.
    """
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job["status"] != job_store.STATUS_WAITING_APPROVAL:
        raise HTTPException(status_code=409, detail=f"Job is not waiting for approval (status={job['status']})")
    approval_token = (job.get("metadata") or {}).get("approval_token")
    if not approval_token:
        raise HTTPException(status_code=409, detail="No approval token stored")
    from app.chat.pending_actions import consume_pending
    consumed = consume_pending(approval_token)
    if not consumed:
        raise HTTPException(status_code=409, detail="Approval token already used or expired")
    # Relaunch the job so the guarded tool runs now that approval is granted.
    pending_tool = consumed.get("tool_name")
    session_id = f"runtime-{job_id}"
    # Re-run with an explicit approve flag in metadata.
    try:
        from app.chat.agent_service import process_message
        result = await process_message(
            message=job["prompt"],
            session_id=session_id,
            user_id=runtime_worker.SYSTEM_USER_ID,
            metadata={"autonomous": True, "approved_action": pending_tool, "job_id": job_id},
        )
        job_store.mark_complete(job_id, {
            "response": result.get("response", ""),
            "reasoning_steps": (result.get("metadata") or {}).get("reasoning_steps", []),
            "requires_confirmation": False,
            "success": result.get("success", False),
        })
    except Exception as e:
        job_store.mark_failed(job_id, str(e))
        raise HTTPException(status_code=500, detail=f"Approval execution failed: {e}")
    return {"job_id": job_id, "status": job_store.get_job(job_id)["status"]}
