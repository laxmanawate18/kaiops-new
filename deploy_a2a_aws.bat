@echo off
set CLOUDSDK_PYTHON=C:\Users\laxma\AppData\Local\Programs\Python\Python310\python.EXE
cd /d f:\Personal\AI-Project\kaiops_latest
echo AWS A2A deploy start at %date% %time% > deploy_aws_a2a.log
"C:\Users\laxma\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd" run deploy kaiops-aws-a2a --image us-central1-docker.pkg.dev/project-3da8cb5f-328e-44d3-b7a/cloud-run-source-deploy/kaiops-aws-a2a:latest --region us-central1 --project project-3da8cb5f-328e-44d3-b7a --allow-unauthenticated --memory 1Gi --cpu 1 --set-env-vars GEMINI_MODEL=gemini-3.6-flash,GOOGLE_GENAI_USE_VERTEXAI=1,GOOGLE_CLOUD_PROJECT=project-3da8cb5f-328e-44d3-b7a,GOOGLE_CLOUD_LOCATION=us-central1,AZURE_MCP_ENABLED=false,A2A_SHARED_TOKEN=localtok123,APP_URL=PLACEHOLDER >> deploy_aws_a2a.log 2>&1
echo AWS A2A deploy end at %date% %time% >> deploy_aws_a2a.log
