from typing import Dict, Optional, List, Tuple, Any
from datetime import datetime, timezone
import uuid
import logging
from google.cloud import firestore

from google.adk.runners import BaseSessionService, Session, Event
from google.adk.sessions.base_session_service import ListSessionsResponse
from app.database.firestore_config import FirestoreConfig
from app.chat.models import MessageSender

logger = logging.getLogger(__name__)

# The synthetic user that owns autonomous (runtime) sessions created by the
# background worker. These sessions are shared/visible to admins & team leads so
# they can open the console link posted in Slack without an ownership mismatch.
SYSTEM_RUNTIME_USER_ID = "sre-agent-runtime"


def _to_iso(value: Any) -> Any:
    """Convert Firestore DatetimeWithNanoseconds/datetime values to ISO strings."""
    if hasattr(value, "isoformat") and not isinstance(value, str):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return value


def _normalize_record(record: Dict[str, Any], keys: Tuple[str, ...] = ("created_at", "last_modified", "timestamp")) -> Dict[str, Any]:
    """Normalize timestamp fields of a Firestore document dict to ISO strings."""
    for key in keys:
        if key in record:
            record[key] = _to_iso(record[key])
    return record


class VertexFirestoreSessionService(BaseSessionService):
    """
    Custom ADK Session Service that persists memory states to Google Cloud (Firestore).
    This bypasses ADK's default SQL/SQLAlchemy DatabaseSessionService entirely,
    providing cloud-native memory and recall.
    
    It also implements the required legacy methods for the REST API.
    """
    
    def __init__(self):
        super().__init__()
        try:
            self.db = FirestoreConfig.get_client()
            self.sessions_ref = self.db.collection('chat_sessions')
            self.messages_ref = self.db.collection('chat_messages')
            # In-memory event replay cache: session_id -> list[Event].
            # ADK's HITL confirmation resume scans prior events of the current
            # invocation; Firestore stores only chat messages, so events must
            # survive in memory across turns (bounded per session).
            self._event_cache: Dict[str, List[Event]] = {}
            logger.info("✅ VertexFirestoreSessionService initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize VertexFirestoreSessionService: {e}")
            raise

    # ==================== ADK BaseSessionService API ====================

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: Optional[dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        
        if not session_id:
            session_id = str(uuid.uuid4())
            
        now = datetime.now(timezone.utc).isoformat()
        
        session_data = {
            "id": session_id,
            "user_id": user_id,
            "app_name": app_name,
            "name": f"Session {now[:10]}",
            "created_at": now,
            "last_modified": now,
            "message_count": 0,
            "is_active": True,
            "metadata": state or {}
        }
        
        self.sessions_ref.document(session_id).set(session_data)
        session = Session(id=session_id, app_name=app_name, user_id=user_id, state=state or {}, events=[])
        self._event_cache[session_id] = session.events
        return session

    async def get_session(
        self,
        *,
        app_name: str,
        user_id: str,
        session_id: str,
        config: Optional[Any] = None,
    ) -> Optional[Session]:
        
        doc = self.sessions_ref.document(session_id).get()
        if not doc.exists:
            return None
            
        data = doc.to_dict()
        if data.get("user_id") != user_id or data.get("app_name") != app_name:
            return None
            
        # Reattach the in-memory event list so ADK's HITL confirmation resume
        # can scan prior events across turns.
        events = self._event_cache.get(session_id, [])
        session = Session(id=session_id, app_name=app_name, user_id=user_id, state=data.get("metadata", {}), events=events)
        self._event_cache[session_id] = session.events
        return session

    async def list_sessions(
        self, *, app_name: str, user_id: Optional[str] = None
    ) -> ListSessionsResponse:
        
        query = self.sessions_ref.where("app_name", "==", app_name)
        if user_id:
            query = query.where("user_id", "==", user_id)
            
        sessions = []
        for doc in query.stream():
            data = doc.to_dict()
            uid = data.get("user_id", user_id or "")
            sessions.append(Session(id=doc.id, app_name=app_name, user_id=uid, state=data.get("metadata", {}), events=[]))
            
        return ListSessionsResponse(sessions=sessions, next_page_token="")

    async def delete_session(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> None:
        doc = self.sessions_ref.document(session_id).get()
        if doc.exists and doc.to_dict().get("user_id") == user_id:
            self.sessions_ref.document(session_id).delete()
            # Also delete messages
            for msg in self.messages_ref.where("session_id", "==", session_id).stream():
                msg.reference.delete()

    async def append_event(self, session: Session, event: Event) -> Event:
        # ADK >= 1.x BaseSessionService.append_event already trims temp delta
        # state and applies state deltas to session.state.
        event = await super().append_event(session, event)

        # Keep the event on the in-memory Session object. ADK's HITL
        # confirmation flow (request_confirmation processor) scans prior
        # session events within the current invocation to resume guarded tool
        # calls — dropping them here breaks restart_pod/rollback approvals.
        # We still don't persist raw events to Firestore; only chat messages
        # are saved via add_message.
        session.events.append(event)
        return event

    # ==================== Legacy REST API Methods (from ChatDatabase) ====================
    # Note: Many of these are synchronous because the routes expect synchronous DB calls.
    # In a full refactor, the routes should be async. We provide sync wrappers/logic here.

    def create_api_session(self, user_id: str, session_name: Optional[str] = None) -> Dict[str, Any]:
        """Creates a session (sync version for API)."""
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        if not session_name:
            session_name = f"New Chat {now[:10]}"
            
        session_data = {
            "id": session_id,
            "user_id": user_id,
            "name": session_name,
            "created_at": now,
            "last_modified": now,
            "message_count": 0,
            "is_active": True,
            "metadata": {}
        }
        
        self.sessions_ref.document(session_id).set(session_data)
        return session_data

    def get_user_sessions(self, user_id: str, include_inactive: bool = True) -> List[Dict[str, Any]]:
        query = self.sessions_ref.where("user_id", "==", user_id)
        if not include_inactive:
            query = query.where("is_active", "==", True)
            
        sessions = []
        for doc in query.stream():
            data = _normalize_record(doc.to_dict())
            if "id" not in data:
                data["id"] = doc.id
            sessions.append(data)

        def _sort_key(session: Dict[str, Any]) -> str:
            """Normalize last_modified (Firestore timestamp or ISO string) for sorting."""
            value = session.get("last_modified", "")
            if hasattr(value, "isoformat"):
                return value.isoformat()
            return str(value or "")

        return sorted(sessions, key=_sort_key, reverse=True)

    def get_api_session(self, user_id: str, session_id: str, allow_runtime: bool = False) -> Optional[Dict[str, Any]]:
        doc = self.sessions_ref.document(session_id).get()
        if not doc.exists:
            return None
        data = _normalize_record(doc.to_dict())
        # Runtime (autonomous worker) sessions are owned by the synthetic system
        # user. Admins/team leads are allowed to open them read-only so the Slack
        # console deep-link works. Note this does NOT grant message-write access.
        owner = data.get("user_id")
        if owner != user_id and not (allow_runtime and owner == SYSTEM_RUNTIME_USER_ID):
            return None
        if "id" not in data:
            data["id"] = doc.id
        return data

    def update_session(self, user_id: str, session_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        doc_ref = self.sessions_ref.document(session_id)
        doc = doc_ref.get()
        
        if not doc.exists or doc.to_dict().get("user_id") != user_id:
            return None
            
        updates = {"last_modified": datetime.now(timezone.utc).isoformat()}
        if "name" in kwargs:
            updates["name"] = kwargs["name"]
        if "is_active" in kwargs:
            updates["is_active"] = kwargs["is_active"]
        if "metadata" in kwargs:
            updates["metadata"] = kwargs["metadata"]
            
        doc_ref.update(updates)
        return self.get_api_session(user_id, session_id)

    def delete_api_session(self, user_id: str, session_id: str) -> bool:
        doc_ref = self.sessions_ref.document(session_id)
        doc = doc_ref.get()
        
        if not doc.exists or doc.to_dict().get("user_id") != user_id:
            return False
            
        doc_ref.delete()
        self.clear_session_messages(user_id, session_id)
        return True

    def delete_all_user_sessions(self, user_id: str) -> int:
        sessions = self.get_user_sessions(user_id)
        count = 0
        batch = self.db.batch()
        batch_size = 0

        for s in sessions:
            session_id = s["id"]
            # Verify ownership before deleting
            doc = self.sessions_ref.document(session_id).get()
            if not doc.exists or doc.to_dict().get("user_id") != user_id:
                continue

            batch.delete(self.sessions_ref.document(session_id))
            batch_size += 1
            count += 1

            # Firestore batch limit is 500 operations
            if batch_size >= 400:
                batch.commit()
                batch = self.db.batch()
                batch_size = 0

            # Delete messages for this session in a separate batch
            msg_batch = self.db.batch()
            msg_count = 0
            for msg in self.messages_ref.where("session_id", "==", session_id).stream():
                msg_batch.delete(msg.reference)
                msg_count += 1
                if msg_count >= 400:
                    msg_batch.commit()
                    msg_batch = self.db.batch()
                    msg_count = 0
            if msg_count > 0:
                msg_batch.commit()

        if batch_size > 0:
            batch.commit()

        return count

    def add_message(
        self, 
        user_id: str, 
        session_id: str, 
        sender: MessageSender, 
        text: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        
        session = self.get_api_session(user_id, session_id)
        if not session:
            return None

        # Single write choke-point sanitization: neutralize active content
        # (<script>, inline handlers, javascript:) in stored text. Rendering
        # stays the frontend's job; this is defense-in-depth so raw payloads
        # are not persisted verbatim forever.
        if text:
            import re as _re
            text = _re.sub(
                r"<script\b[^>]*>.*?</script\s*>", "[removed script]", text,
                flags=_re.IGNORECASE | _re.DOTALL,
            )
            text = _re.sub(r"<script\b[^>]*/?>", "[removed script]", text,
                           flags=_re.IGNORECASE)
            text = _re.sub(
                r"\bon[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)",
                "[removed handler]", text, flags=_re.IGNORECASE,
            )
            text = _re.sub(r"javascript\s*:", "[removed scheme]", text,
                           flags=_re.IGNORECASE)
            
        msg_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        msg_data = {
            "id": msg_id,
            "session_id": session_id,
            "user_id": user_id,
            "sender": sender.value if isinstance(sender, MessageSender) else sender,
            "text": text,
            "timestamp": now,
            "metadata": metadata or {}
        }
        
        self.messages_ref.document(msg_id).set(msg_data)
        
        self.sessions_ref.document(session_id).update({
            "last_modified": now,
            "message_count": firestore.Increment(1)
        })
        
        return msg_data

    def get_messages(self, user_id: str, session_id: str, limit: Optional[int] = None, offset: int = 0, allow_runtime: bool = False) -> Tuple[Optional[List[Dict[str, Any]]], int]:
        session = self.get_api_session(user_id, session_id, allow_runtime=allow_runtime)
        if not session:
            return None, 0
            
        query = self.messages_ref.where("session_id", "==", session_id).order_by("timestamp")
        
        if offset > 0:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
            
        messages = []
        for doc in query.stream():
            data = _normalize_record(doc.to_dict())
            if "id" not in data:
                data["id"] = doc.id
            messages.append(data)
            
        total_query = self.messages_ref.where("session_id", "==", session_id)
        total = total_query.count().get()[0][0].value
        
        return messages, total

    def resolve_gate_message(self, session_id: str, approval_token: str, resolution: str) -> int:
        """Neutralize a consumed HITL gate message so UI refetches can never
        re-render it as actionable (the 'second approval card' bug).

        Finds the assistant message in this session whose metadata carries the
        matching approval_token and stamps it resolved. Returns count updated.
        """
        try:
            db = FirestoreConfig.get_client()
            coll = db.collection("chat_messages")
            query = (
                coll.where(filter=firestore.FieldFilter("session_id", "==", session_id))
                .where(filter=firestore.FieldFilter("metadata.approval_token", "==", approval_token))
                .limit(5)
            )
            updated = 0
            for doc in query.stream():
                data = doc.to_dict() or {}
                meta = dict(data.get("metadata") or {})
                meta["approval_token"] = None
                meta["requires_confirmation"] = False
                meta["resolved"] = True
                meta["resolution"] = resolution
                doc.reference.update({"metadata": meta})
                updated += 1
            if updated:
                logger.info(
                    "[OK] Resolved %d gate message(s) in session %s (%s)",
                    updated, session_id, resolution,
                )
            return updated
        except Exception as e:  # noqa: BLE001 - cosmetic fix must never break approval flow
            logger.warning("[WARN] resolve_gate_message failed: %s", e)
            return 0

    def clear_session_messages(self, user_id: str, session_id: str) -> bool:
        session = self.get_api_session(user_id, session_id)
        if not session:
            return False
            
        count = 0
        for msg in self.messages_ref.where("session_id", "==", session_id).stream():
            msg.reference.delete()
            count += 1
            
        self.sessions_ref.document(session_id).update({
            "message_count": 0,
            "last_modified": datetime.now(timezone.utc).isoformat()
        })
        
        return True

    def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        sessions = self.get_user_sessions(user_id)
        
        total_sessions = len(sessions)
        active_sessions = sum(1 for s in sessions if s.get("is_active", False))
        
        total_msgs = self.messages_ref.where("user_id", "==", user_id).count().get()[0][0].value
            
        today = datetime.now(timezone.utc).date().isoformat()
        today_sessions = sum(1 for s in sessions if s.get("created_at", "").startswith(today))
        
        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "total_messages": total_msgs,
            "sessions_created_today": today_sessions
        }

    def get_all_stats(self) -> Dict[str, Any]:
        return {
            "total_sessions": self.sessions_ref.count().get()[0][0].value,
            "total_messages": self.messages_ref.count().get()[0][0].value,
        }
