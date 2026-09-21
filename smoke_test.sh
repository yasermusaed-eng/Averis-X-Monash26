#!/usr/bin/env bash
# =============================================================================
# SDOC Public URL Smoke Test Wrapper
# =============================================================================
TARGET_URL="${1:-${SERVICE_URL:-http://localhost:8080}}"
python3 scripts/smoke_test.py "${TARGET_URL}" || python scripts/smoke_test.py "${TARGET_URL}"
