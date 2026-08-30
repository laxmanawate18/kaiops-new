#!/bin/bash
# Script to deploy the KaiOps Backend and independent MCP Servers

set -e

# Point gcloud to Python 3.10 to fix compatibility issues
export CLOUDSDK_PYTHON="/mnt/c/Users/laxma/AppData/Local/Programs/Python/Python310/python.exe"

PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo "Error: Could not determine GCP project. Run 'gcloud config set project YOUR_PROJECT_ID'."
    exit 1
fi

REGISTRY_DIR="kubernetes/agent-registry"
TMP_DIR="/tmp/kaiops-registry"
mkdir -p ${TMP_DIR}

echo "Resolving variables in Agent & MCP Registry configurations..."
for file in ${REGISTRY_DIR}/*.yaml; do
    filename=$(basename "$file")
    sed "s/\${PROJECT_ID}/${PROJECT_ID}/g" "$file" > "${TMP_DIR}/${filename}"
done

echo "Deploying MCP Servers..."
for mcp_file in ${TMP_DIR}/*-mcp.yaml; do
    echo "Deploying $(basename $mcp_file)..."
    gcloud alpha ai mcp-servers deploy \
        --region="us-central1" \
        --project="${PROJECT_ID}" \
        --config="${mcp_file}"
done

echo "Deploying SRE Root Agent..."
gcloud alpha ai agents deploy \
    --region="us-central1" \
    --project="${PROJECT_ID}" \
    --config="${TMP_DIR}/sre-agent.yaml"

echo "Cleaning up temporary files..."
rm -rf "${TMP_DIR}"

echo "Backend Agent & MCP deployment complete!"
