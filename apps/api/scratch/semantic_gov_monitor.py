"""Poll the Semantic Governance Policy Engine until ACTIVE, then create the RCA policy.

Detached runner: waits for the engine to finish provisioning, then issues
`gcloud ai semantic-governance-policies create` for kaiops-rca-governance.
Logs to semantic_gov_monitor.log.
"""
import os
import subprocess
import sys
import time
import json

os.environ["CLOUDSDK_PYTHON"] = r"C:\Users\laxma\AppData\Local\Programs\Python\Python310\python.EXE"
GCLOUD = r"C:\Users\laxma\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
PROJ = "project-3da8cb5f-328e-44d3-b7a"
LOC = "us-central1"
LOG = r"f:\Personal\AI-Project\kaiops_latest\apps\api\scratch\semantic_gov_monitor.log"

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    print(msg, flush=True)

def gcloud(args, timeout=90):
    r = subprocess.run([GCLOUD] + args, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    return r.stdout, r.stderr, r.returncode

def token():
    out, _, rc = gcloud(["auth", "application-default", "print-access-token"], timeout=30)
    if rc != 0:
        return ""
    lines = [l for l in out.strip().splitlines() if l.strip()]
    return lines[-1].strip() if lines else ""

def engine_state(tk):
    import urllib.request
    url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJ}/locations/{LOC}/semanticGovernancePolicyEngine"
    try:
        rq = urllib.request.Request(url, headers={"Authorization": f"Bearer {tk}"})
        with urllib.request.urlopen(rq, timeout=30) as resp:
            return json.loads(resp.read().decode()).get("state")
    except Exception as e:
        return f"ERR:{e}"

tk = token()
log(f"started monitor. engine state = {engine_state(tk)}")

for i in range(60):  # up to ~10 min
    st = engine_state(tk)
    log(f"t={i*10}s engine={st}")
    if st == "ACTIVE":
        log("ENGINE ACTIVE -> creating policy")
        agent = "projects/project-3da8cb5f-328e-44d3-b7a/locations/us-central1/agents/agentregistry-00000000-0000-0000-763e-c9a9f19b670e"
        constraint = ("The orchestrator agent must delegate Root Cause Analysis (RCA) to the cloud "
                      "specialist A2A agents and synthesize their findings. It MUST NOT deploy, roll back, "
                      "restart, scale, or otherwise mutate production infrastructure, and MUST NOT expose "
                      "secrets or credentials. Any destructive action requires explicit human approval.")
        out, err, rc = gcloud(["ai", "semantic-governance-policies", "create", "kaiops-rca-governance",
                               "--location=" + LOC, "--display-name=KaiOps RCA Governance",
                               "--agent=" + agent,
                               "--natural-language-constraint=" + constraint,
                               "--description=Governs the orchestrator to be RCA-only (read-only), requiring HITL for any mutating action"])
        log(f"policy create rc={rc}\nSTDOUT:{out}\nSTDERR:{err}")
        break
    time.sleep(10)

log("monitor finished")
