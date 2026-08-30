"""
Agent Runtime — Background Worker

Executes autonomous agent jobs against the ADK root_agent via the existing
`process_message` service (which wraps `Runner.run_async`). Captures the full
reasoning chain + HITL state and persists a structured report back to Firestore.

This is what makes KaiOps "runs in the background" — a worker claims a PENDING
job, runs the agent, and stores the result, all without a human initiating it.
"""

import os
import uuid
import logging
from typing import Any, Dict, Optional

from app.runtime import jobs
from app.chat.custom_session_service import VertexFirestoreSessionService

logger = logging.getLogger(__name__)

# The synthetic user id used for autonomous (non-interactive) sessions.
SYSTEM_USER_ID = os.environ.get("KAIOPS_RUNTIME_USER", "sre-agent-runtime")


def _build_session_service() -> Optional[VertexFirestoreSessionService]:
    try:
        return VertexFirestoreSessionService()
    except Exception as e:
        logger.error(f"[RUNTIME] Session service unavailable: {e}")
        return None


async def run_job(job: Dict[str, Any], session_service: VertexFirestoreSessionService) -> Dict[str, Any]:
    """Execute a single job end-to-end and return the report dict."""
    job_id = job["id"]
    prompt = job["prompt"] or "Perform autonomous root cause analysis."

    # Every job gets its own ADK session so memory stays isolated and the
    # reasoning chain is attributable to this specific investigation.
    session_id = f"runtime-{job_id}"

    try:
        # Ensure an ADK session exists for the synthetic user.
        existing = await session_service.get_session(
            app_name="kaiops", user_id=SYSTEM_USER_ID, session_id=session_id
        )
        if not existing:
            await session_service.create_session(
                app_name="kaiops", user_id=SYSTEM_USER_ID, session_id=session_id
            )

        # Run the agent. This reuses the exact ADK runner wiring already
        # validated by the interactive chat path.
        from app.chat.agent_service import process_message

        logger.info(f"[JOB] Executing {job_id}: {prompt[:80]}...")
        result = await process_message(
            message=prompt,
            session_id=session_id,
            user_id=SYSTEM_USER_ID,
            metadata={
                "autonomous": True,
                "source": job.get("source", "runtime"),
                "incident_name": job.get("incident_name", ""),
                "severity": job.get("severity", "P1"),
                "job_id": job_id,
            },
        )

        response = result.get("response", "")
        meta = result.get("metadata", {}) or {}
        reasoning_steps = meta.get("reasoning_steps", [])

        requires_confirmation = bool(meta.get("requires_confirmation", False))
        pending_tool = meta.get("pending_tool")
        approval_token = meta.get("approval_token")

        report = {
            "response": response,
            "reasoning_steps": reasoning_steps,
            "requires_confirmation": requires_confirmation,
            "pending_tool": pending_tool,
            "approval_token": approval_token,
            "success": result.get("success", False),
            "model_armor": meta.get("model_armor"),
            "error": "",
        }

        if requires_confirmation:
            logger.info(f"[JOB] {job_id} waiting for approval on '{pending_tool}'")
            jobs.mark_waiting_approval(job_id, pending_tool or "", approval_token or "", report)
        else:
            logger.info(f"[JOB] {job_id} complete ({len(response)} chars, {len(reasoning_steps)} steps)")
            jobs.mark_complete(job_id, report)

        return report

    except Exception as e:
        logger.error(f"[RUNTIME] Job {job_id} failed: {e}", exc_info=True)
        report = {
            "response": f"Autonomous investigation failed: {e}",
            "reasoning_steps": [],
            "requires_confirmation": False,
            "pending_tool": None,
            "approval_token": None,
            "success": False,
            "error": str(e),
        }
        jobs.mark_failed(job_id, str(e))
        return report


async def process_pending_jobs(max_jobs: int = 1) -> Dict[str, Any]:
    """
    Worker loop: claim and execute up to `max_jobs` PENDING jobs.
    Returns a summary dict for logging/health checks.
    """
    session_service = _build_session_service()
    if session_service is None:
        return {"processed": 0, "error": "session_service_unavailable"}

    worker_id = f"worker-{os.getpid()}-{uuid.uuid4().hex[:6]}"
    processed = 0
    results = []

    for _ in range(max_jobs):
        job = jobs.claim_next_pending(worker_id)
        if not job:
            break
        report = await run_job(job, session_service)
        processed += 1
        results.append({"job_id": job["id"], "success": report.get("success", False)})

    if processed:
        logger.info(f"[RUNTIME] Worker {worker_id} processed {processed} job(s)")
    return {"worker_id": worker_id, "processed": processed, "results": results}
