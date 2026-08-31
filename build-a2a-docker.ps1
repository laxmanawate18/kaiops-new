# Builds the 3 Cloud Run A2A specialist images LOCALLY with Docker (Docker Desktop).
#
# Use this to iterate faster on the FastAPI A2A specialists before a Cloud Build /
# Cloud Run deploy. Each specialist (gcp/aws/azure) has its own directory with a
# Dockerfile (python:3.12-slim + uv, CMD uvicorn app.fast_api_app:app --port 8080).
#
# Usage:
#   .\build-a2a-docker.ps1                 # build all 3
#   .\build-a2a-docker.ps1 gcp             # build just gcp
#   .\build-a2a-docker.ps1 -Run gcp        # build + run gcp locally on :8080
#   .\build-a2a-docker.ps1 -RunAll         # build + run all 3
#
# Before a Cloud Run deploy, the images can be pushed with:
#   docker tag <img> <region>-docker.pkg.dev/<PROJ>/<repo>/<svc>:latest
#   docker push <region>-docker.pkg.dev/<PROJ>/<repo>/<svc>:latest

param(
    [string]$Only,         # optional: 'gcp' | 'aws' | 'azure'
    [switch]$Run,          # run the built image(s) locally on localhost:8080
    [switch]$RunAll        # build + run all
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$PROJ = "project-3da8cb5f-328e-44d3-b7a"
$REPO = "a2a-specialists"
$REGION = "us-central1"
$tag = "${REGION}-docker.pkg.dev/${PROJ}/${REPO}"

$specials = [ordered]@{
    gcp   = @{ dir = "$root\specialists\kaiops-gcp";   app = "gcp_cloud_logging_rca_specialist"; url = "http://localhost:8080" }
    aws   = @{ dir = "$root\specialists\kaiops-aws";   app = "aws_cloudwatch_rca_specialist";    url = "http://localhost:8080" }
    azure = @{ dir = "$root\specialists\kaiops-azure"; app = "azure_rca_specialist";             url = "http://localhost:8080" }
}

function Build-One([string]$name) {
    $s = $specials[$name]
    $img = "${tag}/kaiops-$name-a2a:latest"
    Write-Host "=== Building $name -> $img ===" -ForegroundColor Cyan
    docker build -t $img $s.dir
    if ($LASTEXITCODE -ne 0) { throw "Docker build failed for $name" }
    Write-Host "Built $name OK" -ForegroundColor Green
    # Also tag a plain local name for easy `docker run`
    docker tag $img "kaiops-$name-a2a:local"
    return $img
}

function Run-One([string]$name) {
    $s = $specials[$name]
    Write-Host "=== Running $name on :8080 (APP_URL=$($s.url)) ===" -ForegroundColor Cyan
    docker run --rm -d --name "kaiops-$name-a2a" -p 8080:8080 `
        -e APP_URL="$($s.url)" `
        -e GEMINI_MODEL="gemini-3.6-flash" `
        -e GOOGLE_GENAI_USE_VERTEXAI="1" `
        -e GOOGLE_CLOUD_PROJECT="$PROJ" `
        -e GOOGLE_CLOUD_LOCATION="us-central1" `
        -e AZURE_MCP_ENABLED="false" `
        -e A2A_SHARED_TOKEN="localtok123" `
        "kaiops-$name-a2a:local"
    if ($LASTEXITCODE -ne 0) { throw "docker run failed for $name" }
    Write-Host "Running $name. Card: $($s.url)/a2a/$($s.app)/.well-known/agent-card.json" -ForegroundColor Green
}

$targets = @()
if ($RunAll) { $targets = @("gcp", "aws", "azure"); $Run = $true }
elseif ($Only) { $targets = @($Only) }
else { $targets = @("gcp", "aws", "azure") }

foreach ($t in $targets) {
    Build-One $t
    if ($Run) { Run-One $t }
}

Write-Host "`nDone. Push for Cloud Run when ready:
  docker tag <img> ${tag}/kaiops-<cloud>-a2a:latest
  docker push ${tag}/kaiops-<cloud>-a2a:latest" -ForegroundColor Yellow
