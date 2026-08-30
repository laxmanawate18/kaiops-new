# =============================================================================
# KaiOps Autonomous Loop — GCP Infrastructure Provisioning
# -----------------------------------------------------------------------------
# Creates the trigger + broker + runtime identity needed for Model C
# (The Autonomous Loop):
#   - Secret Manager secret: kaiops-runtime-token (shared-secret auth for ingest)
#   - Pub/Sub topic + subscription: kaiops-events (real event bus)
#   - Cloud Scheduler job: kaiops-health-sweep (cron that autonomously
#     invokes KaiOps to sweep the fleet for issues, no human in the loop)
#   - IAM: grant the Cloud Run backend SA permission to publish (so the agent
#     can emit its own follow-up events) & Pub/Sub push delivery from the SA
#
# Run from repo root OR any dir; requires `gcloud` auth with project access.
# Idempotent — safe to re-run.
# =============================================================================

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-us-central1}"
BACKEND_SERVICE="sre-agent-backend"
BACKEND_SA="${BACKEND_SA:-275388304596-compute@developer.gserviceaccount.com}"
EVENT_TOPIC="kaiops-events"
EVENT_SUB="kaiops-events-sub"
SCHEDULER_JOB="kaiops-health-sweep"
RUNTIME_SECRET="kaiops-runtime-token"

echo "==> Project: ${PROJECT_ID}  Region: ${REGION}"

# --- 1. Runtime token secret (shared-secret for autonomous ingress) ----------
echo "==> Ensuring Secret Manager secret '${RUNTIME_SECRET}' exists..."
if ! gcloud secrets describe "${RUNTIME_SECRET}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  RTOKEN="$(python -c 'import secrets;print(secrets.token_urlsafe(32))')"
  printf '%s' "${RTOKEN}" | gcloud secrets create "${RUNTIME_SECRET}" \
    --project="${PROJECT_ID}" --data-file=-
  echo "    Created '${RUNTIME_SECRET}' with a new random token."
else
  echo "    '${RUNTIME_SECRET}' already exists (skipped)."
fi

# --- 2. Pub/Sub topic + subscription -----------------------------------------
echo "==> Ensuring Pub/Sub topic '${EVENT_TOPIC}' exists..."
if ! gcloud pubsub topics describe "${EVENT_TOPIC}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud pubsub topics create "${EVENT_TOPIC}" --project="${PROJECT_ID}"
else
  echo "    Topic already exists (skipped)."
fi

# Subscription: push to the backend /api/v1/runtime/ingest/pubsub endpoint with
# OIDC auth using the backend SA (zero-trust). We pull instead to keep it simple
# and let the Cloud Run worker/runner claim jobs; but push is fine for demo.
echo "==> Ensuring Pub/Sub subscription '${EVENT_SUB}' exists..."
if ! gcloud pubsub subscriptions describe "${EVENT_SUB}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  BACKEND_URL="$(gcloud run services describe "${BACKEND_SERVICE}" --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)' 2>/dev/null || true)"
  if [[ -n "${BACKEND_URL}" ]]; then
    gcloud pubsub subscriptions create "${EVENT_SUB}" \
      --project="${PROJECT_ID}" \
      --topic="${EVENT_TOPIC}" \
      --push-endpoint="${BACKEND_URL}/api/v1/runtime/ingest/pubsub" \
      --push-auth-service-account="${BACKEND_SA}" \
      --expiration-period="never" \
      --message-retention-duration="7d" \
      --ack-deadline=60
  else
    echo "    WARNING: backend URL not resolved; creating pull subscription only."
    gcloud pubsub subscriptions create "${EVENT_SUB}" \
      --project="${PROJECT_ID}" --topic="${EVENT_TOPIC}" \
      --expiration-period="never"
  fi
else
  echo "    Subscription already exists (skipped)."
fi

# --- 3. Cloud Scheduler cron job (autonomous health sweep) -------------------
echo "==> Ensuring Cloud Scheduler job '${SCHEDULER_JOB}' exists..."
if ! gcloud scheduler jobs describe "${SCHEDULER_JOB}" --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  BACKEND_URL="$(gcloud run services describe "${BACKEND_SERVICE}" --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)' 2>/dev/null || true)"
  if [[ -n "${BACKEND_URL}" ]]; then
    RTOKEN="$(gcloud secrets versions access latest --secret="${RUNTIME_SECRET}" --project="${PROJECT_ID}" 2>/dev/null || echo '')"
    gcloud scheduler jobs create http "${SCHEDULER_JOB}" \
      --location="${REGION}" \
      --project="${PROJECT_ID}" \
      --schedule="*/10 * * * *" \
      --http-method=POST \
      --uri="${BACKEND_URL}/api/v1/runtime/ingest" \
      --headers="Authorization=Bearer ${RTOKEN}" \
      --message-body='{"incident_name":"🚨 Proactive Fleet Sweep","prompt":"Perform an autonomous health sweep of all registered applications. Summarize which services are healthy or degraded.","severity":"P3","source":"cloud_scheduler"}' \
      --content-type=application/json \
      --attempt-deadline=300s \
      --time-zone="Etc/UTC"
  else
    echo "    WARNING: backend URL not resolved; scheduler job not created."
  fi
else
  echo "    Scheduler job already exists (skipped)."
fi

# --- 4. IAM grant: backend SA can publish events (agent emits follow-ups) ----
echo "==> Ensuring backend SA can publish to '${EVENT_TOPIC}'..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${BACKEND_SA}" \
  --role="roles/pubsub.publisher" >/dev/null 2>&1 || true

echo
echo "==> Autonomous Loop infra ready in project '${PROJECT_ID}'"
echo "    Secret:       ${RUNTIME_SECRET}"
echo "    Pub/Sub:      ${EVENT_TOPIC} / ${EVENT_SUB}"
echo "    Scheduler:    ${SCHEDULER_JOB} (every 10 min)"
echo "    Backend SA:   ${BACKEND_SA}"
