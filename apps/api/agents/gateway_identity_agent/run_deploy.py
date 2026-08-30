"""Self-contained runner that writes deploy status to a log file so it can survive
the snippet executor timeout. Run with: python run_deploy.py
"""
import os, sys, json, io, traceback

LOG = r"f:\Personal\AI-Project\kaiops_latest\identity_gw_deploy_status.log"

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)

def main():
    open(LOG, "w", encoding="utf-8").close()  # reset
    os.environ["GOOGLE_CLOUD_PROJECT"] = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-3da8cb5f-328e-44d3-b7a")
    os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"
    sys.path.insert(0, r"f:\Personal\AI-Project\kaiops_latest\apps\api\agents\gateway_identity_agent")
    try:
        import vertexai
        from vertexai import types
        from vertexai.agent_engines import AdkApp
        from agent import root_agent, MODEL

        PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-3da8cb5f-328e-44d3-b7a")
        LOCATION = "us-central1"
        STAGING_BUCKET = "gs://kaiops-gateway-identity-staging"
        AGENT_GATEWAY = f"projects/{PROJECT}/locations/{LOCATION}/agentGateways/kaiops-egress-gw"

        log(f"model={MODEL} gateway={AGENT_GATEWAY} bucket={STAGING_BUCKET}")
        client = vertexai.Client(project=PROJECT, location=LOCATION, http_options=dict(api_version="v1beta1"))
        app = AdkApp(agent=root_agent)
        config = {
            "display_name": "kaiops-gateway-identity-agent",
            "identity_type": types.IdentityType.AGENT_IDENTITY,
            "agent_gateway_config": {"agent_to_anywhere_config": {"agent_gateway": AGENT_GATEWAY}},
            "requirements": ["google-cloud-aiplatform[adk,agent_engines]"],
            "staging_bucket": STAGING_BUCKET,
        }
        log("creating agent engine (identity+gateway)...")
        remote_app = client.agent_engines.create(agent=app, config=config)
        log("RESOURCE_NAME: " + str(remote_app.resource_name))
        try:
            log("effective_identity: " + str(remote_app.api_resource.spec.effective_identity))
        except Exception as e:
            log(f"effective_identity not yet: {e}")
        log("DONE_OK")
    except Exception:
        log("EXCEPTION:\n" + traceback.format_exc())

if __name__ == "__main__":
    main()
