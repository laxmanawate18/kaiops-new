#!/bin/bash
# Script to deploy the KaiOps React frontend to Google Cloud Run

set -e

# Point gcloud to Python 3.10 to fix compatibility issues
export CLOUDSDK_PYTHON="/mnt/c/Users/laxma/AppData/Local/Programs/Python/Python310/python.exe"

# Configuration
REGION="us-central1"
SERVICE_NAME="kaiops-ui"
# Accept backend URL as first argument, or default to a placeholder
BACKEND_URL="${1:-https://backend-agent-placeholder/api/v1}"

echo "Fetching current GCP project..."
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: Could not determine GCP project. Run 'gcloud config set project YOUR_PROJECT_ID'."
    exit 1
fi

IMAGE_URL="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

echo "🔨 Building the frontend Docker image using Cloud Build..."
# Build from project root but specify the kubernetes Dockerfile
gcloud builds submit --tag "${IMAGE_URL}" -f kubernetes/Dockerfile.frontend .

echo "🚀 Deploying ${SERVICE_NAME} to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image "${IMAGE_URL}" \
    --region "${REGION}" \
    --platform managed \
    --allow-unauthenticated \
    --port 80 \
    --set-env-vars="VITE_API_URL=${BACKEND_URL}"

echo "✅ Frontend deployment to Cloud Run complete!"
echo "You can check the Cloud Run console for the public URL."
