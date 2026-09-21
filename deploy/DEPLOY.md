# Deployment Guide: Google Cloud Run (Production)

This guide provides step-by-step, copy-pasteable instructions for deploying the **SDOC Shipping Document Verification System** to **Google Cloud Run** with Google Secret Manager, Cloud Firestore persistence, and reverse-proxy protections.

> **Security reminder**: Never commit `.env`, API keys, or ground-truth files. All secrets travel through Secret Manager or `--set-secrets` only.

---

## 0. Local Docker Build & Run Test

Verify the container builds and runs correctly before pushing to Cloud Run.

```bash
# 1. Build the image locally
docker build -t sdoc-app:local .

# 2. Run it locally — pass your Gemini key through the environment only
#    (never bake it into the image or Dockerfile)
docker run --rm \
    -p 8080:8080 \
    -e GEMINI_API_KEY="${GEMINI_API_KEY}" \
    -e STORAGE_BACKEND=local \
    sdoc-app:local

# 3. Open http://localhost:8080 in your browser
#    Sidebar should show: Runtime: Local Workstation | Storage: Local JSON
```

If `docker build` or `docker run` fail, check:
- All dependencies are listed in `requirements.txt`
- `.dockerignore` correctly excludes `.env`, `__pycache__`, `results/storage_local.json`

---

## 1. Prerequisites & Environment Setup

Ensure you have the [Google Cloud SDK (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed and logged in.

```bash
# 1. Login to your Google Cloud account
gcloud auth login

# 2. Define your GCP Project ID and deployment region
export PROJECT_ID="your-gcp-project-id"
export REGION="asia-southeast1"   # or us-central1 / europe-west1

# 3. Set the active project
gcloud config set project ${PROJECT_ID}
export PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
```

---

## 2. Enable Required GCP APIs

```bash
gcloud services enable \
    run.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    cloudbuild.googleapis.com \
    firestore.googleapis.com
```

---

## 3. Configure Google Secret Manager (API Key Security)

Never commit or hardcode secrets into the container or any source file. Store `GEMINI_API_KEY` securely in Secret Manager.

```bash
# 1. Create the secret container
gcloud secrets create gemini-api-key \
    --replication-policy="automatic"

# 2. Add the key value interactively from your local shell variable
#    (this reads from your local env, never from a file or command arg visible in ps/history)
printf '%s' "${GEMINI_API_KEY}" | gcloud secrets versions add gemini-api-key --data-file=-

# 3. Authorize Cloud Run's compute service account to read the secret
gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
```

> **Warning**: Avoid passing the API key via `--set-env-vars` in plaintext — use `--set-secrets` (see Step 6) so the value is injected from Secret Manager and never appears in Cloud Run's environment variable logs.

---

## 4. Dataset / Data Path Configuration

By default, `inbox/` and `attachments/` are bundled inside the container (copied by the Dockerfile). This means they are read from the container's local filesystem at `/app/inbox` and `/app/attachments`.

If the dataset is confirmed sensitive or should not be bundled, override the paths via environment variables at deploy time:

```bash
# Option A: Default — data bundled in container (current setup)
# No additional configuration needed.

# Option B: External GCS-backed volume or different path inside the container
#   Set these env vars in your gcloud run deploy command:
#   --set-env-vars="DATA_DIR=/mnt/data,INBOX_DIR=/mnt/data/inbox,ATTACHMENTS_DIR=/mnt/data/attachments"
```

> When deploying for demo/judging, Option A (bundled) is recommended — no additional GCS setup needed and eliminates cold-start I/O latency.

---

## 5. Initialize Cloud Firestore (Persistence)

Firestore stores human-in-the-loop operator review decisions and pipeline results across container restarts.

```bash
gcloud firestore databases create \
    --location=${REGION} \
    --type=firestore-native
```

After Firestore is initialized, the Streamlit sidebar will display **Storage: Google Cloud Firestore** when the app runs on Cloud Run.

---

## 6. Build and Push Container to Artifact Registry

```bash
# 1. Create the Docker repository in Artifact Registry
gcloud artifacts repositories create sdoc-repo \
    --repository-format=docker \
    --location=${REGION} \
    --description="SDOC Shipping Verification Containers"

# 2. Build and push the image using Cloud Build
#    This reads the local Dockerfile; secrets are NOT included in the build context
gcloud builds submit \
    --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/sdoc-repo/sdoc-app:latest .
```

---

## 7. Deploy to Google Cloud Run

```bash
gcloud run deploy sdoc-service \
    --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/sdoc-repo/sdoc-app:latest \
    --region=${REGION} \
    --platform=managed \
    --allow-unauthenticated \
    --port=8080 \
    --memory=2Gi \
    --cpu=2 \
    --timeout=300 \
    --min-instances=1 \
    --max-instances=10 \
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest" \
    --set-env-vars="STORAGE_BACKEND=local,GCP_PROJECT_ID=${PROJECT_ID},MAX_UPLOAD_SIZE_MB=5,SANDBOX_RATE_LIMIT_PER_MINUTE=15"
```

> [!NOTE]
> `--min-instances=1` keeps at least one container instance warm at all times. This prevents cold-start latency when judges visit the URL. Set this to `0` after judging to stop paying for idle instances.

> [!IMPORTANT]
> `GEMINI_API_KEY` is injected via `--set-secrets`, not `--set-env-vars`. This ensures the secret value is read from Secret Manager and **never appears in Cloud Run deployment logs, audit logs, or the GCP console's environment variable list**.

---

## 8. Verify Deployment

```bash
# Retrieve the live service URL
export SERVICE_URL=$(gcloud run services describe sdoc-service \
    --platform=managed --region=${REGION} --format="value(status.url)")

echo "SDOC Live URL: ${SERVICE_URL}"

# Test liveness & system health endpoint
curl -s ${SERVICE_URL}/healthz

# Run automated smoke test
python scripts/smoke_test.py ${SERVICE_URL}
```

### What to Verify in the Live Web App:

| Check | Expected |
|---|---|
| Sidebar → **Runtime** | `Google Cloud Run` |
| Sidebar → **Storage** | `Google Cloud Firestore` |
| Sidebar → **Engine** | `🟢 Hybrid Pipeline Active` |
| Sandbox upload > 5 MB | Blocked with size error |
| Sandbox > 5 uploads/min | Blocked with rate limit warning |
| Sandbox 429 from Gemini | Automatic deterministic fallback + visible notice |
| HITL "Mark Resolved" button | Decision persists after page reload |

---

## 9. Updating the Deployment

After code changes, rebuild and redeploy:

```bash
gcloud builds submit \
    --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/sdoc-repo/sdoc-app:latest .

gcloud run deploy sdoc-service \
    --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/sdoc-repo/sdoc-app:latest \
    --region=${REGION} \
    --platform=managed
```

---

## 10. Cost Control (Post-Judging)

```bash
# Scale down to zero idle instances to stop billing
gcloud run services update sdoc-service \
    --region=${REGION} \
    --min-instances=0

# Delete the service entirely if no longer needed
gcloud run services delete sdoc-service --region=${REGION}
```
