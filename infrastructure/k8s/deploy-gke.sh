#!/bin/bash

# Complete deployment script for KaiOPS on GKE

set -e

PROJECT_ID="${GCP_PROJECT_ID}"
CLUSTER_NAME="kaiops-gke"
REGION="us-central1"
DOCKER_REGISTRY="gcr.io/$PROJECT_ID"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║         KaiOPS Complete Deployment to GKE                 ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"

# Function to print section headers
print_section() {
    echo ""
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}$1${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Function to check command success
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ $1${NC}"
    else
        echo -e "${RED}❌ $1 failed${NC}"
        exit 1
    fi
}

# ============================================================================
# STEP 1: Docker Image Building
# ============================================================================

print_section "STEP 1: Building Docker Images"

echo -e "${YELLOW}Building backend image...${NC}"
cd sre-agent-backend
docker build -f ../kubernetes/Dockerfile.backend -t $DOCKER_REGISTRY/kaiops-backend:latest .
docker push $DOCKER_REGISTRY/kaiops-backend:latest
check_status "Backend image built and pushed"
cd ..

echo -e "${YELLOW}Building frontend image...${NC}"
cd kaiops-ui
docker build -f ../kubernetes/Dockerfile.frontend -t $DOCKER_REGISTRY/kaiops-frontend:latest .
docker push $DOCKER_REGISTRY/kaiops-frontend:latest
check_status "Frontend image built and pushed"
cd ..

# ============================================================================
# STEP 2: GKE Cluster Setup
# ============================================================================

print_section "STEP 2: Verifying GKE Cluster"

echo -e "${YELLOW}Getting cluster credentials...${NC}"
gcloud container clusters get-credentials $CLUSTER_NAME --region $REGION
check_status "Cluster credentials configured"

# ============================================================================
# STEP 3: Deploy Redis
# ============================================================================

print_section "STEP 3: Deploying Redis Cache"

echo -e "${YELLOW}Deploying Redis...${NC}"
kubectl apply -f kubernetes/redis-statefulset.yaml
check_status "Redis deployment"

echo -e "${YELLOW}Waiting for Redis to be ready...${NC}"
kubectl wait --for=condition=ready pod -l app=redis -n redis --timeout=300s
check_status "Redis ready"

# ============================================================================
# STEP 4: Create Secrets
# ============================================================================

print_section "STEP 4: Creating Kubernetes Secrets"

echo -e "${YELLOW}Creating secret for sensitive data...${NC}"
# Reuse an existing JWT signing key so tokens survive redeploys; generate one only
# if no kaiops-secrets secret exists yet. Never hardcode the key in this script.
EXISTING_SECRET_KEY=$(kubectl get secret kaiops-secrets -n kaiops -o jsonpath='{.data.jwt-secret-key}' 2>/dev/null | base64 -d 2>/dev/null || true)
if [ -z "$EXISTING_SECRET_KEY" ]; then
    EXISTING_SECRET_KEY=$(openssl rand -base64 32)
    echo -e "${YELLOW}No existing jwt-secret-key found; generated a new random key (existing tokens will be invalidated)${NC}"
else
    echo -e "${GREEN}Reusing existing jwt-secret-key from kaiops-secrets${NC}"
fi
kubectl create secret generic kaiops-secrets -n kaiops \
  --from-literal=jwt-secret-key="$EXISTING_SECRET_KEY" \
  --from-literal=SECRET_KEY="$EXISTING_SECRET_KEY" \
  --from-literal=ALGORITHM="HS256" \
  --from-literal=ACCESS_TOKEN_EXPIRE_MINUTES="30" \
  --from-literal=GOOGLE_PROJECT_ID="$GCP_PROJECT_ID" \
  --from-literal=GOOGLE_CREDENTIALS_PATH="/var/secrets/gcp/key.json" \
  --dry-run=client -o yaml | kubectl apply -f -
check_status "Secrets created"

# If GCP service account key exists, create the secret
if [ -f "$GOOGLE_CREDENTIALS_PATH" ]; then
    echo -e "${YELLOW}Creating GCP credentials secret...${NC}"
    kubectl create secret generic gcp-credentials -n kaiops \
      --from-file=key.json=$GOOGLE_CREDENTIALS_PATH \
      --dry-run=client -o yaml | kubectl apply -f -
    check_status "GCP credentials secret"
fi

# ============================================================================
# STEP 5: Update Kubernetes Manifests
# ============================================================================

print_section "STEP 5: Updating Kubernetes Manifests"

echo -e "${YELLOW}Updating Docker image references...${NC}"
sed -i "s|gcr.io/YOUR_PROJECT_ID|$DOCKER_REGISTRY|g" kubernetes/kaiops-deployment.yaml
check_status "Manifest updated"

# ============================================================================
# STEP 6: Deploy KaiOPS Application
# ============================================================================

print_section "STEP 6: Deploying KaiOPS Application"

echo -e "${YELLOW}Applying Kubernetes manifests...${NC}"
kubectl apply -f kubernetes/kaiops-deployment.yaml
check_status "KaiOPS deployed"

echo -e "${YELLOW}Waiting for deployments to be ready...${NC}"
kubectl rollout status deployment/kaiops-backend -n kaiops --timeout=300s
check_status "Backend deployment ready"

kubectl rollout status deployment/kaiops-frontend -n kaiops --timeout=300s
check_status "Frontend deployment ready"

# ============================================================================
# STEP 7: Verify Deployment
# ============================================================================

print_section "STEP 7: Verifying Deployment"

echo -e "${YELLOW}Checking pod status...${NC}"
kubectl get pods -n kaiops -o wide
echo ""
kubectl get pods -n redis -o wide

echo -e "${YELLOW}Checking services...${NC}"
kubectl get svc -n kaiops
echo ""
kubectl get svc -n redis

echo -e "${YELLOW}Checking ingress...${NC}"
kubectl get ingress -n kaiops

# ============================================================================
# STEP 8: Display Access Information
# ============================================================================

print_section "STEP 8: Access Information"

FRONTEND_IP=$(kubectl get service kaiops-frontend -n kaiops -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")
BACKEND_IP=$(kubectl get service kaiops-backend -n kaiops -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")

echo -e "${GREEN}✅ Deployment Complete!${NC}"
echo ""
echo "Frontend Service IP: $FRONTEND_IP"
echo "Backend Service IP: $BACKEND_IP"
echo ""
echo -e "${YELLOW}Useful Commands:${NC}"
echo "  Monitor backend logs:  kubectl logs -f deployment/kaiops-backend -n kaiops"
echo "  Monitor frontend logs: kubectl logs -f deployment/kaiops-frontend -n kaiops"
echo "  Port forward backend:  kubectl port-forward -n kaiops svc/kaiops-backend 8000:8000"
echo "  Port forward frontend: kubectl port-forward -n kaiops svc/kaiops-frontend 3000:80"
echo "  Port forward redis:    kubectl port-forward -n redis svc/redis 6379:6379"
echo "  Scale backend:         kubectl scale deployment kaiops-backend -n kaiops --replicas=3"
echo "  Delete deployment:     kubectl delete namespace kaiops redis"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "1. Configure DNS for your domain (e.g., kaiops.example.com)"
echo "2. Set up SSL/TLS certificates with cert-manager"
echo "3. Configure monitoring and logging"
echo "4. Run integration tests"
echo ""
