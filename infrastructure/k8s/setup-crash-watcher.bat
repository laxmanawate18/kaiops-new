@echo off
REM ============================================================================
REM Setup the KaiOps K8s crash-event watcher scheduler.
REM
REM Creates a Cloud Scheduler cron job that calls the backend's
REM   POST /api/v1/runtime/webhooks/watch
REM every N minutes so it auto-triggers an autonomous RCA when it sees
REM CrashLoopBackOff / ImagePullBackOff / OOMKilled / FailedScheduling events.
REM
REM Auth: the watcher demands Bearer KAI_OPS_DEPLOY_WEBHOOK_TOKEN (fail-closed).
REM We pull that secret value here and inject it as a header.
REM
REM Prereqs: gcloud authenticated with the project; the backend already deployed
REM with the kaiops-deploy-webhook-token secret (rev 00065+).
REM ============================================================================
setlocal enabledelayedexpansion
set CLOUDSDK_PYTHON=C:\Users\laxma\AppData\Local\Programs\Python\Python310\python.EXE
set PYTHONIOENCODING=utf-8

echo Fetching current GCP project...
FOR /F "tokens=*" %%i IN ('gcloud config get-value project') DO SET PROJECT_ID=%%i
if "%PROJECT_ID%"=="" ( echo [ERROR] no project & exit /b 1 )

echo Fetching backend URL...
FOR /F "tokens=*" %%i IN ('gcloud run services describe sre-agent-backend --region us-central1 --format="value(status.url)"') DO SET BACKEND_URL=%%i
if "%BACKEND_URL%"=="" ( echo [ERROR] could not resolve sre-agent-backend URL & exit /b 1 )
echo   BACKEND_URL=%BACKEND_URL%

echo Fetching deploy webhook token from Secret Manager...
FOR /F "tokens=*" %%i IN ('gcloud secrets versions access latest --secret kaiops-deploy-webhook-token --project %PROJECT_ID%') DO SET DEPLOY_TOKEN=%%i
if "%DEPLOY_TOKEN%"=="" ( echo [ERROR] kaiops-deploy-webhook-token secret missing & exit /b 1 )

set JOB_NAME=kaiops-crash-watcher
set SCHEDULE=*/2 * * * *
set URL=%BACKEND_URL%/api/v1/runtime/webhooks/watch
set OIDC_SA=275388304596-compute@developer.gserviceaccount.com

echo Creating/updating Cloud Scheduler job [%JOB_NAME%] to call %URL% every 2 min...
call gcloud scheduler jobs update http %JOB_NAME% ^
    --project=%PROJECT_ID% ^
    --location=us-central1 ^
    --schedule="%SCHEDULE%" ^
    --uri="%URL%" ^
    --http-method=POST ^
    --headers="Authorization=Bearer %DEPLOY_TOKEN%" ^
    --oidc-service-account-email=%OIDC_SA% ^
    --oidc-token-audience="%URL%" 2>nul
if %errorlevel% neq 0 (
    echo   job did not exist; creating...
    call gcloud scheduler jobs create http %JOB_NAME% ^
        --project=%PROJECT_ID% ^
        --location=us-central1 ^
        --schedule="%SCHEDULE%" ^
        --uri="%URL%" ^
        --http-method=POST ^
        --headers="Authorization=Bearer %DEPLOY_TOKEN%" ^
        --oidc-service-account-email=%OIDC_SA% ^
        --oidc-token-audience="%URL%"
)

echo.
echo Done. Job [%JOB_NAME%] is set to scan cluster crash events every 2 minutes.
echo To verify:  gcloud scheduler jobs describe %JOB_NAME% --location=us-central1 --project=%PROJECT_ID%
