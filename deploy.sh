#!/usr/bin/env bash
# =============================================================================
# SDOC: Automated Shipping Document Verification
# One-Command Production Cloud Run Deploy Script (Bash/Linux/Mac/Cloud Shell)
# =============================================================================
# Usage:
#   export PROJECT_ID="your-gcp-project-id"
#   export GEMINI_API_KEY="AIzaSy..."   # optional — prompted if not set
#   export REGION="asia-southeast1"     # optional — defaults to asia-southeast1
#   bash deploy.sh
# =============================================================================
set -euo pipefail

echo "======================================================================"
echo "  SDOC ONE-COMMAND DEPLOYMENT TO GOOGLE CLOUD RUN"
echo "======================================================================"

# 1. Check prerequisites
if ! command -v gcloud &>/dev/null; then
    echo "[-] Error: Google Cloud SDK (gcloud) is not installed or not in PATH."
    echo "    Install: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# 2. Configure Project & Region
PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
if [ -z "${PROJECT_ID}" ] || [ "${PROJECT_ID}" = "(unset)" ]; then
    echo "[-] Error: PROJECT_ID is not set and no active gcloud project is configured."
    echo "    Usage: export PROJECT_ID=\"your-gcp-project-id\" && bash deploy.sh"
    exit 1
fi

REGION="${REGION:-asia-southeast1}"
SERVICE_NAME="sdoc-service"
REPO_NAME="sdoc-repo"
IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/sdoc-app:latest"

echo "[+] Target Project : ${PROJECT_ID}"
echo "[+] Target Region  : ${REGION}"
echo "[+] Service Name   : ${SERVICE_NAME}"
echo "[+] Container Tag  : ${IMAGE_TAG}"
echo "----------------------------------------------------------------------"

# 3. Enable Required GCP APIs (idempotent)
echo "[*] Enabling required GCP APIs..."
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    cloudbuild.googleapis.com \
    storage.googleapis.com \
    --project="${PROJECT_ID}"

PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
echo "[+] Compute SA: ${COMPUTE_SA}"

# 4. Configure Secret Manager for GEMINI_API_KEY
echo "[*] Checking Secret Manager for 'gemini-api-key'..."
if ! gcloud secrets describe gemini-api-key --project="${PROJECT_ID}" &>/dev/null; then
    echo "[*] Secret 'gemini-api-key' does not exist. Creating..."
    gcloud secrets create gemini-api-key \
        --replication-policy="automatic" \
        --project="${PROJECT_ID}"

    if [ -n "${GEMINI_API_KEY:-}" ]; then
        printf '%s' "${GEMINI_API_KEY}" | gcloud secrets versions add gemini-api-key \
            --data-file=- --project="${PROJECT_ID}"
        echo "[+] GEMINI_API_KEY stored in Secret Manager."
    else
        echo "[!] WARNING: GEMINI_API_KEY is not set in local environment."
        echo "    Add a secret version manually:"
        echo "      printf '%s' 'AIzaSy...' | gcloud secrets versions add gemini-api-key --data-file=-"
    fi
else
    echo "[+] Secret 'gemini-api-key' already exists in Secret Manager."
    if [ -n "${GEMINI_API_KEY:-}" ]; then
        echo "[*] Updating secret with new key value from environment..."
        printf '%s' "${GEMINI_API_KEY}" | gcloud secrets versions add gemini-api-key \
            --data-file=- --project="${PROJECT_ID}"
        echo "[+] Secret version updated."
    fi
fi

# Grant Cloud Run compute SA read access to the secret
echo "[*] Binding IAM: ${COMPUTE_SA} -> secretmanager.secretAccessor"
gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:${COMPUTE_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="${PROJECT_ID}" >/dev/null

# 5. Create Artifact Registry repository if missing
if ! gcloud artifacts repositories describe "${REPO_NAME}" \
        --location="${REGION}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "[*] Creating Artifact Registry repository '${REPO_NAME}'..."
    gcloud artifacts repositories create "${REPO_NAME}" \
        --repository-format=docker \
        --location="${REGION}" \
        --description="SDOC Shipping Document Verification Containers" \
        --project="${PROJECT_ID}"
fi
echo "[+] Artifact Registry: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"

# 6. Build & Push Container Image via Cloud Build
echo "[*] Submitting build to Cloud Build..."
gcloud builds submit \
    --tag="${IMAGE_TAG}" \
    --project="${PROJECT_ID}" .

echo "[+] Image pushed: ${IMAGE_TAG}"

# 7. Deploy to Google Cloud Run
# Resource limits (demo-optimised):
#   - min-instances=0  -> scale to zero when idle (no cost when unused)
#   - max-instances=3  -> hard cap prevents runaway billing
#   - memory=2Gi       -> covers PyMuPDF + Gemini vision calls
#   - cpu=2            -> smooth first render, fast startup
#   - timeout=300      -> ample for Gemini API calls on slow networks
#   - concurrency=10   -> Streamlit is single-threaded; 10 sessions/instance
#   - GEMINI_API_KEY   -> injected from Secret Manager (never plain env-var)
echo "[*] Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
    --image="${IMAGE_TAG}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --platform=managed \
    --allow-unauthenticated \
    --port=8080 \
    --memory=2Gi \
    --cpu=2 \
    --timeout=300 \
    --min-instances=0 \
    --max-instances=3 \
    --concurrency=10 \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
    --set-env-vars="STORAGE_BACKEND=local,GCP_PROJECT_ID=${PROJECT_ID}"

# 8. Retrieve Public Service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --platform=managed \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --format="value(status.url)")

echo ""
echo "======================================================================"
echo "[+] SUCCESS: SDOC Deployed to Google Cloud Run!"
echo "[+] Public URL : ${SERVICE_URL}"
echo "[+] Healthz    : ${SERVICE_URL}/healthz"
echo "======================================================================"

# 9. Quick smoke test
echo "[*] Running HTTP health check..."
HTTP_CODE=$(curl -o /dev/null -s -w "%{http_code}" "${SERVICE_URL}/healthz" || echo "000")
if [ "${HTTP_CODE}" = "200" ]; then
    echo "[+] Health check passed: HTTP ${HTTP_CODE}"
else
    echo "[!] Health check returned HTTP ${HTTP_CODE} — check Cloud Run logs:"
    echo "    gcloud run services logs read ${SERVICE_NAME} --region=${REGION}"
fi

echo ""
echo "[*] TIP: First visitor after idle may see a ~10s cold start (min-instances=0)."
echo "    Set --min-instances=1 during active judging to keep instance warm:"
echo "    gcloud run services update ${SERVICE_NAME} --region=${REGION} --min-instances=1"
