#!/bin/bash

# GCP GKE Cluster Setup Script
# Creates a production-ready GKE cluster for KaiOPS

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-your-project-id}"
CLUSTER_NAME="kaiops-gke"
REGION="us-central1"
ZONE="us-central1-a"
MACHINE_TYPE="n1-standard-2"
NUM_NODES=2
MIN_NODES=1
MAX_NODES=3

echo -e "${YELLOW}🚀 Starting GKE Cluster Setup for KaiOPS${NC}"
echo "Project: $PROJECT_ID"
echo "Cluster: $CLUSTER_NAME"
echo "Region: $REGION"

# Step 1: Set project
echo -e "${YELLOW}[1/8] Setting GCP project${NC}"
gcloud config set project $PROJECT_ID

# Step 2: Enable required APIs
echo -e "${YELLOW}[2/8] Enabling required Google APIs${NC}"
gcloud services enable container.googleapis.com
gcloud services enable compute.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com
gcloud services enable aiplatform.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Step 3: Create GKE cluster with optimized settings
echo -e "${YELLOW}[3/8] Creating GKE cluster${NC}"
gcloud container clusters create $CLUSTER_NAME \
  --region $REGION \
  --machine-type $MACHINE_TYPE \
  --num-nodes $NUM_NODES \
  --min-nodes $MIN_NODES \
  --max-nodes $MAX_NODES \
  --enable-autoscaling \
  --enable-autorepair \
  --enable-autoupgrade \
  --addons HorizontalPodAutoscaling,HttpLoadBalancing \
  --workload-pool=$PROJECT_ID.svc.id.goog \
  --enable-stackdriver-kubernetes \
  --logging=SYSTEM,WORKLOAD \
  --monitoring=SYSTEM,WORKLOAD \
  --network="default" \
  --cluster-secondary-range-name=pods \
  --services-secondary-range-name=services \
  --quiet

# Step 4: Get cluster credentials
echo -e "${YELLOW}[4/8] Configuring kubectl access${NC}"
gcloud container clusters get-credentials $CLUSTER_NAME --region $REGION

# Step 5: Create namespaces
echo -e "${YELLOW}[5/8] Creating Kubernetes namespaces${NC}"
kubectl create namespace kaiops || true
kubectl create namespace redis || true
kubectl label namespace kaiops app=kaiops || true

# Step 6: Create service account for workload identity
echo -e "${YELLOW}[6/8] Setting up Workload Identity${NC}"
gcloud iam service-accounts create kaiops-sa \
  --display-name="KaiOPS Service Account" || true

# Grant necessary roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:kaiops-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:kaiops-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/logging.logWriter"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:kaiops-sa@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/monitoring.metricWriter"

# Bind Kubernetes service account to GCP service account
kubectl annotate serviceaccount kaiops-backend -n kaiops \
  iam.gke.io/gcp-service-account=kaiops-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --overwrite || true

# Step 7: Install Ingress Controller
echo -e "${YELLOW}[7/8] Installing NGINX Ingress Controller${NC}"
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.1/deploy/static/provider/gcp/deploy.yaml

# Step 8: Verify deployment
echo -e "${YELLOW}[8/8] Verifying cluster${NC}"
kubectl cluster-info
echo ""
echo -e "${GREEN}✅ GKE cluster setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Deploy Redis: kubectl apply -f kubernetes/redis-statefulset.yaml"
echo "2. Deploy backend: kubectl apply -f kubernetes/backend-deployment.yaml"
echo "3. Deploy frontend: kubectl apply -f kubernetes/frontend-deployment.yaml"
echo "4. Deploy ingress: kubectl apply -f kubernetes/ingress.yaml"
echo ""
echo "Monitor deployments:"
echo "  kubectl get pods -n kaiops -w"
echo "  kubectl get services -n kaiops"
echo ""
