"""Wait for the mTLS env update to complete, then test the isolated agent's session query.
Writes to retest_mtls.log. Run detached.
"""
import subprocess, json, urllib.request, urllib.error, time, os

LOG = r"f:\Personal\AI-Project\kaiops_latest\retest_mtls.log"
PROJ="project-3da8cb5f-328e-44d3-b7a"; LOC="us-central1"
ENGINE="4552195292539125760"
OP="projects/"+PROJ+"/locations/"+LOC+"/operations/5770102628746788864"

def log(m):
    with open(LOG,"a",encoding="utf-8") as f: f.write(m+"\n")
    print(m, flush=True)

def token():
    r = subprocess.run("gcloud auth application-default print-access-token", capture_output=True, text=True, shell=True, encoding="utf-8", errors="replace")
    return r.stdout.strip().splitlines()[-1].strip()

def main():
    open(LOG,"w",encoding="utf-8").close()
    for i in range(30):
        tk = token()
        # check op
        try:
            req = urllib.request.Request(f"https://{LOC}-aiplatform.googleapis.com/v1/{OP}", headers={"Authorization": f"Bearer {tk}"})
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.loads(r.read().decode())
            done = d.get("done")
        except Exception as e:
            done = None
        # test query (only after op done)
        if done:
            url = f"https://{LOC}-aiplatform.googleapis.com/v1/projects/{PROJ}/locations/{LOC}/reasoningEngines/{ENGINE}:query"
            payload = {"class_method":"async_create_session","input":{"user_id":"u_mtls2"}}
            req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Authorization": f"Bearer {tk}", "Content-Type":"application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=45) as r:
                    dd = json.loads(r.read().decode())
                log(f"[{i}] op done. QUERY SUCCESS: {json.dumps(dd.get('output',{}))}")
                return
            except urllib.error.HTTPError as e:
                log(f"[{i}] op done. QUERY HTTP {e.code}: {e.read().decode()[:200]}")
                time.sleep(5)
                continue
        else:
            log(f"[{i}] op in-progress, waiting")
        time.sleep(15)
    log("TIME OUT")

if __name__ == "__main__":
    main()
