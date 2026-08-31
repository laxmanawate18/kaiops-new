"""Shared A2A credential resolution for the KaiOps agent mesh.

Resolves the A2A bearer token used between the orchestrator and the cloud
specialist reasoning engines. Resolution order:
  1. ``A2A_SHARED_TOKEN`` env var (set directly for local/dev)
  2. ``A2A_SHARED_TOKEN_SECRET`` (Secret Manager secret resource name) — fetch
     the latest version via the Secret Manager API using ambient credentials.

This is intentionally side-effect free at import time so it never blocks agent
build; call :func:`get_shared_a2a_token` lazily inside request handling or when
wiring the RemoteA2aAgent sub-agents.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Fallback placeholder so the mesh builds in local/dev before the secret exists.
_PLACEHOLDER = "local-dev-placeholder"


def _fetch_secret_manager_latest(secret_resource: str) -> Optional[str]:
    """Fetch the latest secret version payload via the Secret Manager REST API.

    Uses the google-auth application-default credentials (ADC) that are
    automatically available on Cloud Run / Agent Runtime.
    """
    try:
        import json
        import urllib.request

        from google.auth import default
        from google.auth.transport.requests import Request

        creds, _ = default()
        creds.refresh(Request())
        url = (
            "https://secretmanager.googleapis.com/v1/"
            f"{secret_resource}/versions/latest:access"
        )
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {creds.token}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        payload = data.get("payload", {}).get("data", "")
        import base64
        return base64.b64decode(payload).decode("utf-8").strip()
    except Exception as e:  # pragma: no cover - network path
        logger.warning("Could not read A2A token from Secret Manager '%s': %s", secret_resource, e)
        return None


def get_shared_a2a_token() -> str:
    """Return the A2A bearer token shared across the KaiOps engines.

    Priority: ``A2A_SHARED_TOKEN`` > ``A2A_SHARED_TOKEN_SECRET`` (Secret Manager)
    > placeholder.
    """
    direct = os.environ.get("A2A_SHARED_TOKEN")
    if direct:
        return direct

    secret_resource = os.environ.get("A2A_SHARED_TOKEN_SECRET")
    if secret_resource:
        token = _fetch_secret_manager_latest(secret_resource)
        if token:
            return token

    return _PLACEHOLDER
