"""Real Kubernetes remediation executor.

Credential resolution order for _load_api():
1. Explicit kubeconfig file  (env KUBECONFIG_PATH, optional KUBECONFIG_CONTEXT)
2. In-cluster config         (when the pod itself runs inside Kubernetes)
3. Dynamic GKE config        (env GKE_CLUSTER_NAME / GKE_CLUSTER_LOCATION) —
   fetches endpoint+CA via the Container API and mints a short-lived bearer
   token from the ambient Google credentials (works out-of-the-box when this
   code runs as a Cloud Run service with a GKE-authorized service account).
"""
import base64
import logging
import os
import tempfile

logger = logging.getLogger(__name__)

KUBECONFIG_CONTEXT = os.getenv("KUBECONFIG_CONTEXT", "")  # optional specific context


def _load_api():
    from kubernetes import client, config

    # 1. Explicit kubeconfig
    kubeconfig_path = os.getenv("KUBECONFIG_PATH", "")
    try:
        if kubeconfig_path:
            config.load_kube_config(config_file=kubeconfig_path, context=KUBECONFIG_CONTEXT or None)
        else:
            if KUBECONFIG_CONTEXT:
                config.load_kube_config(context=KUBECONFIG_CONTEXT)
            else:
                config.load_kube_config()
        logger.info("k8s executor: using kubeconfig credentials")
        return client.CoreV1Api()
    except Exception as kube_err:  # noqa: BLE001
        logger.info("k8s executor: kubeconfig unavailable (%s)", kube_err.__class__.__name__)

    # 2. In-cluster
    try:
        config.load_incluster_config()
        logger.info("k8s executor: using in-cluster credentials")
        return client.CoreV1Api()
    except Exception as inc_err:  # noqa: BLE001
        logger.info("k8s executor: not running in a cluster (%s)", inc_err.__class__.__name__)

    # 3. Explicit endpoint + scoped service-account token (Cloud Run friendly;
    #    works regardless of Workload Identity / Google-SA mapping on the cluster)
    api_url = os.getenv("KUBE_API_URL", "")
    api_token = os.getenv("KUBE_API_TOKEN", "")
    if api_url and api_token:
        from kubernetes.client import ApiClient, Configuration
        cfg = Configuration()
        cfg.host = api_url.rstrip("/")
        cfg.api_key = {"authorization": f"Bearer {api_token}"}
        cfg.verify_ssl = os.getenv("KUBE_API_VERIFY_TLS", "true").lower() != "false"
        if not cfg.verify_ssl:
            import urllib3  # noqa: F401
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            cfg.assert_hostname = False
        logger.info("k8s executor: using explicit KUBE_API_URL credentials")
        return client.CoreV1Api(api_client=ApiClient(configuration=cfg))

    # 4. Dynamic GKE (Cloud Run + service account)
    return _load_gke_api(client)


def _load_gke_api(k8s_client_module):
    """Build an API client against GKE using ambient google.auth creds."""
    import google.auth
    from kubernetes.client import ApiClient, Configuration

    project_id = (
        os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GOOGLE_PROJECT_ID")
        or ""
    )
    cluster_name = os.getenv("GKE_CLUSTER_NAME", "")
    location = os.getenv("GKE_CLUSTER_LOCATION", "")

    if not (project_id and cluster_name and location):
        raise RuntimeError(
            "No Kubernetes credentials available. Provide KUBECONFIG_PATH, run "
            "in-cluster, or set GKE_CLUSTER_NAME/GKE_CLUSTER_LOCATION/"
            "GOOGLE_CLOUD_PROJECT so GKE access can be resolved dynamically."
        )

    from google.cloud import container_v1

    cm_client = container_v1.ClusterManagerClient()
    cluster = cm_client.get_cluster(
        name=f"projects/{project_id}/locations/{location}/clusters/{cluster_name}"
    )
    endpoint = f"https://{cluster.endpoint}"
    ca_cert_b64 = cluster.master_auth.cluster_ca_certificate

    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)

    ca_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    ca_file.write(base64.b64decode(ca_cert_b64))
    ca_file.close()

    cfg = Configuration()
    cfg.host = endpoint
    cfg.ssl_ca_cert = ca_file.name
    cfg.api_key = {"authorization": f"Bearer {creds.token}"}
    cfg.verify_ssl = True

    api_client = ApiClient(configuration=cfg)
    logger.info("k8s executor: using dynamic GKE credentials for %s/%s",
                location, cluster_name)
    return k8s_client_module.CoreV1Api(api_client)


def restart_pod_real(pod_name: str, namespace: str = "default") -> str:
    """Delete a pod so its Deployment/StatefulSet recreates it (the standard 'restart').

    Returns an honest result string — success OR the actual error.
    """
    try:
        api = _load_api()
        # Read the pod first: verify it exists and capture its owner kind
        pod = api.read_namespaced_pod(name=pod_name, namespace=namespace)
        owner = None
        for ref in (pod.metadata.owner_references or []):
            owner = ref.kind  # Deployment->ReplicaSet->Pod typically; direct owner is ReplicaSet/StatefulSet/Job
        # Delete the pod
        from kubernetes.client import V1DeleteOptions
        api.delete_namespaced_pod(
            name=pod_name, namespace=namespace, body=V1DeleteOptions(grace_period_seconds=30)
        )
        return (
            f"✅ Pod `{pod_name}` deleted in namespace `{namespace}` "
            f"(owner: {owner or 'unknown'}). Its controller will recreate it. "
            "Verify with `kubectl get pods -n {ns} -w`.".format(ns=namespace)
        )
    except Exception as e:
        # Honest failure with actionable message
        from kubernetes.client.exceptions import ApiException
        if isinstance(e, ApiException):
            if e.status == 404:
                return f"❌ Pod `{pod_name}` not found in namespace `{namespace}`."
            if e.status == 403:
                return f"❌ Forbidden: the current credentials cannot delete pods in `{namespace}` ({e.reason})."
            return f"❌ Kubernetes API error {e.status}: {e.reason}"
        return f"❌ Failed to restart pod: {e}"
