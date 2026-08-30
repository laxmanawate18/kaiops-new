#!/bin/bash
# Complete Cloud Deployment Script for KaiOPS
# This script handles the entire deployment process to GKE
# Usage: ./deploy-cloud.sh

set -e

# Configuration
PROJECT_ID="carbon-relic-479214-c1"
CLUSTER_NAME="kai-ops"
CLUSTER_ZONE="us-central1-a"
NAMESPACE="kaiops"
GCR_REGISTRY="gcr.io/${PROJECT_ID}"

echo "========================================================================"
echo "KaiOPS Cloud Deployment to GKE"
echo "========================================================================"
echo "Project ID: ${PROJECT_ID}"
echo "Cluster: ${CLUSTER_NAME}"
echo "Zone: ${CLUSTER_ZONE}"
echo "Namespace: ${NAMESPACE}"
echo "========================================================================"
echo ""

# Step 1: Verify prerequisites
echo "📋 Step 1/8: Verifying prerequisites..."
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI not installed"
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    echo "❌ Error: kubectl not installed"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "❌ Error: docker not installed"
    exit 1
fi

echo "   ✅ All prerequisites met"

# Step 2: Configure GCP and Docker
echo ""
echo "🔧 Step 2/8: Configuring GCP and Docker..."
gcloud config set project ${PROJECT_ID}
gcloud container clusters get-credentials ${CLUSTER_NAME} --zone ${CLUSTER_ZONE}
gcloud auth configure-docker gcr.io
echo "   ✅ GCP and Docker configured"

# Step 3: Create secrets (if not already created)
echo ""
echo "🔐 Step 3/8: Creating Kubernetes secrets..."
if kubectl get secret kaiops-secrets -n ${NAMESPACE} &> /dev/null; then
    echo "   ℹ️  Secrets already exist, skipping..."
    read -p "   Do you want to recreate secrets? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kubectl delete secret kaiops-secrets -n ${NAMESPACE} || true
        kubectl delete secret gcp-credentials -n ${NAMESPACE} || true
        ./create-secrets.sh
    fi
else
    ./create-secrets.sh
fi

# Step 4: Build backend image
echo ""
echo "🏗️  Step 4/8: Building backend Docker image..."
cd ..
docker build -f kubernetes/Dockerfile.backend \
  -t ${GCR_REGISTRY}/kaiops-backend:latest \
  -t ${GCR_REGISTRY}/kaiops-backend:$(date +%Y%m%d-%H%M%S) \
  .
echo "   ✅ Backend image built"

# Step 5: Push backend image
echo ""
echo "📤 Step 5/8: Pushing backend image to GCR..."
docker push ${GCR_REGISTRY}/kaiops-backend:latest
echo "   ✅ Backend image pushed"

# Step 6: Deploy backend first to get its IP
echo ""
echo "🚀 Step 6/8: Deploying backend and services..."
cd kubernetes
kubectl apply -f redis-statefulset.yaml
kubectl apply -f kaiops-deployment.yaml
echo "   ⏳ Waiting for backend LoadBalancer IP..."

# Wait for backend service to get external IP
BACKEND_IP=""
for i in {1..60}; do
    BACKEND_IP=$(kubectl get svc kaiops-backend-service -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
    if [ -n "$BACKEND_IP" ]; then
        echo "   ✅ Backend IP: ${BACKEND_IP}"
        break
    fi
    echo "   Attempt $i/60... waiting for IP assignment..."
    sleep 5
done

if [ -z "$BACKEND_IP" ]; then
    echo "   ⚠️  Warning: Backend IP not assigned yet. You may need to rebuild frontend later."
    echo "   Get the IP with: kubectl get svc kaiops-backend-service -n ${NAMESPACE}"
    BACKEND_IP="<PENDING>"
else
    BACKEND_URL="http://${BACKEND_IP}:8000/api/v1"
fi

# Step 7: Build and push frontend with backend URL
echo ""
echo "🏗️  Step 7/8: Building frontend Docker image with backend URL..."
cd ..
docker build -f kubernetes/Dockerfile.frontend \
  --build-arg VITE_API_URL="${BACKEND_URL}" \
  -t ${GCR_REGISTRY}/kaiops-frontend:latest \
  -t ${GCR_REGISTRY}/kaiops-frontend:$(date +%Y%m%d-%H%M%S) \
  .
echo "   ✅ Frontend image built with VITE_API_URL=${BACKEND_URL}"

echo ""
echo "📤 Pushing frontend image to GCR..."
docker push ${GCR_REGISTRY}/kaiops-frontend:latest
echo "   ✅ Frontend image pushed"

# Step 8: Restart deployments to use new images
echo ""
echo "🔄 Step 8/8: Rolling out updated deployments..."
kubectl rollout restart deployment kaiops-backend -n ${NAMESPACE}
kubectl rollout restart deployment kaiops-frontend -n ${NAMESPACE}

echo "   ⏳ Waiting for deployments to be ready..."
kubectl rollout status deployment/kaiops-backend -n ${NAMESPACE} --timeout=5m
kubectl rollout status deployment/kaiops-frontend -n ${NAMESPACE} --timeout=5m

# Get service information
echo ""
echo "========================================================================"
echo "📊 Deployment Status"
echo "========================================================================"
kubectl get pods -n ${NAMESPACE}
echo ""
echo "========================================================================"
echo "🌐 Service URLs"
echo "========================================================================"
kubectl get svc -n ${NAMESPACE}

# Get frontend IP
FRONTEND_IP=$(kubectl get svc kaiops-frontend-service -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "Pending")

echo ""
echo "========================================================================"
echo "✅ Deployment Complete!"
echo "========================================================================"
echo ""
echo "🔗 Access URLs:"
echo "   Frontend: http://${FRONTEND_IP}"
echo "   Backend:  http://${BACKEND_IP}:8000"
echo "   API Docs: http://${BACKEND_IP}:8000/docs"
echo "   Health:   http://${BACKEND_IP}:8000/api/v1/health"
echo ""
echo "📋 Next Steps:"
echo "   1. Test the application: curl http://${BACKEND_IP}:8000/api/v1/health"
echo "   2. Configure DNS records (optional):"
echo "      - kaiops-sre.searceinc.net -> ${FRONTEND_IP}"
echo "      - api.kaiops-sre.searceinc.net -> ${BACKEND_IP}"
echo "   3. Set up SSL/TLS with cert-manager (optional)"
echo "   4. Configure monitoring and alerting"
echo ""
echo "⚠️  If backend IP was <PENDING>, run these commands:"
echo "   1. Get IP: kubectl get svc kaiops-backend-service -n ${NAMESPACE}"
echo "   2. Update frontend: export BACKEND_IP=<actual-ip>"
echo "   3. Rebuild frontend: docker build --build-arg VITE_API_URL=http://\${BACKEND_IP}:8000/api/v1 ..."
echo "   4. Push and restart: docker push ... && kubectl rollout restart deployment/kaiops-frontend -n ${NAMESPACE}"
echo ""
echo "========================================================================"
