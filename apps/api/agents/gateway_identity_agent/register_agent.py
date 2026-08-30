"""
KaiOps isolated Agent Registry registration for the gateway+identity agent.

Per the Agent Gateway runtime deploy doc, the registry entry must be created
in the SAME project and region as the Agent Gateway (us-central1), and the
interface URL should use the mTLS endpoint.

Usage:
    python register_agent.py --engine-id <RESOURCE_ID>
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error

PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-3da8cb5f-328e-44d3-b7a")
PROJECT_NUMBER = os.environ.get("GOOGLE_CLOUD_PROJECT_NUMBER", "275388304596")
LOCATION = "us-central1"
SERVICE_NAME = "kaiops-gateway-identity-agent"


def access_token() -> str:
    r = subprocess.run(
        "gcloud auth application-default print-access-token",
        capture_output=True, text=True, shell=True, encoding="utf-8", errors="replace",
    )
    return r.stdout.strip().splitlines()[-1].strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-id", required=True, help="Reasoning engine resource ID")
    args = parser.parse_args()

    token = access_token()
    # mTLS endpoint URL for the reasoning engine
    interface_url = (
        f"https://{LOCATION}-aiplatform.mtls.googleapis.com/v1/projects/"
        f"{PROJECT_NUMBER}/locations/{LOCATION}/reasoningEngines/{args.engine_id}"
    )

    body = {
        "displayName": SERVICE_NAME,
        "description": "KaiOps isolated gateway+identity agent (identity_type=AGENT_IDENTITY, egress gateway bound)",
        "interfaces": [{"url": interface_url, "protocolBinding": "HTTP_JSON"}],
        "agentSpec": {"type": "NO_SPEC"},
    }

    url = f"https://agentregistry.googleapis.com/v1/projects/{PROJECT}/locations/{LOCATION}/services?serviceId={SERVICE_NAME}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, method="POST")
    print(f"[register] {SERVICE_NAME} in {LOCATION} ...")
    print(f"[register] interface_url={interface_url}")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode())
        print("[register] SUCCESS:")
        print(json.dumps(d, indent=2)[:800])
    except urllib.error.HTTPError as e:
        print("[register] HTTP", e.code)
        print(e.read().decode()[:800])


if __name__ == "__main__":
    main()
