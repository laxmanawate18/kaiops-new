"""Cloud-aware remediation executor for KaiOps.

Turns the agent from an "advisor" into an "operator" by dispatching destructive
or mutating actions (restart / rollback) to the right cloud's Kubernetes API,
based on the application's ``cloud_provider`` (gcp | aws | azure).

This is the single dispatch point that the HITL-guarded tools
(resync / restart / rollback in ``agents/sre_agent/agent.py``) call after a
human approves via ``require_confirmation=True``. It mirrors the existing
cloud-aware router used by the read tools (``check_application_logs``,
``analyze_pod_logs``) so the branching is consistent.

Design:
    execute(app_name, action, **target)  ->  resolves provider, dispatches.
    Each cloud adapter returns an honest result string (success OR the actual
    error) — never an exception, so the agent can report back truthfully.

Credential model per cloud (all via env, injected by Secret Manager):
    gcp   -> ambient Google SA (GKE_CLUSTER_NAME / GKE_CLUSTER_LOCATION)  [GKE only]
    aws   -> AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY + AWS_REGION + AWS_CLUSTER_NAME
    azure -> AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET + AZURE_SUBSCRIPTION_ID + AZURE_AKS_CLUSTER_NAME
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def get_cloud_provider_from_app(app_name: str) -> str:
    """Determine the application's cloud provider from Firestore metadata."""
    try:
        from app.applications.database_firestore import application_db
        app = application_db.get_application_by_name(app_name)
        if app:
            provider = str(app.get("cloud_provider") or "").lower()
            if provider in ("aws", "gcp", "azure"):
                return provider
            logger.warning(f"[EXEC] cloud_provider '{app.get('cloud_provider')}' not recognized for {app_name}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[EXEC] cloud provider lookup failed for {app_name}: {e}")
    return "gcp"


# --------------------------------------------------------------------------- #
# Cloud adapters
# --------------------------------------------------------------------------- #
def _gcp_execute(action: str, namespace: str, pod_name: str, deployment: str, **_) -> str:
    """GKE adapter: restart a pod (existing restart_pod_real) or roll back a deployment."""
    from agents.k8s_executor import restart_pod_real
    if action == "restart":
        return restart_pod_real(pod_name, namespace)
    if action == "rollback":
        return _gke_rollback(deployment, namespace)
    return f"Unsupported GCP action: {action}"


def _gke_rollback(deployment: str, namespace: str) -> str:
    """Roll back a GKE Deployment to its previous ReplicaSet (kubectl rollout undo)."""
    try:
        from kubernetes import client
        api = client.AppsV1Api()
        # Overwrite the deployment's rollout revision annotation to undo.
        body = {"spec": {"rollbackTo": {"revision": 0}}}
        api.patch_namespaced_deployment(
            name=deployment, namespace=namespace, body={"spec": {"rollbackTo": {"revision": 0}}}
        )
        return (
            f"✅ Deployment `{deployment}` in `{namespace}` rolled back to previous revision. "
            "Verify with `kubectl rollout status deploy/{deployment} -n {ns}`.".format(
                deployment=deployment, ns=namespace
            )
        )
    except Exception as e:  # noqa: BLE001
        return f"❌ Failed to roll back deployment `{deployment}`: {e}"


def _aws_execute(action: str, namespace: str, pod_name: str, deployment: str, **_) -> str:
    """EKS adapter: restart/rollback using the AWS EKS kubeconfig (boto3 + eks token)."""
    try:
        return _eks_execute(action, namespace, pod_name, deployment)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[EXEC] AWS adapter error: {e}")
        return f"❌ AWS (EKS) executor not fully configured: {e}"


