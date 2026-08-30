@echo off
setlocal enabledelayedexpansion

:: Configuration
set REGION=us-central1
set SERVICE_NAME=kaiops-ui
set BACKEND_URL=%1
if "%BACKEND_URL%"=="" set BACKEND_URL=https://backend-agent-placeholder/api/v1

echo Fetching current GCP project...
FOR /F "tokens=*" %%i IN ('gcloud config get-value project') DO SET PROJECT_ID=%%i

if "%PROJECT_ID%"=="" (
    echo Error: Could not determine GCP project. Run 'gcloud config set project YOUR_PROJECT_ID'.
    exit /b 1
)

set IMAGE_URL=us-central1-docker.pkg.dev/%PROJECT_ID%/mcp-servers/%SERVICE_NAME%:latest

echo Building the frontend Docker image using Cloud Build...
copy kubernetes\Dockerfile.frontend Dockerfile
call gcloud builds submit --tag %IMAGE_URL% .
if %errorlevel% neq 0 (
    echo [ERROR] Build failed!
    del Dockerfile
    exit /b %errorlevel%
)
del Dockerfile

echo Deploying %SERVICE_NAME% to Cloud Run...
call gcloud run deploy %SERVICE_NAME% ^
    --image %IMAGE_URL% ^
    --region %REGION% ^
    --platform managed ^
    --allow-unauthenticated ^
    --port 80 ^
    --set-env-vars="VITE_API_URL=%BACKEND_URL%"

echo Frontend deployment to Cloud Run complete!
echo You can check the Cloud Run console for the public URL.
