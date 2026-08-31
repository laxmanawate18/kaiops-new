"""Location resolution helpers for the KaiOps agent mesh.

Two distinct locations must NEVER be conflated:

* **Model endpoint location** (``GOOGLE_CLOUD_LOCATION``): the Gemini Enterprise
  endpoint that serves the model. ``gemini-3.6-flash`` is only served on the
  **global** (and multi-region ``us``/``eu``) endpoints, so this is set to
  ``global`` for model routing.

* **Infra location** (``GOOGLE_CLOUD_AGENT_ENGINE_LOCATION``): the region where
  the agent-engine infra lives (Agent Registry, Vertex AI session service,
  A2A card URLs, reasoning engine IDs). This is ALWAYS ``us-central1`` and is
  runtime-injected by Agent Engine.

Setting ``GOOGLE_CLOUD_LOCATION=global`` must NOT bleed into any infra resource
(a registry agent, a session service, or a ``{location}-aiplatform.googleapis.com``
URL would all break). Use :func:`get_infra_location` for every infra resource,
never ``GOOGLE_CLOUD_LOCATION``.
"""
from __future__ import annotations

import os

# The infra region for this deployment. Runtime-injected by Agent Engine when
# deployed; falls back to the canonical us-central1 (matches the gateway,
# semantic governance policy, and all specialist engines).
_DEFAULT_INFRA_LOCATION = "us-central1"


def get_infra_location() -> str:
    """Return the agent-engine INFRA location, decoupled from the model location.

    Resolution order:
    1. ``GOOGLE_CLOUD_AGENT_ENGINE_LOCATION`` (runtime-injected by Agent Engine)
    2. ``GOOGLE_CLOUD_LOCATION`` **only if it is a real single region** (not
       ``global``/``us``/``eu``), so a bare local run still works
    3. ``us-central1``

    Never returns ``global``/``us``/``eu`` — those are MODEL endpoint locations,
    not valid infra regions.
    """
    if engine_loc := os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_LOCATION"):
        return engine_loc

    loc = os.environ.get("GOOGLE_CLOUD_LOCATION", "")
    # A Bare region like "us-central1". Reject model-endpoint aliases.
    if loc and loc not in ("global", "us", "eu", "global-aiplatform"):
        return loc

    return _DEFAULT_INFRA_LOCATION


def get_project_number() -> str:
    """Return the numeric project id, used in resource paths (not the project ID
    string, which the Agent Registry silently drops for some targets)."""
    return os.environ.get("GOOGLE_CLOUD_PROJECT_NUMBER", "275388304596")


def get_project_id() -> str:
    """Return the project ID used for agent-engine resource names."""
    return os.environ.get(
        "GOOGLE_CLOUD_PROJECT",
        os.environ.get("GOOGLE_CLOUD_PROJECT_NUMBER", "project-3da8cb5f-328e-44d3-b7a"),
    )