def _eks_execute(action: str, namespace: str, pod_name: str, deployment: str) -> str:
    """EKS remediation via a dynamically-minted kubeconfig (boto3 eks)."""
    import os
    import json
    import boto3

    region = os.getenv("AWS_REGION", "ap-southeast-2")
    cluster_name = os.getenv("AWS_CLUSTER_NAME", "kaiops-demo-cluster")

    # Mint a short-lived kubeconfig from the EKS cluster (uses ambient AWS creds).
    eks = boto3.client("eks", region_name=region)
    cluster = eks.describe_cluster(name=cluster_name)["cluster"]
    endpoint = cluster["endpoint"]
    ca_b64 = cluster["certificateAuthority"]["data"]

    # EKS bearer token via boto3 EKS Auth (the SDK-native path — no awscli needed).
    # `aws eks get-token` is the CLI path; the SDK path uses the EKS Auth client
    # (boto3 >= 1.34) or falls back to `aws eks get-token` if the auth client is
    # unavailable.
    token = _eks_token(eks, cluster_name, region)

    import base64, tempfile
    from kubernetes import client, config

    ca_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    ca_file.write(base64.b64decode(ca_b64))
    ca_file.close()

    from kubernetes.client import ApiClient, Configuration
    cfg = Configuration()
    cfg.host = endpoint
    cfg.ssl_ca_cert = ca_file.name
    cfg.api_key = {"authorization": f"Bearer {token}"}
    cfg.verify_ssl = True
    api_client = ApiClient(configuration=cfg)

    if action == "restart":
        core = client.CoreV1Api(api_client)
        core.delete_namespaced_pod(name=pod_name, namespace=namespace)
        return f"✅ EKS pod `{pod_name}` in `{namespace}` deleted (Deployment will recreate it)."
    if action == "rollback":
        apps = client.AppsV1Api(api_client)
        apps.patch_namespaced_deployment(
            name=deployment, namespace=namespace, body={"spec": {"rollbackTo": {"revision": 0}}}
        )
        return f"✅ EKS deployment `{deployment}` in `{namespace}` rolled back."
    return f"Unsupported AWS action: {action}"


def _eks_token(eks_client, cluster_name: str, region: str) -> str:
    """Mint an EKS bearer token (SDK-native, with CLI fallback)."""
    # Preferred: boto3 EKS Auth client (boto3 >= 1.35) — generates a token
    # without needing the awscli installed.
    try:
        auth = boto3.client("eks-auth", region_name=region)
        resp = auth.generate_cluster_access_token(cluster_name=cluster_name)
        token = resp.get("token", "")
        if token:
            return token
    except Exception as e:  # noqa: BLE001
        logger.info(f"[EXEC] eks-auth client unavailable ({e}); trying CLI")

    # Fallback: `aws eks get-token` (requires awscli).
    import subprocess, json
    try:
        out = subprocess.check_output(
            ["aws", "eks", "get-token", "--cluster-name", cluster_name, "--region", region],
            text=True, timeout=30,
        )
        return json.loads(out)["status"]["token"]
    except Exception as e:  # noqa: BLE001
        logger.error(f"[EXEC] Could not mint EKS token: {e}")
        return ""


def _azure_execute(action: str, namespace: str, pod_name: str, deployment: str, **_) -> str:
    """AKS adapter: restart/rollback using the Azure Kubernetes client (default creds)."""
    try:
        return _aks_execute(action, namespace, pod_name, deployment)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[EXEC] Azure adapter error: {e}")
        return f"❌ Azure (AKS) executor not fully configured: {e}"


