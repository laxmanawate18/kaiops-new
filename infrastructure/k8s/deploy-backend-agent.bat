@echo off
setlocal enabledelayedexpansion

echo Fetching current GCP project...
FOR /F "tokens=*" %%i IN ('gcloud config get-value project') DO SET PROJECT_ID=%%i

if "%PROJECT_ID%"=="" (
    echo Error: Could not determine GCP project. Run 'gcloud config set project YOUR_PROJECT_ID'.
    exit /b 1
)

set REGISTRY_DIR=kubernetes\agent-registry
set TMP_DIR=%TEMP%\kaiops-registry
if not exist "%TMP_DIR%" mkdir "%TMP_DIR%"

echo Resolving variables in Agent and MCP Registry configurations...
for %%f in ("%REGISTRY_DIR%\*.yaml") do (
    python -c "import sys; content = open(sys.argv[1]).read().replace('${PROJECT_ID}', sys.argv[2]); open(sys.argv[3], 'w').write(content)" "%%f" "%PROJECT_ID%" "%TMP_DIR%\%%~nxf"
)

echo Deploying MCP Servers...
for %%f in ("%TMP_DIR%\*-mcp.yaml") do (
    echo Deploying %%~nxf...
    REM NOTE: gcloud is gcloud.cmd on Windows; without `call` control never
    REM returns to this script (silent exit). Always `call` external tools.
    call gcloud alpha ai mcp-servers deploy ^
        --region="us-central1" ^
        --project="%PROJECT_ID%" ^
        --config="%%f"
)

echo Deploying SRE Root Agent...
call gcloud alpha ai agents deploy ^
    --region="us-central1" ^
    --project="%PROJECT_ID%" ^
    --config="%TMP_DIR%\sre-agent.yaml"

echo Cleaning up temporary files...
rmdir /s /q "%TMP_DIR%"

echo Backend Agent and MCP deployment complete!
