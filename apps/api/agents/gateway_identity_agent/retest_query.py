"""Poll the isolated gateway+identity agent's :query until IAP policies propagate.

Writes status to retest_status.log. Run detached.
"""
import subprocess, json, urllib.request, urllib.error, time, os, sys

LOG = r"f:\Personal\AI-Project\kaiops_latest\retest_status.log"

def log(m):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(m + "\n")
    print(m, flush=True)

def token():
    r = subprocess.run("gcloud auth application-default print-access-token", capture_output=True, text=True, shell=True, encoding="utf-8", errors="replace")
    return r.stdout.strip().splitlines()[-1].strip()

PROJ=os.environ.get("GOOGLE_CLOUD_PROJECT", "project-3da8cb5f-328e-44d3-b7a"); LOC="us-central1"; ENGINE="4552195292539125760"

def main():
    open(LOG, "w", encoding="utf-8").close()
    for attempt in range(40):
        t = token()
        url = f"https://{LOC}-aiplatform.googleapis.com/v1/projects/{PROJ}/locations/{LOC}/reasoningEngines/{ENGINE}:query"
        payload = {"class_method": "async_create_session", "input": {"user_id": f"u_prop{attempt}"}}
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Authorization": f"Bearer {t}", "Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.loads(r.read().decode())
            log(f"attempt {attempt}: SUCCESS: " + json.dumps(d)[:600])
            return
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            if "sessions" not in body and "Failed to send" not in body:
                log(f"attempt {attempt}: DIFFERENT error {e.code}: {body[:400]}")
            else:
                log(f"attempt {attempt}: still gateway-blocked ({e.code})")
        time.sleep(12)
    log("NO SUCCESS after 40 attempts (8 min).")

if __name__ == "__main__":
    main()