def _aks_execute(action: str, namespace: str, pod_name: str, deployment: str) -> str:
    """AKS remediation via the Azure SDK k8s client (default creds), with CLI fallback."""
    import os

    subscription = os.getenv("AZURE_SUBSCRIPTION_ID", "")
    resource_group = os.getenv("AZURE_RESOURCE_GROUP", "")
    aks_name = os.getenv("AZURE_AKS_CLUSTER_NAME", "")

    if not (subscription and resource_group and aks_name):
        return "❌ Azure (AKS) executor needs AZURE_SUBSCRIPTION_ID / AZURE_RESOURCE_GROUP / AZURE_AKS_CLUSTER_NAME."

    # Build a kubeconfig for the AKS cluster. Prefer the Azure SDK (azure-identity
    # + azure-mgmt-containerservice) so we don't depend on the azure-cli being
    # installed; fall back to `az aks get-credentials`.
    kubeconfig = _aks_kubeconfig(subscription, resource_group, aks_name)
    if kubeconfig is None:
        # CLI fallback
        import subprocess
        try:
            subprocess.run(
                ["az", "aks", "get-credentials", "--resource-group", resource_group,
                 "--name", aks_name, "--subscription", subscription],
                check=True, capture_output=True, timeout=60,
            )
            from kubernetes import config
            config.load_kube_config()
            return _aks_apply(action, namespace, pod_name, deployment)
        except Exception as e:  # noqa: BLE001
            return f"❌ Could not mint AKS credentials (need `az aks get-credentials`): {e}"

    # SDK path: write kubeconfig to a temp file and load it.
    import tempfile
    from kubernetes import config
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".yaml", mode="w", encoding="utf-8")
    f.write(kubeconfig)
    f.close()
    config.load_kube_config(config_file=f.name)
    return _aks_apply(action, namespace, pod_name, deployment)


def _aks_kubeconfig(subscription: str, resource_group: str, aks_name: str):
    """Fetch an AKS cluster kubeconfig via the Azure SDK, or None on failure."""
    try:
        from azure.identity import DefaultAzureCredential
        from azure.mgmt.containerservice import ContainerServiceClient
        from azure.mgmt.containerservice.models import Credential
        import base64, json

        cred = DefaultAzureCredential()
        client = ContainerServiceClient(credential=cred, subscription_id=subscription)
        creds = client.managed_clusters.list_cluster_admin_credentials(
            resource_group_name=resource_group, resource_name=aks_name
        )
        kubeconfigs = creds.kubeconfigs or []
        if kubeconfigs:
            raw = kubeconfigs[0].value
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            return raw
        return None
    except Exception as e:  # noqa: BLE001
        logger.info(f"[EXEC] Azure SDK kubeconfig unavailable ({e}); trying az CLI")
        return None


def _aks_apply(action: str, namespace: str, pod_name: str, deployment: str) -> str:
    """Apply a restart/rollback using a loaded kubeconfig."""
    from kubernetes import client
    if action == "restart":
        core = client.CoreV1Api()
        core.delete_namespaced_pod(name=pod_name, namespace=namespace)
        return f"✅ AKS pod `{pod_name}` in `{namespace}` deleted (Deployment will recreate it)."
    if action == "rollback":
        apps = client.AppsV1Api()
        apps.patch_namespaced_deployment(
            name=deployment, namespace=namespace, body={"spec": {"rollbackTo": {"revision": 0}}}
        )
        return f"✅ AKS deployment `{deployment}` in `{namespace}` rolled back."
    return f"Unsupported Azure action: {action}"


# --------------------------------------------------------------------------- #
# Public dispatch
# --------------------------------------------------------------------------- #
def execute(
    app_name: str,
    action: str,
    namespace: str = "default",
    pod_name: str = "",
    deployment: str = "",
    **_,
) -> str:
    """Dispatch a remediation action to the app's cloud provider.

    Args:
        app_name: Application name (used to look up cloud_provider).
        action: "restart" | "rollback".
        namespace: Kubernetes namespace (default "default").
        pod_name: Pod name (required for "restart").
        deployment: Deployment name (required for "rollback").

    Returns:
        An honest result string (success OR the actual error/unsupported msg).
    """
    provider = get_cloud_provider_from_app(app_name)
    logger.info(f"[EXEC] Dispatch app={app_name} action={action} -> provider={provider}")
    if action == "restart" and not pod_name:
        return "❌ restart requires pod_name."
    if action == "rollback" and not deployment:
        return "❌ rollback requires deployment."

    if provider == "aws":
        return _aws_execute(action, namespace, pod_name, deployment)
    if provider == "azure":
        return _azure_execute(action, namespace, pod_name, deployment)
    return _gcp_execute(action, namespace, pod_name, deployment)


# Back-compat: existing HITL tools reference restart_pod_real directly; keep that
# available alongside the new dispatcher.
__all__ = ["execute", "get_cloud_provider_from_app"]
