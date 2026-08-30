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
import asyncio
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
    app_name = (job.get("metadata") or {}).get("argocd_app") or (job.get("metadata") or {}).get("application") or ""

    try:
        # Ensure an ADK session exists for the synthetic user. Tag it with the
        # application name so the Healthy path can resolve a real console link
        # (the app's latest RCA session) instead of a fabricated one.
        existing = await session_service.get_session(
            app_name="kaiops", user_id=SYSTEM_USER_ID, session_id=session_id
        )
        if not existing:
            await session_service.create_session(
                app_name="kaiops", user_id=SYSTEM_USER_ID, session_id=session_id
            )
            # Stamp the app name on the session doc so /console resolution works.
            try:
                from app.database.firestore_config import FirestoreConfig
                FirestoreConfig.get_client().collection("chat_sessions").document(session_id).update(
                    {"application_name": app_name, "session_type": "runtime"}
                )
            except Exception as tag_err:  # noqa: BLE001
                logger.warning(f"[JOB] tag session app_name failed: {tag_err}")

        # Run the agent. This reuses the exact ADK runner wiring already
        # validated by the interactive chat path. Bounded by a timeout so a
        # hung/long agent run cannot wedge the worker loop (env-gated).
        from app.chat.agent_service import process_message

        logger.info(f"[JOB] Executing {job_id}: {prompt[:80]}...")
        job_timeout = int(os.environ.get("KAIOPS_JOB_TIMEOUT_SECONDS", "900"))
        process_coro = process_message(
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
        try:
            result = await asyncio.wait_for(process_coro, timeout=job_timeout)
        except asyncio.TimeoutError:
            logger.error(f"[JOB] {job_id} timed out after {job_timeout}s; marking FAILED")
            jobs.mark_failed(job_id, f"Job timed out after {job_timeout}s")
            return {
                "response": f"Autonomous investigation timed out after {job_timeout}s.",
                "reasoning_steps": [],
                "requires_confirmation": False,
                "pending_tool": None,
                "approval_token": None,
                "success": False,
                "error": f"timeout:{job_timeout}s",
            }
        except Exception as exec_err:
            logger.error(f"[JOB] {job_id} execution failed: {exec_err}", exc_info=True)
            jobs.mark_failed(job_id, str(exec_err))
            return {
                "response": f"Autonomous investigation failed: {exec_err}",
                "reasoning_steps": [],
                "requires_confirmation": False,
                "pending_tool": None,
                "approval_token": None,
                "success": False,
                "error": str(exec_err),
            }

        response = result.get("response", "")
        meta = result.get("metadata", {}) or {}
        reasoning_steps = meta.get("reasoning_steps", [])

        requires_confirmation = bool(meta.get("requires_confirmation", False))
        pending_tool = meta.get("pending_tool")
        approval_token = meta.get("approval_token")

        # Persist the RCA conversation (user prompt + assistant report) as chat
        # messages so the console deep-link (/console/runtime-{job_id}) shows the
        # actual investigation instead of an empty conversation. The worker owns
        # this session (SYSTEM_USER_ID), so add_message's ownership check passes.
        try:
            from app.chat.models import MessageSender
            session_service.add_message(
                user_id=SYSTEM_USER_ID, session_id=session_id,
                sender=MessageSender.USER, text=prompt,
                metadata={"autonomous": True, "source": job.get("source", "runtime")},
            )
            if response:
                session_service.add_message(
                    user_id=SYSTEM_USER_ID, session_id=session_id,
                    sender=MessageSender.ASSISTANT, text=response,
                    metadata={"autonomous": True, "source": job.get("source", "runtime"),
                              "requires_confirmation": requires_confirmation,
                              "approval_token": approval_token, "pending_tool": pending_tool},
                )
            logger.info(f"[JOB] Persisted {job_id} conversation to chat_messages")
        except Exception as msgerr:  # noqa: BLE001
            logger.warning(f"[JOB] persist chat messages failed: {msgerr}")

        report = {
            "response": response,
            "reasoning_steps": reasoning_steps,
            "requires_confirmation": requires_confirmation,
            "pending_tool": pending_tool,
            "approval_token": approval_token,
            "success": result.get("success", False),
            # NOTE: key name is a frontend contract (ApprovalCard.tsx). This block is
            # KaiOps' own HITL destructive-action gate. Google Cloud Model Armor is
            # provisioned separately as template `kaiops-governance-template`
            # (docs/FEATURE_PROGRESS.md §4); the Agent Gateway exposes no model-armor
            # binding field, so platform filters apply at the app/eval layer.
            "model_armor": meta.get("model_armor"),
            "error": "",
        }

        if requires_confirmation:
            logger.info(f"[JOB] {job_id} waiting for approval on '{pending_tool}'")
            jobs.mark_waiting_approval(job_id, pending_tool or "", approval_token or "", report)
        else:
            logger.info(f"[JOB] {job_id} complete ({len(response)} chars, {len(reasoning_steps)} steps)")
            jobs.mark_complete(job_id, report)

        # For ArgoCD-poller jobs, post the detailed RCA into the app's Slack thread
        # (subthread reply under the [App_Name] Failed parent), with the session link
        # and Approve/Reject HITL buttons if a guardrails action is pending.
        try:
            source = job.get("source", "")
            if source == "argocd_poller":
                from app.slack.reporter import post_rca_report
                from agents.sre_agent.remediation_guide import classify_root_cause
                app_name = (job.get("metadata") or {}).get("argocd_app") or ""
                frontend_url = os.environ.get("KAI_OPS_FRONTEND_URL", "https://kaiops-sre.searceinc.net")
                session_link = f"{frontend_url}/console/{session_id}"
                awaits_confirm = bool(report.get("requires_confirmation"))
                # Classify the RCA so the Slack thread tags SRE team when it is
                # infra-related (per the app-vs-infra classifier).
                is_infra = classify_root_cause(response) == "infra"
                await post_rca_report(
                    app_name=app_name,
                    rca_text=response or "RCA completed. See console for details.",
                    status="Failed",
                    session_link=session_link,
                    hitl_action_id=approval_token if awaits_confirm else "",
                    is_infra=is_infra,
                )
                logger.info(f"[RUNTIME] Posted RCA report to Slack thread for {app_name} (is_infra={is_infra})")
        except Exception as slack_err:  # noqa: BLE001
            logger.warning(f"[RUNTIME] post_rca_report (Slack) failed: {slack_err}")

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
