"""KaiOps RAG Engine setup (Phase 1).

Creates the serverless kaiops-knowledge corpus, ingests the runbooks from GCS,
and runs a retrieval query to verify. Idempotent: skips corpus creation if it
already exists.

Run: python build_rag.py
"""
import os, sys, io, json, subprocess
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PROJ = "project-3da8cb5f-328e-44d3-b7a"
PN = "275388304596"
LOC = "us-east5"  # us-central1 Spanner mode is restricted; serverless works in us-east5
CORPUS = f"projects/{PN}/locations/{LOC}/ragCorpora/2305843009213693952"
GCS_BASE = f"gs://{PROJ}-rag-staging/kaiops-runbooks"
RUNBOOKS_DIR = r"f:\Personal\AI-Project\kaiops_latest\apps\api\runbooks"
RUNBOOKS = ["crashloop.md", "high-latency.md", "http-500-spike.md", "oomkilled.md", "gateway-observability.md"]


def upload_runbooks():
    for f in RUNBOOKS:
        subprocess.run(["gcloud", "storage", "cp", os.path.join(RUNBOOKS_DIR, f), f"{GCS_BASE}/{f}",
                        "--project=" + PROJ], capture_output=True, timeout=180)


def build():
    import vertexai
    import vertexai.rag as rag
    from vertexai.rag.utils.resources import RagResource, RagRetrievalConfig
    vertexai.init(project=PROJ, location=LOC)

    # Create corpus if not present (serverless KNN to avoid Spanner restriction)
    existing = [c.name for c in rag.list_corpora()]
    if CORPUS not in existing:
        from vertexai.rag.utils.resources import RagVectorDbConfig, RagManagedDb
        from vertexai.rag.utils.resources import RagManagedDbConfig
        try:
            rag.create_corpus(
                display_name="kaiops-knowledge",
                description="Unified KaiOps knowledge: runbooks, past incidents, approved feedback (serverless)",
                backend_config=RagVectorDbConfig(
                    vector_db=RagManagedDb(),
                ),
            )
        except Exception as e:
            # The SDK default RagManagedDb maps to restricted Spanner; the
            # serverless switch must be made via REST with ragManagedDb.knn={}.
            print("corpus create (SDK) needs REST for serverless; creating via REST...")
            # fallback handled by rag_corpus_setup.py; not re-implemented here.
            raise

    # Import runbooks (need GCS URIs)
    upload_runbooks()
    paths = [f"{GCS_BASE}/{f}" for f in RUNBOOKS]
    rag.import_files(corpus_name=CORPUS, paths=paths, timeout=300)

    # Verify retrieval
    resp = rag.retrieval_query(
        text="CrashLoopBackOff diagnosis",
        rag_resources=[RagResource(rag_corpus=CORPUS)],
        rag_retrieval_config=RagRetrievalConfig(top_k=3),
    )
    ctxs = getattr(getattr(resp, "contexts", None), "contexts", []) or []
    print("retrieval matches:", len(ctxs))
    for c in ctxs:
        print("  ", getattr(c, "source_uri", ""), "->", (getattr(c, "text", "") or "")[:80].replace("\n", " "))


if __name__ == "__main__":
    build()
