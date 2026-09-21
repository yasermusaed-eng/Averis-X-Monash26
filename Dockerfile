# =============================================================================
# SDOC: Automated Shipping Document Verification Engine
# Production Container for Google Cloud Run (Python 3.14-slim)
# =============================================================================

FROM python:3.14-slim

# System configuration & Cloud Run defaults
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ENABLE_CORS=false \
    STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# Install runtime utilities (curl for container health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Layer 1: Pinned Python dependencies (leveraging Docker layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Layer 2: Application code, static assets, configuration, and data
COPY . .

# Expose default Cloud Run port (informational; Cloud Run binds to $PORT dynamically)
EXPOSE 8080

# Health check probe for local Docker runs and orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8080}/healthz || exit 1

# Cloud Run dynamic PORT binding:
# Cloud Run passes $PORT as an environment variable (e.g. PORT=8080).
# We invoke Streamlit via sh -c to expand ${PORT:-8080} dynamically at runtime.
ENTRYPOINT ["sh", "-c", "exec streamlit run app.py --server.port=${PORT:-8080} --server.address=0.0.0.0 --server.enableCORS=false --server.enableXsrfProtection=false --server.headless=true --browser.gatherUsageStats=false"]
