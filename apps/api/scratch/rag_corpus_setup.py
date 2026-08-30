"""Simple RAG corpus setup: wait for the 6 serverless corpora, keep us-east5,
delete the other 5, and rename the kept one to kaiops-knowledge."""
import subprocess, json, urllib.request, urllib.error, os, sys, time, io
sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding="utf-8",errors="replace")
os.environ["CLOUDSDK_PYTHON"] = r"C:\Users\laxma\AppData\Local\Programs\Python\Python310\python.EXE"
gcloud = r"C:\Users\laxma\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
PROJ="project-3da8cb5f-328e-44d3-b7a"; PN="275388304596"

def token():
    r = subprocess.run([gcloud,"auth","application-default","print-access-token"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout.strip().splitlines()[-1].strip()

def req(method,url,body=None,timeout=120):
    try:
        data=json.dumps(body).encode() if body else None
        r=urllib.request.Request(url, data=data, headers={"Authorization":f"Bearer {tk}","Content-Type":"application/json"}, method=method)
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]

tk=token()
ops={
 "us-east5":"projects/275388304596/locations/us-east5/operations/6849936550323552256",
 "europe-west1":"projects/275388304596/locations/europe-west1/operations/3752618410911989760",
 "europe-west4":"projects/275388304596/locations/europe-west4/operations/2814127924561575936",
 "asia-southeast1":"projects/275388304596/locations/asia-southeast1/operations/5632599882125541376",
 "us-south1":"projects/275388304596/locations/us-south1/operations/5867426703638265856",
 "australia-southeast1":"projects/275388304596/locations/australia-southeast1/operations/1336996793526779904",
}
# Wait up to ~5 min for each
corpora={}
for loc,op in ops.items():
    for _ in range(30):
        st,b=req("GET",f"https://{loc}-aiplatform.googleapis.com/v1/{op}")
        if isinstance(b,dict) and b.get("done"):
            resp=b.get("response") or {}
            name=resp.get("name","")
            corpora[loc]=name
            print(f"[{loc}] DONE -> {name}")
            break
        time.sleep(10)
    else:
        print(f"[{loc}] timeout, corpus name unknown")

# Delete the 5 unwanted (keep us-east5)
KEEP="us-east5"
for loc,name in corpora.items():
    if loc==KEEP: continue
    if name:
        st,b=req("DELETE",f"https://{loc}-aiplatform.googleapis.com/v1/{name}")
        print(f"[delete {loc}] {st}")
    else:
        print(f"[delete {loc}] no name, skipping")

# Rename kept corpus to kaiops-knowledge if a name exists
kept=corpora.get(KEEP)
if kept:
    # update display_name via PATCH
    st,b=req("PATCH",f"https://{KEEP}-aiplatform.googleapis.com/v1/{kept}",{"displayName":"kaiops-knowledge","description":"Unified KaiOps knowledge: runbooks, past incidents, approved feedback (serverless)"})
    print(f"[rename {KEEP}] PATCH {st}")
    print("FINAL corpus:", kept)
else:
    print("us-east5 corpus name not resolved yet; will retry later")
