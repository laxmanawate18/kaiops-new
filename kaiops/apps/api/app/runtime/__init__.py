"""Agent Runtime — Autonomous Loop (Model C).

The runtime package gives KaiOps an event-driven, background-execution layer:
external triggers (Cloud Scheduler, Pub/Sub, webhook) create Firestore jobs that
a background Agent Runtime worker claims and executes through the ADK runner,
persisting a reasoning chain + report back to Firestore.
"""

from app.runtime import jobs, worker, routes

__all__ = ["jobs", "worker", "routes"]
