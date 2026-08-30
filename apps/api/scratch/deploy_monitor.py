"""Monitor backend build + deploy. Logs to deploy_monitor.log."""
import subprocess, os, time, sys, io
os.environ["CLOUDSDK_PYTHON"] = r"C:\Users\laxma\AppData\Local\Programs\Python\Python310\python.EXE"
GCLOUD = r"C:\Users\laxma\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
PROJ = "project-3da8cb5f-328e-44d3-b7a"
LOG = r"f:\Personal\AI-Project\kaiops_latest\deploy_monitor_out.log"
DEPLOY_LOG = r"f:\Personal\AI-Project\kaiops_latest\deploy_backend_run.log"
BUILD = "acfd6401-ba65-4631-a01f-2fb1c9cdbe70"

def log(m):
    with open(LOG,"a",encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {m}\n")
    print(m, flush=True)

def gcloud(args, timeout=60):
    r=subprocess.run([GCLOUD]+args,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=timeout)
    return r.stdout.strip(), r.returncode

for i in range(120):  # up to ~10 min
    status, rc = gcloud(["builds","describe",BUILD,"--project="+PROJ,"--format=value(status)"])
    log(f"t={i*5}s build={status}")
    if status in ("SUCCESS","FAILURE","CANCELLED","EXPIRED"):
        log(f"BUILD FINAL: {status}")
        break
    # also peek at deploy log tail
    try:
        with open(DEPLOY_LOG,"rb") as f:
            tail=f.read().decode("utf-8",errors="replace")[-1200:]
        if "DEPLOY END" in tail or "Deployed" in tail or "Deployment failed" in tail:
            log("DEPLOY LOG shows terminal marker")
    except Exception:
        pass
    time.sleep(5)
log("monitor done (build monitor)")
