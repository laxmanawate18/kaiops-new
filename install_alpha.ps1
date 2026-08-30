$ErrorActionPreference = 'Stop'

Write-Host "Copying bundled python..."
$cmdOutput = & "C:\Users\laxma\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd" components copy-bundled-python
Write-Host "Copied python to: $cmdOutput"

$env:CLOUDSDK_PYTHON = $cmdOutput

Write-Host "Installing alpha component..."
gcloud components install alpha --quiet
Write-Host "Done installing alpha."
