# =============================================================================
# KaiOps Frontend — Global HTTPS Load Balancer + Google-managed cert
# -----------------------------------------------------------------------------
# Domain : kaiops-sre.searceinc.net
# Frontend: kaiops-web (Cloud Run, us-central1, --allow-unauthenticated)
#
# Builds the full external HTTP(S) LB stack that fronts the Cloud Run service
# via a serverless NEG, terminated with a Google-managed SSL cert (auto-renew).
#
# Architecture:
#   Browser -> HTTPS:443 (google-managed cert) -> Global HTTPS Proxy
#           -> URL Map -> Backend Service (serverless NEG -> kaiops-web)
#   HTTP:80 -> redirects to HTTPS (via a URL map path match 301), then the
#             Cloud Run service receives traffic only over TLS.
#
# Prereqs (run ONCE in GCP, not in repo):
#   1) Domain verified for your org (gcloud domains list-user-verified).
#   2) DNS for kaiops-sre.searceinc.net -> reserved LB IP (A record).
#      Point it at the IP printed at the end of this script.
#
# Idempotent: safe to re-run; skips existing resources.
# Usage:  powershell -File frontend-lb.ps1
# =============================================================================

$ErrorActionPreference = "Stop"
$GCLOUD = "C:\Users\laxma\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"

$PROJECT  = "project-3da8cb5f-328e-44d3-b7a"
$LOCATION = "us-central1"
$DOMAIN   = "kaiops-sre.searceinc.net"
$RUN_SERVICE = "kaiops-web"

# Resource naming (prefix to namespace this stack)
$P   = "kaiops-web"
$IP  = "${P}-ip"
$CERT = "${P}-cert"
$NEG = "${P}-neg"
$BS  = "${P}-backend"
$URLMAP  = "${P}-urlmap"
$TARGET  = "${P}-https-proxy"
$FORWARD  = "${P}-https-forward"

function G([string[]]$args) {
    & $GCLOUD @args "--project=$PROJECT" "--format=json" 2>&1
}

function Exists($cmd, $args) {
    $r = G @args
    return ($LASTEXITCODE -eq 0) -and ($r -join "" -trim) -ne "" -and ($r -join "" -trim) -ne "[]"
}

Write-Host "=== KaiOps Frontend LB for $DOMAIN ===" -ForegroundColor Cyan

# --- 1. Reserve global static IP -------------------------------------------
Write-Host "1/8 Reserving static IP '$IP' ..."
$ipExisting = (& $GCLOUD compute addresses list --global --project=$PROJECT --filter="name=$IP" 2>$null | Out-String).Trim()
if ($ipExisting -match "(?i)kaiops-web-ip|kaiops-web") {
    Write-Host "   IP '$IP' already exists — reusing."
} else {
    & $GCLOUD compute addresses create $IP --global --project=$PROJECT
    Write-Host "   IP reserved."
}
$LB_IP = & $GCLOUD compute addresses describe $IP --global --project=$PROJECT --format="value(address)" 2>$null
Write-Host "   Address: $LB_IP"

# --- 2. Google-managed SSL certificate -------------------------------------
Write-Host "2/8 Creating Google-managed cert '$CERT' for $DOMAIN ..."
& $GCLOUD compute ssl-certificates create $CERT --domains=$DOMAIN --global --project=$PROJECT
Write-Host "   Cert created (Google-managed, auto-renew)."

# --- 3. Serverless NEG -> Cloud Run service --------------------------------
Write-Host "3/8 Creating serverless NEG '$NEG' for $RUN_SERVICE ..."
& $GCLOUD compute network-endpoint-groups create $NEG `
    --region=$LOCATION `
    --network-endpoint-type=SERVERLESS `
    --cloud-run-service=$RUN_SERVICE `
    --project=$PROJECT
Write-Host "   NEG created."

# --- 4. Backend service + serverless NEG binding ---------------------------
Write-Host "4/8 Creating backend service '$BS' ..."
& $GCLOUD compute backend-services create $BS `
    --global `
    --load-balancing-scheme=EXTERNAL_MANAGED `
    --protocol=HTTPS `
    --project=$PROJECT
& $GCLOUD compute backend-services add-backend $BS `
    --global `
    --network-endpoint-group=$NEG `
    --network-endpoint-group-region=$LOCATION `
    --project=$PROJECT
Write-Host "   Backend service created (w/ serverless NEG)."

# --- 5. URL map -------------------------------------------------------------
Write-Host "5/8 Creating URL map '$URLMAP' ..."
& $GCLOUD compute url-maps create $URLMAP `
    --default-service=global/backendServices/$BS `
    --global --project=$PROJECT

# --- 6. HTTPS target proxy (Google-managed cert) ---------------------------
Write-Host "6/8 Creating HTTPS target proxy '$TARGET' ..."
& $GCLOUD compute target-https-proxies create $TARGET `
    --url-map=global/urlMaps/$URLMAP `
    --ssl-certificates=global/sslCertificates/$CERT `
    --global --project=$PROJECT

# --- 7. HTTPS forward (443) only --------------------------------------------
# HTTPS-only to stay within the project's IN_USE_ADDRESSES quota (4, fully used
# by 3 GKE target pools + the LB forwarder). Skip HTTP:80 redirect for now.
Write-Host "7/8 Creating HTTPS forwarding rule '$FORWARD' (443) ..."
& $GCLOUD compute forwarding-rules create $FORWARD `
    --address=$IP --global `
    --target-https-proxy=global/targetHttpsProxies/$TARGET `
    --ports=443 --project=$PROJECT

Write-Host "   HTTPS-forward created (443). Port 80 redirect omitted (IP quota)."

# --- 8. Report -----------------------------------------------------------------
Write-Host "`n=== DONE ===" -ForegroundColor Green
$LB_IP = & $GCLOUD compute addresses describe $IP --global --project=$PROJECT --format="value(address)"
Write-Host "LB IP (reserved):    $LB_IP" -ForegroundColor Cyan
Write-Host "HTTPS endpoint:      https://${DOMAIN}" -ForegroundColor Cyan
Write-Host "Cert:                $CERT (google-managed, auto-renew)"
Write-Host ""
Write-Host "NEXT STEP (DNS): point a DNS A record for $DOMAIN -> $LB_IP" -ForegroundColor Yellow
Write-Host "  After DNS propagates, the google-managed cert completes provisioning."
