@echo off
setlocal enabledelayedexpansion

echo Fetching current GCP project...
FOR /F "tokens=*" %%i IN ('gcloud config get-value project') DO SET PROJECT_ID=%%i

if "%PROJECT_ID%"=="" (
    echo [ERROR] Could not determine GCP project. Run 'gcloud config set project YOUR_PROJECT_ID'.
    exit /b 1
)

set SERVICE_NAME=sre-agent-backend
set IMAGE_URL=us-central1-docker.pkg.dev/%PROJECT_ID%/mcp-servers/%SERVICE_NAME%:latest

echo Building the backend Docker image using Cloud Build...
copy infrastructure\docker\Dockerfile.backend Dockerfile
call gcloud builds submit --tag %IMAGE_URL% .
if %errorlevel% neq 0 (
    echo [ERROR] Build failed!
    del Dockerfile
    exit /b %errorlevel%
)
del Dockerfile

echo Fetching MCP URLs...
FOR /F "tokens=*" %%i IN ('gcloud run services describe argocd-mcp-server --region us-central1 --format="value(status.url)"') DO SET MCP_URL_ARGOCD=%%i
FOR /F "tokens=*" %%i IN ('gcloud run services describe azure-mcp-server --region us-central1 --format="value(status.url)"') DO SET MCP_URL_AZURE=%%i
FOR /F "tokens=*" %%i IN ('gcloud run services describe github-mcp-server --region us-central1 --format="value(status.url)"') DO SET MCP_URL_GITHUB=%%i
FOR /F "tokens=*" %%i IN ('gcloud run services describe grafana-mcp-server --region us-central1 --format="value(status.url)"') DO SET MCP_URL_GRAFANA=%%i
FOR /F "tokens=*" %%i IN ('gcloud run services describe aws-mcp-server --region us-central1 --format="value(status.url)"') DO SET MCP_URL_AWS=%%i

echo Ensuring Secret Manager secrets exist (create if missing)...
REM JWT signing key: create with a random value on first run; rotation is
REM handled by infrastructure/k8s/rotate-secrets.sh
REM NOTE: gcloud is gcloud.cmd on Windows. Without `call`, invoking it inside
REM this script TRANSFERS CONTROL to gcloud.cmd and never returns (silent
REM exit=0, deploy step skipped). Always `call` external .cmd/.bat tools.
call gcloud secrets describe kaiops-jwt-secret >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 })) | gcloud secrets create kaiops-jwt-secret --data-file=-"
)

echo Deploying %SERVICE_NAME% to Cloud Run...
REM NOTE: --set-env-vars replaces ALL env vars on the service. The full set
REM of non-secret configuration must be listed here. Provider credentials are
REM injected via --set-secrets (never plaintext).
call gcloud run deploy %SERVICE_NAME% ^
    --image %IMAGE_URL% ^
    --region "us-central1" ^
    --platform managed ^
    --allow-unauthenticated ^
    --port 8000 ^
    --set-secrets="SECRET_KEY=kaiops-jwt-secret:latest,AZURE_CLIENT_SECRET=kaiops-azure-client-secret:latest,AWS_SECRET_ACCESS_KEY=kaiops-aws-secret-access-key:latest,KAIOPS_RUNTIME_TOKEN=kaiops-runtime-token:latest,SLACK_WEBHOOK_URL=kaiops-slack-webhook:latest,ARGOCD_AUTH_TOKEN=kaiops-argocd-token:latest,ARGOCD_PASSWORD=kaiops-argocd-password:latest,GITHUB_TOKEN=kaiops-github-token:latest,GRAFANA_TOKEN=kaiops-grafana-token:latest,GRAFANA_PASSWORD=kaiops-grafana-password:latest,AWS_ACCESS_KEY_ID=kaiops-aws-access-key-id:latest,KAI_OPS_DEPLOY_WEBHOOK_TOKEN=kaiops-deploy-webhook-token:latest,SLACK_BOT_TOKEN=kaiops-slack-bot-token:latest,SLACK_SIGNING_SECRET=kaiops-slack-signing-secret:latest" ^
    --set-env-vars="MCP_URL_ARGOCD=!MCP_URL_ARGOCD!,MCP_URL_AZURE=!MCP_URL_AZURE!,MCP_URL_GITHUB=!MCP_URL_GITHUB!,MCP_URL_GRAFANA=!MCP_URL_GRAFANA!,MCP_URL_AWS=!MCP_URL_AWS!,ENVIRONMENT=production,GOOGLE_GENAI_USE_VERTEXAI=1,GOOGLE_CLOUD_PROJECT=%PROJECT_ID%,GOOGLE_CLOUD_LOCATION=global,GEMINI_MODEL=gemini-3.6-flash,ALLOWED_ORIGINS=*,KAI_OPS_FRONTEND_URL=https://kaiops-sre.searceinc.net,SEED_DEMO_USERS=false,AZURE_MOCK_MODE=false,GKE_CLUSTER_NAME=gcp-demo-cluster,GKE_CLUSTER_LOCATION=us-central1-a,AZURE_SUBSCRIPTION_ID=ed6bdfae-dfcf-442b-9a21-a606e5c653c2,AZURE_TENANT_ID=4d3c899c-ed4a-4e26-9542-0ff4166a3873,AZURE_CLIENT_ID=44828441-b4ed-4632-b84d-5c1a763d4b86,AZURE_RESOURCE_GROUP=dontdelete,AZURE_LOG_ANALYTICS_WORKSPACE_ID=fca5eeb1-1aea-42da-a9b2-7e9b53e5d1cd,AZURE_WORKSPACE_NAME=DefaultWorkspace-ed6bdfae-dfcf-442b-9a21-a606e5c653c2-CUS,AZURE_AKS_CLUSTER_NAME=my-demo-cluster,ARGOCD_URL=https://34.61.13.1,ARGOCD_USERNAME=admin,GRAFANA_URL=http://34.9.192.101,GRAFANA_USERNAME=admin,VERTEX_SEARCH_DATA_STORE_ID=projects/%PROJECT_ID%/locations/us-central1/collections/default_collection/dataStores/sre-runbooks,KUBE_API_URL=https://34.42.202.43,KUBE_API_VERIFY_TLS=true,AWS_REGION=ap-southeast-2,AWS_CLUSTER_NAME=kaiops-demo-cluster,AWS_CLOUDWATCH_LOG_GROUP=/aws/containerinsights/kaiops-demo-cluster/application,AWS_MCP_URL=!MCP_URL_AWS!/mcp!,SLACK_CHANNEL=#incidents"

if %errorlevel% neq 0 (
    echo [ERROR] Deployment failed!
    exit /b %errorlevel%
)

echo.
echo Deployed %SERVICE_NAME% successfully!
