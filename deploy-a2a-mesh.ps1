# deploy-a2a-mesh.ps1
# Deploys the KaiOps 4-engine A2A mesh to Agent Runtime with Agent Identity.
#
# Engines:
#   - kaiops-orchestrator  (_legacy/kaiops/ -> reasoningEngine, RemoteA2aAgent -> 3 specialists)
#   - kaiops-azure         (specialists/kaiops-azure/ -> azure_rca_specialist)
#   - kaiops-aws           (specialists/kaiops-aws/   -> aws_cloudwatch_rca_specialist)
#   - kaiops-gcp           (specialists/kaiops-gcp/   -> gcp_cloud_logging_rca_specialist)
#
# A2A auth: shared bearer token stored in Secret Manager as `A2A_SHARED_TOKEN`.
# Each engine is deployed with --agent-identity (SPIFFE) for GCP access; the A2A
# token is separate and injected via A2A_SHARED_TOKEN env (secret ref).

[CmdletBinding()]
param(
    [string]$ProjectId = "project-3da8cb5f-328e-44d3-b7a",
    [string]$Region = "us-central1",
    [string]$Root = "f:\Personal\AI-Project\kaiops_latest",
    # If false, instruct agents-cli to deploy the ORCHESTRATOR (kaiops/) too.
    [switch]$SkipOrchestrator,
    # Generate a fresh token (rotate) instead of reusing an existing secret.
    [switch]$RotateToken
)

$ErrorActionPreference = "Stop"
$gcloud = (Get-Command gcloud -ErrorAction SilentlyContinue).Source
if (-not $gcloud) { throw "gcloud CLI not found on PATH." }

function Set-GcloudProject ([string]$proj) {
    & $gcloud config set project $proj | Out-Null
}

function Get-SecretResource ([string]$proj, [string]$name) {
    return "projects/$proj/secrets/$name"
}

function Ensure-A2ASecret ([string]$proj, [switch]$rotate) {
    $name = "A2A_SHARED_TOKEN"
    $exists = & $gcloud secrets describe $name --project=$proj 2>$null
    if (-not $exists -or $rotate) {
        # 48-byte URL-safe token.
        $token = [Convert]::ToBase64String(
            (1..48 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 })
        ) -replace '\+', '-' -replace '/', '_' -replace '=', ''
        if ($exists) { & $gcloud secrets delete $name --project=$proj --quiet | Out-Null }
        & $gcloud secrets create $name --project=$proj --replication-policy=automatic | Out-Null
        & $gcloud secrets versions add $name --data-file=- --project=$proj | Out-Null
        Write-Host "[A2A] Created/rotated secret $name (auto-generated token)" -ForegroundColor Green
    } else {
        Write-Host "[A2A] Secret $name already exists; reusing." -ForegroundColor Yellow
    }
    return Get-SecretResource $proj $name
}

function Update-EnvVars ([string]$dir, [hashtable]$vars) {
    # Deploy with updated env vars. agents-cli accepts --update-env-vars KEY=VAL.
    $pairs = @()
    foreach ($k in $vars.Keys) { $pairs += "$k=$($vars[$k])" }
    if ($pairs.Count -gt 0) {
        & agents-cli deploy --update-env-vars ($pairs -join ",") | Out-Null
    }
}

function Deploy-Engine ([hashtable]$engine) {
    $dir = Join-Path $Root $engine.Folder
    Write-Host "`n=== Deploying $($engine.Name) ($dir) ===" -ForegroundColor Cyan
    Push-Location $dir
    try {
        # 1. Deploy with Agent Identity (SPIFFE).
        $args = @("deploy", "--agent-identity")
        if ($engine.EnvVars) {
            $pairs = @()
            foreach ($k in $engine.EnvVars.Keys) { $pairs += "$k=$($engine.EnvVars[$k])" }
            $args += @("--update-env-vars", ($pairs -join ","))
        }
        & agents-cli @args
        if ($LASTEXITCODE -ne 0) { throw "agents-cli deploy failed for $($engine.Name)" }

        # 2. Capture the reasoningEngine id from deployment_metadata.json.
        $meta = Get-Content (Join-Path $dir "deployment_metadata.json") -Raw | ConvertFrom-Json
        $engine.RuntimeId = $meta.remote_agent_runtime_id -split '/' | Select-Object -Last 1
        Write-Host "   $($engine.Name) reasoningEngine = $($engine.RuntimeId)" -ForegroundColor Green

    } finally {
        Pop-Location
    }
}

Set-GcloudProject $ProjectId
$secretResource = Ensure-A2ASecret $ProjectId -rotate:$RotateToken

# A2A base URL for a specialist engine (exposing side), used by the orchestrator.
function A2A-BaseUrl ([string]$engineId) {
    return "https://$Region-aiplatform.googleapis.com/reasoningEngines/v1/projects/$ProjectId/locations/$Region/reasoningEngines/$engineId/api"
}

# Order matters: deploy specialists FIRST so the orchestrator can resolve their cards.
$specialists = @(
    @{ Name="azure"; Folder="specialists/kaiops-azure"; App="azure_rca_specialist";
       EnvVars=@{ "GOOGLE_CLOUD_LOCATION"=$Region; "A2A_SHARED_TOKEN_SECRET"=$secretResource; "A2A_SHARED_TOKEN"="" } },
    @{ Name="aws";   Folder="specialists/kaiops-aws";   App="aws_cloudwatch_rca_specialist";
       EnvVars=@{ "GOOGLE_CLOUD_LOCATION"=$Region; "A2A_SHARED_TOKEN_SECRET"=$secretResource; "A2A_SHARED_TOKEN"="" } },
    @{ Name="gcp";   Folder="specialists/kaiops-gcp";   App="gcp_cloud_logging_rca_specialist";
       EnvVars=@{ "GOOGLE_CLOUD_LOCATION"=$Region; "A2A_SHARED_TOKEN_SECRET"=$secretResource; "A2A_SHARED_TOKEN"="" } }
)

# Deploy each specialist and record its A2A base URL.
$specUrls = @{}
foreach ($spec in $specialists) {
    Deploy-Engine $spec
    $specUrls[$spec.Name] = A2A-BaseUrl $spec.RuntimeId
}

# Now deploy/update the orchestrator, pointing its RemoteA2aAgents at each specialist.
if (-not $SkipOrchestrator) {
    $orchEnv = @{
        "GOOGLE_CLOUD_LOCATION" = $Region
        "A2A_SHARED_TOKEN_SECRET" = $secretResource
        "A2A_SHARED_TOKEN" = ""
        "AZURE_MCP_ENABLED" = "false"
        "AZURE_A2A_BASE_URL" = $specUrls["azure"]
        "AWS_A2A_BASE_URL"   = $specUrls["aws"]
        "GCP_A2A_BASE_URL"   = $specUrls["gcp"]
    }
    Deploy-Engine @{ Name="orchestrator"; Folder="_legacy/kaiops"; EnvVars=$orchEnv }
}

Write-Host "`n=== A2A Mesh Deployment Complete ===" -ForegroundColor Green
Write-Host "Azure specialist: $($specUrls['azure'])/a2a/azure_rca_specialist"
Write-Host "AWS specialist:   $($specUrls['aws'])/a2a/aws_cloudwatch_rca_specialist"
Write-Host "GCP specialist:   $($specUrls['gcp'])/a2a/gcp_cloud_logging_rca_specialist"
Write-Host "Secret: $secretResource"
