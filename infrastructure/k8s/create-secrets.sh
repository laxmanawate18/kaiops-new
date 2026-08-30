#!/bin/bash
# Automated Kubernetes Secrets Creation from .env
# This script reads your .env file and creates Kubernetes secrets
# Usage: ./create-secrets.sh

set -e

echo "========================================================================"
echo "Creating Kubernetes Secrets for KaiOPS Deployment"
echo "========================================================================"

# Check if .env exists
if [ ! -f "../sre-agent-backend/.env" ]; then
    echo "❌ Error: .env file not found at ../sre-agent-backend/.env"
    exit 1
fi

# Load environment variables from .env (filter out comments and empty lines)
set -a
source <(grep -v '^#' ../sre-agent-backend/.env | grep -v '^$' | sed 's/#.*$//' | sed 's/[[:space:]]*$//')
set +a

# Check if kubectl is configured
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Error: kubectl is not configured or cluster is not accessible"
    exit 1
fi

# Create namespace if it doesn't exist
echo ""
echo "📦 Creating namespace..."
kubectl create namespace kaiops --dry-run=client -o yaml | kubectl apply -f -

# Create main secrets
echo ""
echo "🔐 Creating kaiops-secrets..."

# Check required variables
if [ -z "${JWT_SECRET_KEY}" ]; then
    echo "⚠️  Warning: JWT_SECRET_KEY not found in .env"
fi

# JWT signing key: use JWT_SECRET_KEY from .env if set, otherwise generate one.
# This key is exposed to the backend as SECRET_KEY (see kaiops-deployment.yaml).
JWT_SECRET_KEY="${JWT_SECRET_KEY:-}"
if [ -z "$JWT_SECRET_KEY" ]; then
    echo "⚠️  JWT_SECRET_KEY not set; generating a new random one (all existing tokens will be invalidated)"
    JWT_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || openssl rand -base64 32)
fi

kubectl create secret generic kaiops-secrets -n kaiops \
  --from-literal=GITHUB_TOKEN="${GITHUB_TOKEN:-}" \
  --from-literal=GRAFANA_SERVICE_ACCOUNT_TOKEN="${GRAFANA_SERVICE_ACCOUNT_TOKEN:-}" \
  --from-literal=ARGOCD_AUTH_TOKEN="${ARGOCD_AUTH_TOKEN:-}" \
  --from-literal=AZURE_CLIENT_SECRET="${AZURE_CLIENT_SECRET:-}" \
  --from-literal=AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}" \
  --from-literal=GOOGLE_API_KEY="${GOOGLE_API_KEY:-}" \
  --from-literal=AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}" \
  --from-literal=AZURE_CLIENT_ID="${AZURE_CLIENT_ID:-}" \
  --from-literal=AZURE_TENANT_ID="${AZURE_TENANT_ID:-}" \
  --from-literal=AZURE_SUBSCRIPTION_ID="${AZURE_SUBSCRIPTION_ID:-}" \
  --from-literal=JWT_SECRET_KEY="${JWT_SECRET_KEY}" \
  --from-literal=jwt-secret-key="${JWT_SECRET_KEY}" \
  --from-literal=JWT_ALGORITHM="${JWT_ALGORITHM:-HS256}" \
  --from-literal=ACCESS_TOKEN_EXPIRE_MINUTES="${ACCESS_TOKEN_EXPIRE_MINUTES:-30}" \
  --from-literal=REDIS_HOST="${REDIS_HOST:-kaiops-redis}" \
  --from-literal=REDIS_PORT="${REDIS_PORT:-6379}" \
  --from-literal=CACHE_TTL="${CACHE_TTL:-3600}" \
  --dry-run=client -o yaml | kubectl apply -f -

# Create GCP credentials secret
echo ""
echo "🔐 Creating gcp-credentials..."
if [ -f "../sre-agent-backend/carbon-relic-479214-c1-4484b149786b.json" ]; then
    kubectl create secret generic gcp-credentials -n kaiops \
      --from-file=key.json=../sre-agent-backend/carbon-relic-479214-c1-4484b149786b.json \
      --dry-run=client -o yaml | kubectl apply -f -
    echo "   ✅ GCP credentials secret created"
else
    echo "   ⚠️  Warning: GCP credentials file not found, skipping..."
fi

# Verify secrets
echo ""
echo "========================================================================"
echo "✅ Secrets created successfully!"
echo "========================================================================"
echo ""
echo "📋 Verifying secrets in kaiops namespace:"
kubectl get secrets -n kaiops

echo ""
echo "========================================================================"
echo "⚠️  SECURITY REMINDER"
echo "========================================================================"
echo "1. Never commit .env file to git"
echo "2. Add .env to .gitignore if not already present"
echo "3. Rotate exposed credentials immediately after deployment"
echo "4. Review and remove secrets from your terminal history"
echo ""
echo "Run this to clean bash history:"
echo "  history -c && history -w"
echo "========================================================================"
