"""Phase 2: import knowledge docs (approved feedback + incidents) into the corpus."""
import os, io, sys
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ["GOOGLE_CLOUD_PROJECT"] = "project-3da8cb5f-328e-44d3-b7a"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-east5"
import vertexai
vertexai.init(project="project-3da8cb5f-328e-44d3-b7a", location="us-east5")
import vertexai.rag as rag

corpus = "projects/275388304596/locations/us-east5/ragCorpora/2305843009213693952"
files = open(r"f:\Personal\AI-Project\kaiops_latest\apps\api\scratch\rag_knowledge_files.txt").read().split()

# Max 25 GCS URIs per request
for i in range(0, len(files), 25):
    batch = files[i:i + 25]
    try:
        resp = rag.import_files(corpus_name=corpus, paths=batch, timeout=600)
        imp = getattr(resp, "imported_rag_files", [])
        print(f"batch [{i}:{i+len(batch)}]: OK imported={len(imp)} failed={getattr(resp,'failed_files',None)}")
    except Exception as e:
        print(f"batch [{i}:{i+len(batch)}]: ERR {type(e).__name__}: {str(e)[:200]}")
