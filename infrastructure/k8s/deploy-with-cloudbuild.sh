#!/bin/bash
# Cloud Build + kubectl Deployment Workflow
# This script automates your existing process of building with Cloud Build and deploying with kubectl

set -e

PROJECT_ID="carbon-relic-479214-c1"
CLUSTER_NAME="kai-ops"
CLUSTER_ZONE="us-central1-a"
NAMESPACE="kaiops"

echo "========================================================================"
echo "KaiOPS Cloud Deployment via Cloud Build + kubectl"
echo "========================================================================"
echo "Project: ${PROJECT_ID}"
echo "Cluster: ${CLUSTER_NAME} (${CLUSTER_ZONE})"
echo "Namespace: ${NAMESPACE}"
echo "========================================================================"
echo ""

# Step 1: Verify prerequisites
echo "📋 Step 1/6: Verifying prerequisites..."
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI not installed"
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    echo "❌ Error: kubectl not installed"
    exit 1
fi

# Check if cloudbuild-simple.yaml exists
if [ ! -f "cloudbuild-simple.yaml" ]; then
    echo "❌ Error: cloudbuild-simple.yaml not found in current directory"
    echo "   Run this script from the kubernetes/ directory"
    exit 1
fi

# Check if kaiops-deployment.yaml exists
if [ ! -f "kaiops-deployment.yaml" ]; then
    echo "❌ Error: kaiops-deployment.yaml not found"
    exit 1
fi

echo "   ✅ All prerequisites met"

# Step 2: Configure GCP
echo ""
echo "🔧 Step 2/6: Configuring GCP..."
gcloud config set project ${PROJECT_ID}
gcloud container clusters get-credentials ${CLUSTER_NAME} --zone ${CLUSTER_ZONE}
echo "   ✅ GCP configured"

# Step 3: Create/verify secrets
echo ""
echo "🔐 Step 3/6: Checking Kubernetes secrets..."
if kubectl get secret kaiops-secrets -n ${NAMESPACE} &> /dev/null; then
    echo "   ✅ Secrets already exist"
else
    echo "   ⚠️  Secrets not found. Creating..."
    if [ -f "create-secrets.sh" ]; then
        ./create-secrets.sh
    else
        echo "   ❌ Error: create-secrets.sh not found"
        echo "   Please create secrets manually or run create-secrets.sh"
        exit 1
    fi
fi

# Step 4: Build images with Cloud Build
echo ""
echo "🏗️  Step 4/6: Building images with Cloud Build..."
echo "   This includes ALL your latest code changes:"
echo "   ✅ Status display fix (frontend)"
echo "   ✅ Enum serialization fix (backend)"
echo "   ✅ Updated API URL configuration"
echo ""

cd ..  # Go to project root for Cloud Build
gcloud builds submit \
  --config=kubernetes/cloudbuild-simple.yaml \
  --timeout=3600s \
  .

if [ $? -eq 0 ]; then
    echo ""
    echo "   ✅ Images built and pushed successfully!"
else
    echo ""
    echo "   ❌ Cloud Build failed. Check logs above."
    exit 1
fi

# Step 5: Deploy to GKE
echo ""
echo "🚀 Step 5/6: Deploying to GKE..."
cd kubernetes

# Deploy Redis first if not exists
if ! kubectl get statefulset redis -n redis &> /dev/null; then
    echo "   📦 Deploying Redis..."
    kubectl apply -f redis-statefulset.yaml
fi

# Apply main deployment
echo "   📦 Applying kaiops-deployment.yaml..."
kubectl apply -f kaiops-deployment.yaml

# Force rollout restart to use new images
echo "   🔄 Rolling out new deployments..."
kubectl rollout restart deployment kaiops-backend -n ${NAMESPACE}
kubectl rollout restart deployment kaiops-frontend -n ${NAMESPACE}

# Wait for rollout
echo "   ⏳ Waiting for rollout to complete..."
kubectl rollout status deployment/kaiops-backend -n ${NAMESPACE} --timeout=5m
kubectl rollout status deployment/kaiops-frontend -n ${NAMESPACE} --timeout=5m

# Step 6: Display results
echo ""
echo "========================================================================"
echo "✅ Deployment Complete!"
echo "========================================================================"
echo ""

# Get pod status
echo "📊 Pod Status:"
kubectl get pods -n ${NAMESPACE}

echo ""
echo "========================================================================"
echo "🌐 Service Information"
echo "========================================================================"
kubectl get svc -n ${NAMESPACE}

# Get IPs
BACKEND_IP=$(kubectl get svc kaiops-backend -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "Pending")
FRONTEND_IP=$(kubectl get svc kaiops-frontend -n ${NAMESPACE} -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "Pending")

echo ""
echo "========================================================================"
echo "🔗 Access URLs"
echo "========================================================================"
echo "Frontend:  http://${FRONTEND_IP}"
echo "Backend:   http://${BACKEND_IP}:8000"
echo "API Docs:  http://${BACKEND_IP}:8000/docs"
echo "Health:    http://${BACKEND_IP}:8000/api/v1/health"
echo ""

if [ "$BACKEND_IP" != "Pending" ]; then
    echo "🧪 Testing backend health..."
    sleep 5  # Wait a bit for pods to be ready
    if curl -s -f "http://${BACKEND_IP}:8000/api/v1/health" > /dev/null 2>&1; then
        echo "   ✅ Backend is healthy!"
    else
        echo "   ⚠️  Backend not responding yet (may still be starting)"
    fi
fi

echo ""
echo "========================================================================"
echo "✅ Deployed Changes"
echo "========================================================================"
echo "✅ Status display fix - Frontend handles enum format"
echo "✅ Status display fix - Backend extracts .value properly"
echo "✅ API URL configured: http://api.kaiops-sre.searceinc.net/api/v1"
echo "✅ All latest code changes from localhost"
echo ""
echo "📋 Next Steps:"
echo "1. Test the application in browser: http://${FRONTEND_IP}"
echo "2. Verify status shows correctly (Active/Inactive, not Unknown)"
echo "3. Check logs if needed:"
echo "   kubectl logs -f deployment/kaiops-backend -n ${NAMESPACE}"
echo "   kubectl logs -f deployment/kaiops-frontend -n ${NAMESPACE}"
echo ""
echo "========================================================================"
