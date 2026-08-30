$ErrorActionPreference = 'Stop'

# Script to deploy the KaiOps React frontend to Google Cloud Run

# Configuration
$Region = "us-central1"
$ServiceName = "kaiops-ui"
$BackendUrl = if ($args.Count -gt 0) { $args[0] } else { "https://backend-agent-placeholder/api/v1" }

Write-Host "Fetching current GCP project..."
$ProjectId = gcloud config get-value project
if (-not $ProjectId) {
    Write-Error "Could not determine GCP project. Run 'gcloud config set project YOUR_PROJECT_ID'."
    exit 1
}

$ImageUrl = "us-central1-docker.pkg.dev/${ProjectId}/mcp-servers/${ServiceName}:latest"

Write-Host "Building the frontend Docker image using Cloud Build..."

Write-Host "Deploying $ServiceName to Cloud Run..."
gcloud run deploy $ServiceName `
    --image $ImageUrl `
    --region $Region `
    --platform managed `
    --allow-unauthenticated `
    --port 80 `
    --set-env-vars="VITE_API_URL=$BackendUrl"

Write-Host "Frontend deployment to Cloud Run complete!"
Write-Host "You can check the Cloud Run console for the public URL."
