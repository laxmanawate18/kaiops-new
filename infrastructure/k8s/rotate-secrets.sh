#!/usr/bin/env bash
# =============================================================================
# KaiOps Secret Rotation -> Google Secret Manager
# =============================================================================
# Rotates application secrets by writing new versions to Google Secret Manager
# (never stored in env files or plaintext manifests).
#
# Usage:
#   ./rotate-secrets.sh                  # rotate SECRET_KEY only (auto-generated)
#   GITHUB_TOKEN=ghp_xxx ./rotate-secrets.sh --all
#   ./rotate-secrets.sh --secret GITHUB_TOKEN   # rotate one external secret
#
# External-provider secrets (GitHub, Grafana, ArgoCD, Azure, AWS, Google AI)
# cannot be generated here — first rotate them at the provider, then pass the
# new value via environment variable (see EXTERNAL_SECRETS below).
#
# IMPORTANT:
#   * Rotating SECRET_KEY invalidates ALL existing JWTs (users are logged out).
#   * After rotation, redeploy the backend so it picks up the `latest` version:
#       bash infrastructure/k8s/deploy-backend-cloudrun.sh   (or .bat)
#   * Recommended cadence: SECRET_KEY quarterly, provider tokens per provider
#     policy (GitHub fine-grained PATs: 90 days, etc.)
# =============================================================================
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-us-central1}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "null" ]]; then
    echo "[ERROR] Could not determine GCP project. Run 'gcloud config set project YOUR_PROJECT_ID'." >&2
    exit 1
fi

# --- Secret definitions ------------------------------------------------------
# Auto-generated secrets: name -> generator
AUTO_SECRETS=(
    "kaiops-jwt-secret-key"   # SECRET_KEY (JWT signing)
)

# External secrets: Secret Manager name -> env var holding the new value
declare -A EXTERNAL_SECRETS=(
    ["kaiops-github-token"]="GITHUB_TOKEN"
    ["kaiops-grafana-token"]="GRAFANA_SERVICE_ACCOUNT_TOKEN"
    ["kaiops-argocd-token"]="ARGOCD_AUTH_TOKEN"
    ["kaiops-azure-client-secret"]="AZURE_CLIENT_SECRET"
    ["kaiops-aws-secret-access-key"]="AWS_SECRET_ACCESS_KEY"
    ["kaiops-google-api-key"]="GOOGLE_API_KEY"
)

MODE="${1:---jwt}"
ROTATE_ALL=false
TARGET_SECRET=""

case "${MODE}" in
    --all)    ROTATE_ALL=true ;;
    --secret) TARGET_SECRET="${2:-}"; [[ -z "${TARGET_SECRET}" ]] && { echo "[ERROR] --secret requires a name"; exit 1; } ;;
    --jwt)    ;; # default: SECRET_KEY only
    *) echo "Usage: $0 [--jwt|--all|--secret NAME]"; exit 1 ;;
esac

# --- Helpers -----------------------------------------------------------------
# Upsert: create the secret if missing, otherwise add a new version.
upsert_secret() {
    local name="$1" value="$2"
    if ! gcloud secrets describe "${name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
        echo "  [CREATE] ${name}"
        printf '%s' "${value}" | gcloud secrets create "${name}" \
            --project="${PROJECT_ID}" --data-file=- --replication-policy="automatic" >/dev/null
    else
        echo "  [ADD VERSION] ${name}"
        printf '%s' "${value}" | gcloud secrets versions add "${name}" \
            --project="${PROJECT_ID}" --data-file=- >/dev/null
    fi
}

generate_random() {
    # 48 random bytes, base64-encoded (no newlines) -> strong symmetric key
    openssl rand -base64 48 | tr -d '\n'
}

echo "Rotating secrets in project '${PROJECT_ID}'..."

# --- 1. Auto-generated secrets ------------------------------------------------
if [[ "${ROTATE_ALL}" == true || -z "${TARGET_SECRET}" ]]; then
    for name in "${AUTO_SECRETS[@]}"; do
        echo "[*] Rotating ${name} (auto-generated)..."
        upsert_secret "${name}" "$(generate_random)"
    done
    echo "    NOTE: SECRET_KEY rotation invalidates all existing JWTs (forced logout)."
fi

# --- 2. External-provider secrets ----------------------------------------------
for name in "${!EXTERNAL_SECRETS[@]}"; do
    env_var="${EXTERNAL_SECRETS[$name]}"
    if [[ -n "${TARGET_SECRET}" && "${TARGET_SECRET}" != "${name}" ]]; then
        continue
    fi
    if [[ "${ROTATE_ALL}" != true && -z "${TARGET_SECRET}" ]]; then
        continue  # default mode: JWT only
    fi
    new_value="${!env_var:-}"
    if [[ -z "${new_value}" ]]; then
        echo "[SKIP] ${name}: set \$${env_var} to rotate (rotate at the provider first)."
        continue
    fi
    echo "[*] Rotating ${name} from \$${env_var}..."
    upsert_secret "${name}" "${new_value}"
done

# --- 3. Summary -----------------------------------------------------------------
echo
echo "Done. Next steps:"
echo "  1. Redeploy the backend to pick up 'latest' secret versions:"
echo "       bash infrastructure/k8s/deploy-backend-cloudrun.sh"
echo "  2. For GKE, sync Secret Manager -> k8s Secrets (External Secrets Operator"
echo "     or manual 'gcloud secrets versions access latest' into kubectl create secret)."
echo "  3. Verify old secret versions can be disabled after a soak period:"
echo "       gcloud secrets versions list <NAME> --project=${PROJECT_ID}"
