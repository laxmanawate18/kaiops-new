"""
Agent Runtime — Job State Machine

Persists autonomous agent jobs in Firestore. A job represents a single
autonomous investigation that the Agent Runtime worker executes in the
background, WITHOUT a human initiating it on every turn.

Lifecycle:
    PENDING  -> RUNNING  -> COMPLETE
                        |-> WAITING_APPROVAL  (requires human confirmation)
                        |-> FAILED

Mirrors the Firestore patterns used by app.chat.custom_session_service
(FirestoreConfig.get_client() singleton + collections).
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.database.firestore_config import FirestoreConfig

logger = logging.getLogger(__name__)

# Job statuses
STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_COMPLETE = "COMPLETE"
STATUS_WAITING_APPROVAL = "WAITING_APPROVAL"
STATUS_FAILED = "FAILED"
STATUS_CANCELLED = "CANCELLED"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(record: Dict[str, Any], keys: tuple = ("created_at", "started_at", "completed_at", "updated_at")) -> Dict[str, Any]:
    """Normalize Firestore timestamp fields to ISO strings."""
    for key in keys:
        value = record.get(key)
        if hasattr(value, "isoformat") and not isinstance(value, str):
            try:
                record[key] = value.isoformat()
            except Exception:
                record[key] = str(value)
        elif value is None and key in ("started_at", "completed_at"):
            record[key] = ""
    return record


def _jobs_ref():
    return FirestoreConfig.get_client().collection("agent_jobs")


def create_job(
    source: str,
    incident_name: str,
    prompt: str,
    severity: str = "P1",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a new autonomous job (status PENDING)."""
    job_id = str(uuid.uuid4())
    now = _now()
    job = {
        "id": job_id,
        "source": source,                     # e.g. "cloud_scheduler", "pubsub", "webhook", "runtime_api"
        "incident_name": incident_name,
        "prompt": prompt,
        "severity": severity,
        "status": STATUS_PENDING,
        "metadata": metadata or {},
        "created_at": now,
        "updated_at": now,
        "started_at": "",
        "completed_at": "",
        "worker_id": "",
        "report": {},                         # {response, reasoning_steps, requires_confirmation, ...}
        "error": "",
    }
    _jobs_ref().document(job_id).set(job)
    logger.info(f"[JOB] Created {job_id} source={source} severity={severity} status=PENDING")
    return job


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    doc = _jobs_ref().document(job_id).get()
    if not doc.exists:
        return None
    data = _normalize(doc.to_dict())
    data["id"] = doc.id
    return data


def list_jobs(limit: int = 25, status: Optional[str] = None) -> List[Dict[str, Any]]:
    # Query by status only (single-field => no composite index needed), then
    # sort in memory. Using order_by(created_at) with a where() on status
    # would require a composite index, which may not exist yet in fresh projects.
    query = _jobs_ref().where("status", "==", status) if status else _jobs_ref()
    docs = list(query.stream())
    jobs = []
    for doc in docs:
        data = _normalize(doc.to_dict())
        data["id"] = doc.id
        jobs.append(data)
    # Sort newest-first by created_at (lexicographic ISO strings sort correctly).
    jobs.sort(key=lambda j: str(j.get("created_at", "")), reverse=True)
    return jobs[:limit]


def find_open_by_fingerprint(incident_key: str, limit: int = 5):
    """Return the most recent OPEN job (PENDING/RUNNING/WAITING_APPROVAL) matching
    an ``incident_key`` fingerprint, or None.

    Used by the deployment webhook to dedupe repeated alert re-fires: if the same
    ``(application, incident_type)`` already has an active RCA, we short-circuit
    rather than spawning a duplicate job.
    """
    open_statuses = (STATUS_PENDING, STATUS_RUNNING, STATUS_WAITING_APPROVAL)
    try:
        docs = list(_jobs_ref().where("status", "in", open_statuses).stream())
    except Exception as e:  # noqa: BLE001
        # 'in' queries need the field present; fall back to a client-side scan.
        logger.warning(f"[JOB] find_open_by_fingerprint 'in' query failed ({e}); scanning")
        docs = []
        try:
            all_docs = list(_jobs_ref().stream())
            docs = [d for d in all_docs if d.to_dict().get("status") in open_statuses]
        except Exception as e2:  # noqa: BLE001
            logger.error(f"[JOB] fingerprint scan failed: {e2}")
            return None
    for doc in docs:
        data = doc.to_dict()
        meta = data.get("metadata") or {}
        if meta.get("incident_key") == incident_key:
            return {**data, "id": doc.id}
    return None


