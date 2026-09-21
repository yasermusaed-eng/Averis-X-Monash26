# =============================================================================
# SDOC: Automated Shipping Document Verification
# One-Command Production Cloud Run Deploy Script — Windows PowerShell
# =============================================================================
# Usage:
#   $env:PROJECT_ID    = "your-gcp-project-id"
#   $env:GEMINI_API_KEY = "AIzaSy..."    # optional - can add to Secret Manager manually
#   $env:REGION        = "asia-southeast1"  # optional - defaults below
#   .\deploy.ps1
# =============================================================================

$ErrorActionPreference = "Stop"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  SDOC ONE-COMMAND DEPLOYMENT TO GOOGLE CLOUD RUN (PowerShell)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

# --- Check gcloud ---
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Write-Host "[-] Error: gcloud CLI not found. Install from:" -ForegroundColor Red
    Write-Host "    https://cloud.google.com/sdk/docs/install" -ForegroundColor Red
    Write-Host "    Or: winget install Google.CloudSDK" -ForegroundColor Yellow
    exit 1
}

# --- Configuration ---
$PROJECT_ID   = $env:PROJECT_ID   ?? (gcloud config get-value project 2>$null)
$REGION       = $env:REGION       ?? "asia-southeast1"
$SERVICE_NAME = "sdoc-service"
$REPO_NAME    = "sdoc-repo"
$IMAGE_TAG    = "${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/sdoc-app:latest"

if (-not $PROJECT_ID -or $PROJECT_ID -eq "(unset)") {
    Write-Host "[-] Error: PROJECT_ID not set." -ForegroundColor Red
    Write-Host "    Run: `$env:PROJECT_ID = 'your-gcp-project-id'" -ForegroundColor Yellow
    exit 1
}

Write-Host "[+] Project   : $PROJECT_ID" -ForegroundColor Green
Write-Host "[+] Region    : $REGION" -ForegroundColor Green
Write-Host "[+] Service   : $SERVICE_NAME" -ForegroundColor Green
Write-Host "[+] Image     : $IMAGE_TAG" -ForegroundColor Green
Write-Host "----------------------------------------------------------------------"

# --- Step 1: Enable APIs ---
Write-Host "[*] Enabling required GCP APIs..." -ForegroundColor Yellow
gcloud services enable `
    run.googleapis.com `
    artifactregistry.googleapis.com `
    secretmanager.googleapis.com `
    cloudbuild.googleapis.com `
    storage.googleapis.com `
    --project="$PROJECT_ID"

$PROJECT_NUMBER = gcloud projects describe $PROJECT_ID --format="value(projectNumber)"
$COMPUTE_SA = "${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
Write-Host "[+] Compute SA: $COMPUTE_SA" -ForegroundColor Green

# --- Step 2: Secret Manager ---
Write-Host "[*] Checking Secret Manager for 'gemini-api-key'..." -ForegroundColor Yellow
$secretExists = gcloud secrets describe gemini-api-key --project="$PROJECT_ID" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[*] Creating secret 'gemini-api-key'..." -ForegroundColor Yellow
    gcloud secrets create gemini-api-key `
        --replication-policy="automatic" `
        --project="$PROJECT_ID"

    if ($env:GEMINI_API_KEY) {
        $keyBytes = [System.Text.Encoding]::UTF8.GetBytes($env:GEMINI_API_KEY)
        $tmpFile  = [System.IO.Path]::GetTempFileName()
        [System.IO.File]::WriteAllBytes($tmpFile, $keyBytes)
        gcloud secrets versions add gemini-api-key --data-file="$tmpFile" --project="$PROJECT_ID"
        Remove-Item $tmpFile
        Write-Host "[+] GEMINI_API_KEY stored in Secret Manager." -ForegroundColor Green
    } else {
        Write-Host "[!] GEMINI_API_KEY not in environment. Add it manually:" -ForegroundColor Yellow
        Write-Host "    `$key = 'AIzaSy...'; [System.Text.Encoding]::UTF8.GetBytes(`$key) | Set-Content -Path tmp.bin -AsByteStream" -ForegroundColor Gray
        Write-Host "    gcloud secrets versions add gemini-api-key --data-file=tmp.bin" -ForegroundColor Gray
        Write-Host "    Remove-Item tmp.bin" -ForegroundColor Gray
    }
} else {
    Write-Host "[+] Secret 'gemini-api-key' already exists." -ForegroundColor Green
    if ($env:GEMINI_API_KEY) {
        Write-Host "[*] Updating secret version..." -ForegroundColor Yellow
        $keyBytes = [System.Text.Encoding]::UTF8.GetBytes($env:GEMINI_API_KEY)
        $tmpFile  = [System.IO.Path]::GetTempFileName()
        [System.IO.File]::WriteAllBytes($tmpFile, $keyBytes)
        gcloud secrets versions add gemini-api-key --data-file="$tmpFile" --project="$PROJECT_ID"
        Remove-Item $tmpFile
        Write-Host "[+] Secret version updated." -ForegroundColor Green
    }
}

