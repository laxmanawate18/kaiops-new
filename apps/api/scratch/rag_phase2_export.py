"""Phase 2: Export approved feedback + past incidents into RAG-knowledge docs.

Reads Firestore (approved feedback + chat_messages grouped by session), writes
Markdown knowledge docs to a GCS dir, ready for rag.import_files.
"""
import os, sys, io, json, subprocess
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("CLOUDSDK_PYTHON", r"C:\Users\laxma\AppData\Local\Programs\Python\Python310\python.EXE")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GCLOUD = r"C:\Users\laxma\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
PROJ = "project-3da8cb5f-328e-44d3-b7a"
GCS_BASE = f"gs://{PROJ}-rag-staging/kaiops-knowledge"
OUT_DIR = r"f:\Personal\AI-Project\kaiops_latest\apps\api\scratch\rag_knowledge_docs"
sys.path.insert(0, r"f:\Personal\AI-Project\kaiops_latest\kaiops\apps\api")
import os as _os
_os.chdir(r"f:\Personal\AI-Project\kaiops_latest\kaiops\apps\api")
_os.environ["GOOGLE_CLOUD_PROJECT"] = PROJ
from dotenv import load_dotenv
load_dotenv()
from app.database.firestore_config import FirestoreConfig

db = FirestoreConfig.get_client()


def write_doc(name, content):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("wrote:", name)


def export_approved_feedback():
    docs = []
    for doc in db.collection("feedback").stream():
        d = doc.to_dict()
        if str(d.get("status", "")).upper() == "APPROVED":
            content = (
                f"# Approved Feedback (expert-validated guidance)\n\n"
                f"## User question\n{d.get('user_message') or d.get('comment') or '(n/a)'}\n\n"
                f"## Agent response (validated)\n{d.get('ai_response') or '(n/a)'}\n\n"
                f"## Label\nFeedback type: {d.get('feedback_type')}, rating: {d.get('rating')}, "
                f"tags: {d.get('tags') or []}\n\n## Suggested better response\n"
                f"{d.get('suggested_response') or '(none)'}\n"
            )
            write_doc(f"approved-feedback-{doc.id}.md", content)
            docs.append(doc.id)
    return docs


def export_past_incidents(max_sessions=40):
    # Group messages by session
    msgs_by_sid = {}
    for doc in db.collection("chat_messages").stream():
        d = doc.to_dict()
        msgs_by_sid.setdefault(d.get("session_id") or "unknown", []).append(
            {"sender": d.get("sender", ""), "text": d.get("text", "") or ""}
        )
    # session meta
    sessions = {}
    for doc in db.collection("chat_sessions").stream():
        d = doc.to_dict()
        sessions[doc.id] = (d.get("name") or "Session") 
    n = 0
    for sid, msgs in msgs_by_sid.items():
        if n >= max_sessions:
            break
        if not msgs:
            continue
        name = sessions.get(sid, "Incident")
        lines = [f"# Past Incident: {name}\n\n"]
        lines.append(f"Session: {sid}\n\n## Conversation\n")
        for m in msgs:
            who = "USER" if str(m["sender"]).lower() in ("user", "human") else "AGENT"
            txt = (m["text"] or "")[:600]
            if txt.strip():
                lines.append(f"**{who}:** {txt}\n")
        write_doc(f"incident-{sid[:12]}.md", "\n".join(lines))
        n += 1
    return n


def upload_all():
    # Batch-upload the whole docs dir in one gcloud call (fast).
    subprocess.run([GCLOUD, "storage", "cp", os.path.join(OUT_DIR, "*"), GCS_BASE + "/", "--project=" + PROJ],
                   capture_output=True, timeout=300)
    print("uploaded dir to", GCS_BASE)


if __name__ == "__main__":
    fb = export_approved_feedback()
    print("approved feedback docs:", len(fb))
    inc = export_past_incidents()
    print("incident docs:", inc)
    upload_all()
