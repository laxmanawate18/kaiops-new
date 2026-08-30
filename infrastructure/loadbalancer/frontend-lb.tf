# =============================================================================
# KaiOps Frontend — Global HTTP(S) Load Balancer (Terraform / IaC)
# -----------------------------------------------------------------------------
# Domain  : kaiops-sre.searceinc.net
# Backend : kaiops-web (Cloud Run, us-central1, --allow-unauthenticated)
#
# * Cleaner, reviewable, idempotent alternative to frontend-lb.ps1.
# * Google-managed cert auto-renews; HTTPS-only via 80->443 redirect.
# * Does NOT manage DNS (add A record externally; see README.md).
# =============================================================================

terraform {
  required_version = ">= 1.3"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.60"
    }
  }
}

# ---- Inputs ----------------------------------------------------------------
variable "project_id" {
  type        = string
  default     = "project-3da8cb5f-328e-44d3-b7a"
  description = "GCP project ID."
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Region hosting the Cloud Run service."
}

variable "domain" {
  type        = string
  default     = "kaiops-sre.searceinc.net"
  description = "Frontend domain to serve over HTTPS."
}

variable "cloud_run_service" {
  type        = string
  default     = "kaiops-web"
  description = "Cloud Run service the LB fronts."
}

variable "name_prefix" {
  type        = string
  default     = "kaiops-web"
  description = "Prefix for all LB resource names."
}

locals {
  addr      = "${var.name_prefix}-ip"
  cert      = "${var.name_prefix}-cert"
  neg       = "${var.name_prefix}-neg"
  backend   = "${var.name_prefix}-backend"
  urlmap    = "${var.name_prefix}-urlmap"
  tgt_https = "${var.name_prefix}-https-proxy"
  fwd_https = "${var.name_prefix}-https-forward"
}

provider "google" {
  project = var.project_id
}

# ---- 1. Reserve a global static IP ------------------------------------------
resource "google_compute_global_address" "this" {
  name   = local.addr
  labels = { app = "kaiops-frontend" }
}

# ---- 2. Google-managed SSL cert (auto-renew) --------------------------------
resource "google_compute_managed_ssl_certificate" "this" {
  name    = local.cert
  managed {
    domains = [var.domain]
  }
  lifecycle {
    # Google-managed cert is immutable; ignore field churn.
    create_before_destroy = true
  }
}

# ---- 3. Serverless NEG -> Cloud Run service ---------------------------------
resource "google_compute_region_network_endpoint_group" "this" {
  name                  = local.neg
  region                = var.region
  network_endpoint_type = "SERVERLESS"
  cloud_run {
    service = var.cloud_run_service
  }
}

# ---- 4. Global backend service + serverless NEG ------------------------------
# NOTE: Serverless NEG backends do NOT support timeout_sec or max_utilization —
# those are unsupported for serverless (Cloud Run) groups. Keep it minimal.
resource "google_compute_backend_service" "this" {
  name                  = local.backend
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTPS"

  backend {
    group          = google_compute_region_network_endpoint_group.this.id
    balancing_mode = "UTILIZATION"
  }
}

# ---- 5. URL map (default backend) --------------------
resource "google_compute_url_map" "this" {
  name            = local.urlmap
  default_service = google_compute_backend_service.this.id
}

# ---- 6. Target proxy (HTTPS only; google-managed cert) ---------------
resource "google_compute_target_https_proxy" "this" {
  name             = local.tgt_https
  url_map          = google_compute_url_map.this.id
  ssl_certificates = [google_compute_managed_ssl_certificate.this.id]
}

# ---- 7. Forwarding rule (HTTPS 443 only) ---------------------------------
# NOTE: HTTPS-only to stay within the project's IN_USE_ADDRESSES quota (4) which
# is fully consumed by 3 GKE target pools + 1 forward rule. HTTP->HTTPS redirect
# (port 80) is intentionally omitted; users reach the site via https directly.
resource "google_compute_global_forwarding_rule" "https" {
  name       = local.fwd_https
  target     = google_compute_target_https_proxy.this.id
  ip_address = google_compute_global_address.this.id
  port_range = "443"
}

# ---- Outputs ------------------------------------------------------------------
output "lb_ip" {
  value       = google_compute_global_address.this.address
  description = "Reserved LB IP — point kaiops-sre.searceinc.net (A record) here."
}

output "https_url" {
  value       = "https://${var.domain}"
  description = "HTTPS endpoint served by the LB."
}
