"""Monitor the RAG orchestrator deploy. Detects a NEW orchestrator-gov engine
(newer than 3796153505094303744), writes its ID + status to a result file."""
import os, io, sys, subprocess, json, time, urllib.request, urllib.error
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ.setdefault("CLOUDSDK_PYTHON", r"C:\Users\laxma\AppData\Local\Programs\Python\Python310\python.EXE")
gcloud = r"C:\Users\laxma\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
PROJ = "project-3da8cb5f-328e-44d3-b7a"; LOC = "us-central1"
RESULT = r"f:\Personal\AI-Project\kaiops_latest\apps\api\scratch\rag_new_engine.txt"
OLD_IDS = {"3796153505094303744", "2282662555321106432"}  # exclude prior engines

def token():
    r = subprocess.run([gcloud, "auth", "application-default", "print-access-token"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    return r.stdout.strip().splitlines()[-1].strip()

def get_engines():
    tk = token()
    req = urllib.request.Request(
        f"https://{LOC}-aiplatform.googleapis.com/v1beta1/projects/{PROJ}/locations/{LOC}/reasoningEngines",
        headers={"Authorization": f"Bearer {tk}"}, method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode()).get("reasoningEngines", [])

for i in range(60):  # up to ~10 min
    try:
        engs = get_engines()
        cand = [e for e in engs if e.get("createTime", "") > "2026-08-29T13:51:14" or e.get("description", "").find("orchestrator") >= 0]
        # find newest that isn't the old ID
        for e in sorted(engs, key=lambda e: e.get("createTime", ""), reverse=True):
            nm = e.get("name", "").split("/")[-1]
            if nm not in OLD_IDS and e.get("createTime", "") > "2026-08-29T13:51:14":
                with open(RESULT, "w", encoding="utf-8") as f:
                    f.write(nm)
                print(f"FOUND new engine id={nm} createTime={e.get('createTime')[:19]} state={e.get('spec',{}).get('state','?')}", flush=True)
                sys.exit(0)
        print(f"t={i*10}s no new engine yet (total={len(engs)})", flush=True)
    except Exception as e:
        print(f"t={i*10}s poll err: {type(e).__name__} {str(e)[:120]}", flush=True)
    time.sleep(10)
print("TIMEOUT", flush=True)
