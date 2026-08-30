$ErrorActionPreference = 'Stop'

Write-Host "Fetching current GCP project..."
$ProjectId = gcloud config get-value project
if (-not $ProjectId) {
    Write-Error "Could not determine GCP project. Run 'gcloud config set project YOUR_PROJECT_ID'."
    exit 1
}

$McpDirs = @("argocd-server", "aws-server", "azure-server", "gcp-server", "github-server", "grafana-server")

# Service account used by the KaiOps backend on Cloud Run. It is granted
# roles/run.invoker on each MCP service so it can obtain ID tokens with that
# service as the audience (see apps/api/agents/mcp_client.py).
# Resolved dynamically from the deployed backend service so the binding always
# matches the real caller. Override with the BackendSA environment variable.
$BackendSA = $env:BackendSA
if (-not $BackendSA) {
    $BackendSA = gcloud run services describe sre-agent-backend --region "us-central1" --format="value(spec.template.spec.serviceAccountName)" 2>$null
}
if (-not $BackendSA) {
    $BackendSA = "275388304596-compute@developer.gserviceaccount.com"
}
Write-Host "Backend service account: $BackendSA"

# Per-service configuration: module file (MCP_SCRIPT) and the env vars each
# server needs. Secrets are pulled from Secret Manager via --set-secrets so
# no credential is ever stored in plaintext env vars.
#   dir            | module file        | secret env -> secret name
#   ---------------+--------------------+--------------------------------------
#   argocd-server  | argocd_mcp_server  | ARGOCD_AUTH_TOKEN -> kaiops-argocd-token
#   aws-server     | aws_mcp_server     | AWS_ACCESS_KEY_ID -> kaiops-aws-access-key-id
#                                         AWS_SECRET_ACCESS_KEY -> kaiops-aws-secret-access-key
#   azure-server   | aks_mcp_server     | (uses Azure CLI / kubectl; no secret)
#   gcp-server     | gcp_mcp_server     | (uses ADC; no secret)
#   github-server  | github_mcp_server  | GITHUB_TOKEN -> kaiops-github-token
#   grafana-server | grafana_mcp_server | GRAFANA_API_KEY -> kaiops-grafana-token
$McpConfig = @{
    "argocd-server"  = @{ Module = "argocd_mcp_server";  Secrets = "ARGOCD_AUTH_TOKEN=kaiops-argocd-token:latest" }
    "aws-server"     = @{ Module = "aws_mcp_server";     Secrets = "AWS_ACCESS_KEY_ID=kaiops-aws-access-key-id:latest,AWS_SECRET_ACCESS_KEY=kaiops-aws-secret-access-key:latest" }
    "azure-server"   = @{ Module = "aks_mcp_server";     Secrets = "" }
    "gcp-server"     = @{ Module = "gcp_mcp_server";     Secrets = "" }
    "github-server"  = @{ Module = "github_mcp_server";  Secrets = "GITHUB_TOKEN=kaiops-github-token:latest" }
    "grafana-server" = @{ Module = "grafana_mcp_server"; Secrets = "GRAFANA_API_KEY=kaiops-grafana-token:latest" }
}

foreach ($Dir in $McpDirs) {
    # Generate the service name (e.g. azure-mcp-server) to maintain backward compatibility with Cloud Run names
    $ServiceName = $Dir.Replace("-server", "-mcp-server")
    $ImageUrl = "us-central1-docker.pkg.dev/${ProjectId}/mcp-servers/${ServiceName}:latest"
    $Module = $McpConfig[$Dir].Module
    $Secrets = $McpConfig[$Dir].Secrets
    $McpScriptPath = "${Dir}.${Module}"

    Write-Host "Building Docker image for $ServiceName..."
    Copy-Item -Path "infrastructure/docker/Dockerfile.mcp" -Destination "Dockerfile"
    gcloud builds submit --tag $ImageUrl .
    if ($LASTEXITCODE -ne 0) { Write-Error "Build failed for $ServiceName"; exit 1 }
    Remove-Item "Dockerfile"

    Write-Host "Deploying $ServiceName to Cloud Run with MCP_SCRIPT=$McpScriptPath ..."
    # NOTE: --set-env-vars replaces ALL env vars on the service, so every
    # non-secret env var each server needs must be listed here. Secrets are
    # injected via --set-secrets (never plaintext).
    $EnvVars = "MCP_SCRIPT=${McpScriptPath}"
    switch ($Dir) {
        "argocd-server"  { $EnvVars = "${EnvVars},ARGOCD_URL=https://34.61.13.1" }
        "aws-server"     { $EnvVars = "${EnvVars},AWS_REGION=ap-southeast-2,AWS_MOCK_MODE=false,AWS_CLOUDWATCH_LOG_GROUP=/aws/containerinsights/kaiops-demo-cluster/application,AWS_CLUSTER_NAME=kaiops-demo-cluster" }
        "grafana-server" { $EnvVars = "${EnvVars},GRAFANA_URL=http://34.9.192.101" }
        default          { }
    }
    $DeployArgs = @(
        "run", "deploy", $ServiceName,
        "--image", $ImageUrl,
        "--region", "us-central1",
        "--platform", "managed",
        "--no-allow-unauthenticated",
        "--port", "8080",
        "--set-env-vars", $EnvVars
    )
    if ($Secrets) {
        $DeployArgs += @("--set-secrets", $Secrets)
    }
    gcloud @DeployArgs
    if ($LASTEXITCODE -ne 0) { Write-Error "Deployment failed for $ServiceName"; exit 1 }

    # Allow only the backend service account to invoke this MCP service.
    Write-Host "Granting roles/run.invoker on $ServiceName to $BackendSA ..."
    gcloud run services add-iam-policy-binding $ServiceName `
        --region "us-central1" `
        --member "serviceAccount:${BackendSA}" `
        --role "roles/run.invoker" `
        --quiet
    if ($LASTEXITCODE -ne 0) { Write-Error "IAM binding failed for $ServiceName"; exit 1 }

    Write-Host "Deployed $ServiceName!"
}

Write-Host "All MCP servers successfully deployed to Cloud Run!"
