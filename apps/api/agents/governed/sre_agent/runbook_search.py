"""Real Vertex AI Search grounding for SRE runbooks.

Searches an enterprise runbook data store via Vertex AI Search (Discovery Engine)
using the REST API — proven reliable for unstructured data stores where the gRPC
SDK channel may not be provisioned.

Never fabricates content: if unconfigured or failing, returns an explicit message.
"""
import os
import logging
import re
import time
from functools import lru_cache

import requests
import google.auth
from google.auth.transport.requests import Request as GoogleAuthRequest

logger = logging.getLogger(__name__)

DATA_STORE_ID = os.getenv("VERTEX_SEARCH_DATA_STORE_ID", "")

_TOKEN_CACHE: dict = {"token": None, "expires_at": 0}


def project_id_from_path(data_store_id: str):
    parsed = _parse_data_store(data_store_id)
    return parsed[0] if parsed else None


@lru_cache(maxsize=1)
def _parse_data_store(data_store_id: str):
    """Parse a full data store resource path into (project, location, collection, data_store)."""
    parts = data_store_id.strip("/").split("/")
    # projects/{p}/locations/{l}/collections/{c}/dataStores/{d}
    if len(parts) == 8 and parts[0] == "projects" and parts[2] == "locations":
        return parts[1], parts[3], parts[5], parts[7]
    return None


def _get_token() -> str:
    """Fetch (and cache) an ADC access token with the quota project set."""
    now = time.time()
    if _TOKEN_CACHE["token"] and now < _TOKEN_CACHE["expires_at"] - 60:
        return _TOKEN_CACHE["token"]

    credentials, _project = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
        quota_project_id=project_id_from_path(DATA_STORE_ID) or None,
    )
    request = GoogleAuthRequest()
    credentials.refresh(request)
    _TOKEN_CACHE["token"] = credentials.token
    _TOKEN_CACHE["expires_at"] = time.time() + 3600
    return credentials.token


def _fetch_document_body(project: str, location: str, collection: str, data_store: str, doc_id: str) -> str:
    """Fetch a document's raw content by id. Returns '' on any failure."""
    try:
        url = (
            f"https://{location}-discoveryengine.googleapis.com/v1/"
            f"projects/{project}/locations/{location}/collections/{collection}/"
            f"dataStores/{data_store}/branches/default_branch/documents/{doc_id}"
        )
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {_get_token()}",
                "X-Goog-User-Project": project,
            },
            timeout=10,
        )
        response.raise_for_status()
        content = response.json().get("content", {})
        raw = content.get("rawData") or ""
        if not raw and content.get("rawBytes"):
            import base64
            raw = base64.b64decode(content["rawBytes"]).decode("utf-8", errors="replace")
        return raw
    except Exception as e:
        logger.warning("Could not fetch document body for %s: %s", doc_id, e)
        return ""


def _best_section(raw: str, query: str, max_chars: int = 900) -> str:
    """Return the document section most relevant to the query terms."""
    if not raw:
        return ""
    # Split on markdown headings; fall back to paragraphs.
    sections = re.split(r"\n#{1,3} ", raw) if "\n#" in raw else re.split(r"\n\s*\n", raw)
    terms = [t.lower() for t in re.split(r"\W+", query) if len(t) > 2]
    best, best_score = "", -1
    for section in sections:
        text = section.strip()
        if not text:
            continue
        score = sum(text.lower().count(t) for t in terms)
        if score > best_score:
            best, best_score = text, score
    best = best or raw.strip()
    return best[:max_chars] + ("…" if len(best) > max_chars else "")


def search_runbooks(query: str, top_k: int = 3) -> str:
    """Search enterprise SRE runbooks via Vertex AI Search (REST).

    Returns formatted runbook excerpts with source citations.
    Falls back to a clear 'unavailable' message if not configured — NEVER fake content.
    """
    if not DATA_STORE_ID:
        return (
            "⚠️ Runbook search unavailable: VERTEX_SEARCH_DATA_STORE_ID not configured. "
            "Set it to the full data store resource path "
            "(projects/<proj>/locations/global/collections/default_collection/dataStores/<id>)."
        )

    parsed = _parse_data_store(DATA_STORE_ID)
    if not parsed:
        return f"⚠️ Runbook search unavailable: invalid data store path '{DATA_STORE_ID}'."

    project, location, collection, data_store = parsed
    url = (
        f"https://{location}-discoveryengine.googleapis.com/v1/"
        f"projects/{project}/locations/{location}/collections/{collection}/"
        f"dataStores/{data_store}/servingConfigs/default_search:search"
    )

    try:
        token = _get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Goog-User-Project": project,
            "Content-Type": "application/json",
        }
        response = requests.post(
            url,
            headers=headers,
            json={"query": query, "pageSize": top_k},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()

        results = []
        for item in payload.get("results", []):
            doc = item.get("document", {})
            struct = doc.get("structData", {}) or {}
            derived = doc.get("derivedStructData", {}) or {}
            title = struct.get("title") or derived.get("title") or doc.get("id", "(untitled)")
            uri = struct.get("uri") or struct.get("link") or ""
            doc_id = doc.get("id", "")

            body_parts = []
            for ans in derived.get("extractive_answers", []) or []:
                text = ans.get("extractiveAnswer", "")
                if text:
                    body_parts.append(text.strip())
            for snip in derived.get("snippets", []) or []:
                text = snip.get("snippet", "")
                if text:
                    clean = re.sub(r"<[^>]+>", "", text).strip()
                    if clean:
                        body_parts.append(clean)

            # Extractive answers may be empty for freshly-indexed unstructured
            # docs — fall back to fetching the document body directly and
            # returning the most relevant section.
            if not body_parts and doc_id:
                raw = _fetch_document_body(project, location, collection, data_store, doc_id)
                if raw:
                    body_parts.append(_best_section(raw, query))

            body = "\n   ".join(body_parts[:2]) if body_parts else ""
            entry = f"📘 {title}"
            if uri:
                entry += f"\n   Source: {uri}"
            if body:
                entry += f"\n   {body}"
            results.append(entry)

        if not results:
            return (
                f"🔍 No runbook documents found in Vertex AI Search for query: '{query}'. "
                "The data store may be empty."
            )

        header = f"📚 Runbook search results for '{query}' ({len(results)} found):\n\n"
        return header + "\n\n---\n\n".join(results)

    except Exception as e:  # honest failure — never fake content
        logger.error("Runbook search failed: %s", e, exc_info=True)
        return f"⚠️ Runbook search failed: {e}"
