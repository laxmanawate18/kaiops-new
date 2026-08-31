"""Polls the reasoning engines API for the -gov engines and writes status to a log.
Run detached; check monitor_governed.log periodically.
"""
import subprocess, json, urllib.request, urllib.error, time, os, sys

LOG = r"f:\Personal\AI-Project\kaiops_latest\monitor_governed.log"
PROJ = "project-3da8cb5f-328e-44d3-b7a"
LOC = "us-central1"

def token():
    r = subprocess.run("gcloud auth application-default print-access-token", capture_output=True, text=True, shell=True, encoding="utf-8", errors="replace")
    return r.stdout.strip().splitlines()[-1].strip()

def log(m):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(m + "\n")
    print(m, flush=True)

def main():
    open(LOG, "w", encoding="utf-8").close()
    for attempt in range(40):  # ~40 * 20s = ~13 min
        try:
            tk = token()
            url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJ}/locations/{LOC}/reasoningEngines"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tk}"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode())
            eng = d.get("reasoningEngines", [])
            gov = [e for e in eng if "gov" in e.get("displayName", "")]
            log(f"[{attempt}] total={len(eng)} gov={len(gov)}")
            for e in gov:
                spec = e.get("spec", {})
                log(f"    {e.get('displayName')} id={e.get('name','').split('/')[-1]} ident={spec.get('identityType')} gw={'agentGatewayConfig' in str(spec.get('deploymentSpec',{}))} cm={len(spec.get('classMethods',[]) or [])}")
            if len(gov) >= 4:
                log("ALL 4 GOVERNED ENGINES PRESENT.")
                break
        except Exception as ex:
            log(f"[{attempt}] poll err: {type(ex).__name__}: {ex}")
        time.sleep(20)
    log("MONITOR DONE")

if __name__ == "__main__":
    main()