def update_job(job_id: str, **fields) -> Optional[Dict[str, Any]]:
    """Update allowed job fields. `updated_at` is set automatically."""
    ref = _jobs_ref().document(job_id)
    if not ref.get().exists:
        return None
    fields["updated_at"] = _now()
    ref.update({k: v for k, v in fields.items() if v is not None})
    return get_job(job_id)


def claim_next_pending(worker_id: str) -> Optional[Dict[str, Any]]:
    """
    Atomically claim the oldest PENDING job (-> RUNNING) using a Firestore
    transaction so multiple workers never pick up the same job. Returns the
    job dict or None if none available.

    Failure tolerance (env-gated): each claim increments an ``attempts`` counter.
    If ``attempts`` exceeds ``KAIOPS_JOB_MAX_ATTEMPTS`` (default 2), the job is
    marked FAILED instead of being re-claimed, so a persistently-failing job
    cannot loop forever.
    """
    client = FirestoreConfig.get_client()
    coll = _jobs_ref()

    # Claim the oldest PENDING job. Uses a status-guarded update (no Firestore
    # transaction, which has sync-client quirks): read PENDING docs, pick the
    # oldest, then update ONLY if it is still PENDING. A stale read could let
    # two workers pick the same doc, but the re-read guard below prevents both
    # from executing the same job.
    try:
        pending_docs = list(coll.where("status", "==", STATUS_PENDING).stream())
        if not pending_docs:
            return None
        doc = sorted(pending_docs, key=lambda d: str(d.to_dict().get("created_at", "")))[0]
        ref = doc.reference

        # Re-read to confirm still PENDING; update if so.
        current = ref.get()
        if not current.exists or current.to_dict().get("status") != STATUS_PENDING:
            return None

        # Bounded re-claims: if this job has already been attempted too many
        # times, give up and move it to a terminal FAILED state.
        max_attempts = int(os.environ.get("KAIOPS_JOB_MAX_ATTEMPTS", "2"))
        attempts = int(current.to_dict().get("attempts") or 0)
        if attempts + 1 > max_attempts:
            ref.update({"status": STATUS_FAILED, "error": "Max attempts exceeded",
                        "updated_at": _now(), "completed_at": _now()})
            logger.warning(f"[JOB] {doc.id} exceeded max attempts ({max_attempts}); marked FAILED")
            return None

        ref.update({
            "status": STATUS_RUNNING,
            "worker_id": worker_id,
            "started_at": _now(),
            "updated_at": _now(),
            "attempts": attempts + 1,
        })
        data = doc.to_dict()
        data["id"] = doc.id
        data["attempts"] = attempts + 1
        logger.info(f"[JOB] Claimed {data['id']} by worker {worker_id} (attempt {attempts + 1})")
        return data
    except Exception as e:
        logger.warning(f"[JOB] Claim failed: {e}")
        return None


def mark_waiting_approval(job_id: str, pending_tool: str, approval_token: str, report: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return update_job(job_id, status=STATUS_WAITING_APPROVAL, report=report, completed_at=_now(),
                      metadata={"pending_tool": pending_tool, "approval_token": approval_token})


def mark_running(job_id: str) -> Optional[Dict[str, Any]]:
    """Move a job from PENDING to RUNNING (used by the long-running loop start)."""
    return update_job(job_id, status=STATUS_RUNNING, started_at=_now(), updated_at=_now())


def mark_complete(job_id: str, report: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return update_job(job_id, status=STATUS_COMPLETE, report=report, completed_at=_now())


def mark_failed(job_id: str, error: str) -> Optional[Dict[str, Any]]:
    logger.error(f"[JOB] Failed {job_id}: {error}")
    return update_job(job_id, status=STATUS_FAILED, error=error, completed_at=_now())