# Grant IAM access
Write-Host "[*] Binding IAM: secretmanager.secretAccessor -> $COMPUTE_SA" -ForegroundColor Yellow
gcloud secrets add-iam-policy-binding gemini-api-key `
    --member="serviceAccount:$COMPUTE_SA" `
    --role="roles/secretmanager.secretAccessor" `
    --project="$PROJECT_ID" | Out-Null

# --- Step 3: Artifact Registry ---
Write-Host "[*] Checking Artifact Registry repository..." -ForegroundColor Yellow
$repoExists = gcloud artifacts repositories describe $REPO_NAME `
    --location="$REGION" --project="$PROJECT_ID" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[*] Creating Artifact Registry repository '$REPO_NAME'..." -ForegroundColor Yellow
    gcloud artifacts repositories create $REPO_NAME `
        --repository-format=docker `
        --location="$REGION" `
        --description="SDOC Shipping Document Verification Containers" `
        --project="$PROJECT_ID"
}
Write-Host "[+] Registry: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}" -ForegroundColor Green

# --- Step 4: Cloud Build ---
Write-Host "[*] Building and pushing image via Cloud Build..." -ForegroundColor Yellow
gcloud builds submit `
    --tag="$IMAGE_TAG" `
    --project="$PROJECT_ID" .
Write-Host "[+] Image pushed: $IMAGE_TAG" -ForegroundColor Green

# --- Step 5: Cloud Run Deploy ---
Write-Host "[*] Deploying to Cloud Run..." -ForegroundColor Yellow
gcloud run deploy $SERVICE_NAME `
    --image="$IMAGE_TAG" `
    --region="$REGION" `
    --project="$PROJECT_ID" `
    --platform=managed `
    --allow-unauthenticated `
    --port=8080 `
    --memory=2Gi `
    --cpu=2 `
    --timeout=300 `
    --min-instances=0 `
    --max-instances=3 `
    --concurrency=10 `
    --set-secrets="GEMINI_API_KEY=gemini-api-key:latest" `
    --set-env-vars="STORAGE_BACKEND=local,GCP_PROJECT_ID=$PROJECT_ID"

# --- Step 6: Get URL ---
$SERVICE_URL = gcloud run services describe $SERVICE_NAME `
    --platform=managed --region="$REGION" --project="$PROJECT_ID" `
    --format="value(status.url)"

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "[+] SUCCESS: SDOC deployed to Google Cloud Run!" -ForegroundColor Green
Write-Host "[+] Public URL : $SERVICE_URL" -ForegroundColor Green
Write-Host "[+] Healthz    : $SERVICE_URL/healthz" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan

# --- Step 7: Smoke test ---
Write-Host "[*] HTTP health check..." -ForegroundColor Yellow
try {
    $resp = Invoke-WebRequest -Uri "$SERVICE_URL/healthz" -TimeoutSec 15 -UseBasicParsing
    if ($resp.StatusCode -eq 200) {
        Write-Host "[+] Health check PASSED: HTTP $($resp.StatusCode)" -ForegroundColor Green
    } else {
        Write-Host "[!] Health check HTTP $($resp.StatusCode) - check Cloud Run logs" -ForegroundColor Yellow
    }
} catch {
    Write-Host "[!] Health check failed: $_" -ForegroundColor Yellow
    Write-Host "    Check logs: gcloud run services logs read $SERVICE_NAME --region=$REGION" -ForegroundColor Gray
}

Write-Host ""
Write-Host "[*] TIP: First visit after idle may take ~10s (cold start, min-instances=0)." -ForegroundColor Yellow
Write-Host "    Keep warm during judging:" -ForegroundColor Gray
Write-Host "    gcloud run services update $SERVICE_NAME --region=$REGION --min-instances=1" -ForegroundColor Gray
