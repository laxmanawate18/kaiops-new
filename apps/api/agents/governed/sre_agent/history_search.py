"""Search past incidents and approved feedback for similar issues."""
import logging
import os

logger = logging.getLogger(__name__)


def _get_db():
    from google.cloud import firestore  # noqa: F401
    from app.database.firestore_config import FirestoreConfig
    return FirestoreConfig.get_client()


def _score_text(text: str, terms: list) -> int:
    """Count how many query terms (>2 chars) appear in the text."""
    if not text:
        return 0
    lowered = text.lower()
    return sum(1 for t in terms if t in lowered)


def search_past_incidents(query: str, limit: int = 3) -> str:
    """Search previous investigation sessions for messages similar to the query.

    Strategy: fetch recent assistant messages (last N days), score by keyword overlap
    with the query, return top matches with session context.
    Firestore has no full-text search; keyword scoring client-side over a bounded
    recent window (e.g., 200 most recent assistant messages) is acceptable at this scale.
    """
    try:
        db = _get_db()
        terms = [t.lower() for t in query.split() if len(t) > 2]
        if not terms:
            return "No usable keywords in query for historical search."

        # No order_by here: where+order_by requires a composite Firestore index.
        # Fetch a bounded window and sort client-side instead.
        docs = (
            db.collection("chat_messages")
            .where("sender", "==", "assistant")
            .limit(200)
            .stream()
        )

        scored = []
        for doc in docs:
            data = doc.to_dict() or {}
            text = data.get("text") or ""
            score = _score_text(text, terms)
            if score >= 2:
                scored.append((score, data))

        scored.sort(key=lambda x: (x[0], str(x[1].get("timestamp", ""))), reverse=True)
        top = scored[:limit]

        if not top:
            return "No similar past investigations found."

        lines = []
        for score, data in top:
            ts = data.get("timestamp", "unknown date")
            snippet = (data.get("text") or "")[:300].replace("\n", " ")
            session_id = data.get("session_id", "?")
            lines.append(
                f"🧠 Similar past investigation (score {score}, {ts}, session {session_id}):\n"
                f"   {snippet}..."
            )
        return "\n\n".join(lines)
    except Exception as e:
        logger.error("search_past_incidents failed: %s", e, exc_info=True)
        return f"⚠️ Past incident search unavailable: {e}"


def search_approved_feedback(query: str, limit: int = 3) -> str:
    """Search APPROVED feedback entries for expert-validated guidance."""
    try:
        db = _get_db()
        terms = [t.lower() for t in query.split() if len(t) > 2]
        if not terms:
            return "No usable keywords in query for feedback search."

        # Feedback docs store status ('APPROVED'/'PENDING'/'DENIED'), comment/content text,
        # ai_response and user_message. Keyword-score against all text fields.
        docs = (
            db.collection("feedback")
            .where("status", "==", "APPROVED")
            .limit(200)
            .stream()
        )

        scored = []
        for doc in docs:
            data = doc.to_dict() or {}
            combined = " ".join(
                str(data.get(f) or "")
                for f in ("comment", "content", "ai_response", "user_message", "suggested_response")
            )
            score = _score_text(combined, terms)
            if score >= 2:
                scored.append((score, data))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:limit]

        if not top:
            return "No approved feedback matching this issue found."

        lines = []
        for score, data in top:
            created = data.get("created_at", "unknown date")
            text = data.get("comment") or data.get("content") or data.get("ai_response") or ""
            snippet = text[:300].replace("\n", " ")
            rating = data.get("rating")
            lines.append(
                f"✅ Expert-approved guidance (score {score}, {created}, rating={rating}):\n"
                f"   {snippet}..."
            )
        return "\n\n".join(lines)
    except Exception as e:
        logger.error("search_approved_feedback failed: %s", e, exc_info=True)
        return f"⚠️ Approved feedback search unavailable: {e}"
