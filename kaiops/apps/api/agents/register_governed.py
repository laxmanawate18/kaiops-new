"""
Register each governed engine in Agent Registry (us-central1) and grant the
agent identity the roles/iap.egressor on the agent + essential endpoints.

Run AFTER the governed engines are deployed. Needs each engine's resource ID.

Usage:
    python register_governed.py <engine_id:display_name> [<engine_id2:name2> ...]
    or pass --all to auto-discover the *-gov engines.
"""

import sys
import subprocess
import json
import os
import urllib.request
import urllib.error

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-3da8cb5f-328e-44d3-b7a")
PROJECT_NUMBER = os.environ.get("GOOGLE_CLOUD_PROJECT_NUMBER", "275388304596")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
PY = r"f:\Personal\AI-Project\kaiops_latest\.venv\Scripts\python.exe"
GCLOUD_BIN = r"C:\Users\laxma\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
GCLOUD_PY = r"C:\Users\laxma\AppData\Local\Programs\Python\Python310\python.EXE"

# Essential endpoints already registered + bound (reuse): map display -> endpoint resId
# These were created earlier for the isolated agent; reuse the SAME endpoint resources.
ENDPOINTS = {
    "kaiops-endpoint-aiplatform-mtls": "agentregistry-00000000-0000-0000-223e-b016f34083e5",
    "kaiops-endpoint-agentregistry": "agentregistry-00000000-0000-0000-3e0b-fc474ff1fdcb",
    "kaiops-endpoint-aiplatform": "agentregistry-00000000-0000-0000-d6d4-ebc599df3744",
    "kaiops-endpoint-aiplatform-rep": "agentregistry-00000000-0000-0000-7752-f9b0eec15817",
}

# display_name -> registry service name (must match deploy display names)
SERVICE_NAMES = {
    "kaiops-orchestrator-gov": "kaiops-orchestrator-gov",
    "gcp-rca-specialist-gov": "gcp-rca-specialist-gov",
    "aws-rca-specialist-gov": "aws-rca-specialist-gov",
    "azure-rca-specialist-gov": "azure-rca-specialist-gov",
}


def token():
    r = subprocess.run("gcloud auth application-default print-access-token", capture_output=True, text=True, shell=True, encoding="utf-8", errors="replace", env=os.environ.copy())
    return r.stdout.strip().splitlines()[-1].strip()


def cli(args, timeout=90):
    env = os.environ.copy()
    env["CLOUDSDK_PYTHON"] = GCLOUD_PY
    r = subprocess.run(
        [GCLOUD_BIN] + args,
        capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace", env=env,
    )
    return r.returncode, r.stdout, r.stderr


def register_agent(display, engine_id):
    tk = token()
    svc = SERVICE_NAMES.get(display, display)
    url = f"https://agentregistry.googleapis.com/v1/projects/{PROJECT}/locations/{LOCATION}/services?serviceId={svc}"
    interface_url = f"https://{LOCATION}-aiplatform.mtls.googleapis.com/v1/projects/{PROJECT_NUMBER}/locations/{LOCATION}/reasoningEngines/{engine_id}"
    body = {
        "displayName": svc,
        "description": f"governed engine {display} (identity+gateway)",
        "interfaces": [{"url": interface_url, "protocolBinding": "HTTP_JSON"}],
        "agentSpec": {"type": "NO_SPEC"},
    }
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Authorization": f"Bearer {tk}", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode())
        reg = d.get("response", d)
        print(f"[{display}] registered service={svc}")
        # get registryResource from the service
        res = describe_service(svc)
        return res
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        if e.code == 409 or "ALREADY_EXISTS" in body:
            print(f"[{display}] already registered (409); fetching resource")
            return describe_service(svc)
        print(f"[{display}] register HTTP {e.code}: {body[:300]}")
        return None


def describe_service(svc):
    tk = token()
    url = f"https://agentregistry.googleapis.com/v1/projects/{PROJECT}/locations/{LOCATION}/services/{svc}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tk}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode())
        rr = d.get("registryResource", "")
        eid = rr.split("/agents/")[-1] if "/agents/" in rr else None
        print(f"  service={svc} registryResource={rr}")
        return eid
    except urllib.error.HTTPError as e:
        print(f"  describe {svc} HTTP {e.code}: {e.read().decode()[:200]}")
        return None


def grant_egressor(member, resource_kind, resource_id):
    # resource_kind in {agent, endpoint}
    flag = "--agent" if resource_kind == "agent" else "--endpoint"
    rc, out, err = cli([
        "iap", "web", "add-iam-policy-binding",
        "--resource-type=agent-registry", f"{flag}={resource_id}",
        f"--region={LOCATION}", f"--project={PROJECT}",
        f"--member={member}", "--role=roles/iap.egressor",
    ])
    ok = rc == 0 and "Updated" in out + err
    print(f"  grant {resource_kind}={resource_id} egressor: {'OK' if ok else 'FAIL'} {out.strip()[:60]}{err.strip()[:60]}")
    return ok


def process(display, engine_id):
    member = (f"principal://agents.global.org-820797041517.system.id.goog/resources/"
              f"aiplatform/projects/{PROJECT_NUMBER}/locations/{LOCATION}/reasoningEngines/{engine_id}")
    print(f"\n=== {display} (engine {engine_id}) ===")
    # 1. register agent
    agent_res_id = register_agent(display, engine_id)
    if agent_res_id:
        # 2. grant egressor on the agent resource
        grant_egressor(member, "agent", agent_res_id)
    # 3. grant egressor on each essential endpoint (reused)
    for name, eid in ENDPOINTS.items():
        grant_egressor(member, "endpoint", eid)


def main():
    args = sys.argv[1:]
    if args and args[0] == "--all":
        # auto-discover gov engines by listing reasoning engines
        tk = token()
        url = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT}/locations/{LOCATION}/reasoningEngines"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {tk}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read().decode())
        for e in d.get("reasoningEngines", []):
            disp = e.get("displayName", "")
            if disp.endswith("-gov"):
                eid = e.get("name", "").split("/")[-1]
                process(disp, eid)
        return
    for spec in args:
        if ":" in spec:
            eid, disp = spec.split(":", 1)
        else:
            disp = spec
            eid = spec
        process(disp, eid)


if __name__ == "__main__":
    main()
