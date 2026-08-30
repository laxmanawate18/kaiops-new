@echo off
set CLOUDSDK_PYTHON=C:\Users\laxma\AppData\Local\Programs\Python\Python310\python.EXE
cd /d "f:\Personal\AI-Project\kaiops_latest"
echo ===== DEPLOY START 22:25:17 ===== > "f:\Personal\AI-Project\kaiops_latest\deploy_backend_run.log"
call "f:\Personal\AI-Project\kaiops_latest\infrastructure\k8s\deploy-backend-cloudrun.bat" >> "f:\Personal\AI-Project\kaiops_latest\deploy_backend_run.log" 2>&1
echo ===== DEPLOY END rc=%ERRORLEVEL% ===== >> "f:\Personal\AI-Project\kaiops_latest\deploy_backend_run.log"
