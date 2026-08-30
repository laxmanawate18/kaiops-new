"""Deploy the RAG-enabled governed orchestrator.

Loads real secrets from Secret Manager (replacing the redacted .env
placeholders), sets the RAG corpus env, then runs run_deploy_governed.py
orchestrator (gateway-bound). Writes to deploy_governed_orchestrator.log.
"""
import os, sys, io, subprocess
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.environ.setdefault("CLOUDSDK_PYTHON", r"C:\Users\laxma\AppData\Local\Programs\Python\Python310\python.EXE")
GCLOUD = r"C:\Users\laxma\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"

# Real secret values -> Secret Manager name (replaces placeholders)
MAP = {
    "AZURE_CLIENT_SECRET": "kaiops-azure-client-secret",
    "ARGOCD_AUTH_TOKEN": "kaiops-argocd-token",
    "ARGOCD_PASSWORD": "kaiops-argocd-password",
    "GITHUB_TOKEN": "kaiops-github-token",
    "GRAFANA_TOKEN": "kaiops-grafana-token",
    "GRAFANA_API_KEY": "kaiops-grafana-token",
    "GRAFANA_PASSWORD": "kaiops-grafana-password",
    "AWS_ACCESS_KEY_ID": "kaiops-aws-access-key-id",
    "AWS_SECRET_ACCESS_KEY": "kaiops-aws-secret-access-key",
    "SECRET_KEY": "kaiops-jwt-secret",
}
for k, sn in MAP.items():
    r = subprocess.run([GCLOUD, "secrets", "versions", "access", "latest", "--secret=" + sn],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=os.environ.copy(), timeout=60)
    if r.returncode == 0:
        os.environ[k] = r.stdout.strip()
    else:
        print(f"[warn] {k} ({sn}): {r.stderr.strip()[:120]}")

print("env secrets loaded:", [k for k in MAP if os.environ.get(k)])

# RAG env (corpus defaults are in code; set explicitly for clarity)
os.environ.setdefault("KAIOPS_RAG_CORPUS",
                      "projects/275388304596/locations/us-east5/ragCorpora/2305843009213693952")
os.environ.setdefault("KAIOPS_RAG_LOCATION", "us-east5")
os.environ.setdefault("KAIOPS_RAG_TOP_K", "4")
os.environ.setdefault("A2A_SHARED_TOKEN", "localtok123")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "project-3da8cb5f-328e-44d3-b7a")
# 🔒 DECOUPLE model vs infra locations:
#   GOOGLE_CLOUD_LOCATION = global  -> MODEL endpoint (gemini-3.6-flash is served
#       ONLY on the global / multi-region endpoint; single-region us-central1 404s).
#   GOOGLE_CLOUD_AGENT_ENGINE_LOCATION = us-central1 -> INFRA (gateway, Agent
#       Registry, Vertex AI session service, A2A URLs). The agent code + deploy
#       script already route all INFRA resourced via this var (gcp_location helper),
#       so setting GOOGLE_CLOUD_LOCATION=global never leaks into infra.
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_CLOUD_AGENT_ENGINE_LOCATION"] = "us-central1"
os.environ["KAI_OPS_MODEL_LOCATION"] = "global"
# 🔒 HARD RULE: gemini-3.6-flash is the canonical model everywhere. Pin it
# explicitly so the final governed orchestrator runs 3.6-flash (not a stale
# value inherited from a prior deploy or a .env default).
os.environ["GEMINI_MODEL"] = "gemini-3.6-flash"

# Run the deploy (gateway-bound orchestrator). cd to agents dir.
os.chdir(r"f:\Personal\AI-Project\kaiops_latest\kaiops\apps\api\agents")
subprocess.run([r"f:\Personal\AI-Project\kaiops_latest\.venv\Scripts\python.exe",
                "run_deploy_governed.py", "orchestrator"], check=False, env=os.environ.copy())
print("RUNNER EXITED")
