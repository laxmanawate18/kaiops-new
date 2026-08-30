$ErrorActionPreference = 'Stop'

# Script to deploy the KaiOps Backend and independent MCP Servers

Write-Host "Fetching current GCP project..."
$ProjectId = gcloud config get-value project
if (-not $ProjectId) {
    Write-Error "Could not determine GCP project. Run 'gcloud config set project YOUR_PROJECT_ID'."
    exit 1
}

$RegistryDir = "kubernetes/agent-registry"
$TmpDir = [System.IO.Path]::GetTempPath() + "kaiops-registry"
if (!(Test-Path -Path $TmpDir)) {
    New-Item -ItemType Directory -Force -Path $TmpDir | Out-Null
}

Write-Host "Resolving variables in Agent and MCP Registry configurations..."
$YamlFiles = Get-ChildItem -Path $RegistryDir -Filter "*.yaml"
foreach ($File in $YamlFiles) {
    $Content = Get-Content $File.FullName -Raw
    $Content = $Content -replace '\$\{PROJECT_ID\}', $ProjectId
    $DestPath = Join-Path -Path $TmpDir -ChildPath $File.Name
    [IO.File]::WriteAllText($DestPath, $Content)
}

Write-Host "Deploying MCP Servers..."
$McpFiles = Get-ChildItem -Path $TmpDir -Filter "*-mcp.yaml"
foreach ($McpFile in $McpFiles) {
    Write-Host "Deploying $($McpFile.Name)..."
    gcloud alpha ai mcp-servers deploy `
        --region="us-central1" `
        --project="$ProjectId" `
        --config="$($McpFile.FullName)"
}

Write-Host "Deploying SRE Root Agent..."
$RootAgentFile = Join-Path -Path $TmpDir -ChildPath "sre-agent.yaml"
gcloud alpha ai agents deploy `
    --region="us-central1" `
    --project="$ProjectId" `
    --config="$RootAgentFile"

Write-Host "Cleaning up temporary files..."
Remove-Item -Path $TmpDir -Recurse -Force

Write-Host "Backend Agent and MCP deployment complete!"
