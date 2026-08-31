"""Wait for a new gcp governed engine (with mTLS vars) to appear & serve, then test :query.
Writes to monitor_mtls_test.log. Run detached.
"""
import subprocess, json, urllib.request, urllib.error, time, os

LOG = r"f:\Personal\AI-Project\kaiops_latest\monitor_mtls_test.log"
PROJ="project-3da8cb5f-328e-44d3-b7a"; LOC="us-central1"

def log(m):
    with open(LOG,"a",encoding="utf-8") as f: f.write(m+"\n")
    print(m, flush=True)

def token():
    r = subprocess.run("gcloud auth application-default print-access-token", capture_output=True, text=True, shell=True, encoding="utf-8", errors="replace")
    return r.stdout.strip().splitlines()[-1].strip()

def main():
    open(LOG,"w",encoding="utf-8").close()
    # Snapshot current engine count to find the NEW one
    tk = token()
    url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJ}/locations/{LOC}/reasoningEngines"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tk}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode())
    names = set(e.get("name") for e in d.get("reasoningEngines",[]))
    log(f"baseline engines: {len(names)}")

    for i in range(40):
        time.sleep(15)
        try:
            tk = token()
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tk}"})
            with urllib.request.urlopen(req, timeout=30) as r:
                dd = json.loads(r.read().decode())
            engs = dd.get("reasoningEngines",[])
            new = [e for e in engs if e.get("name") not in names]
            if new:
                e = new[-1]
                eid = e.get("name","").split("/")[-1]
                spec = e.get("spec",{})
                cm = len(spec.get("classMethods",[]) or [])
                log(f"[{i}] NEW engine {eid} ident={spec.get('identityType')} gw={'agentGatewayConfig' in str(spec.get('deploymentSpec',{}))} cm={cm}")
                if cm >= 13:
                    # query it
                    qurl = f"https://{LOC}-aiplatform.googleapis.com/v1/projects/{PROJ}/locations/{LOC}/reasoningEngines/{eid}:query"
                    payload = {"class_method":"async_create_session","input":{"user_id":"u_mtls_test"}}
                    qreq = urllib.request.Request(qurl, data=json.dumps(payload).encode(), headers={"Authorization": f"Bearer {tk}", "Content-Type":"application/json"}, method="POST")
                    try:
                        with urllib.request.urlopen(qreq, timeout=45) as qr:
                            qd = json.loads(qr.read().decode())
                        log(f"[{i}] QUERY SUCCESS: {json.dumps(qd.get('output',{}))}")
                        return
                    except urllib.error.HTTPError as e:
                        log(f"[{i}] QUERY HTTP {e.code}: {e.read().decode()[:250]}")
                        return
            else:
                log(f"[{i}] no new engine yet")
        except Exception as ex:
            log(f"[{i}] poll err: {type(ex).__name__}")
    log("TIME OUT")

if __name__ == "__main__":
    main()
