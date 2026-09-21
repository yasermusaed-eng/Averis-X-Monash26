"""
SDOC Gemini API Key Resolution Module.

Designed for production Google Cloud Run deployments where secrets are injected
via Google Secret Manager as environment variables (GEMINI_API_KEY).

Precedence:
1. Explicit function argument (if provided and non-empty).
2. os.environ["GEMINI_API_KEY"] (Cloud Run / Secret Manager / Docker ENV / .env).
3. Streamlit st.secrets["GEMINI_API_KEY"] (Streamlit Cloud fallback, safely guarded).

Returns empty string ("") if not configured, allowing the application to run
gracefully in 100% Deterministic Engine mode with zero crashes or exceptions.
"""

import os
from typing import Optional


def resolve_gemini_api_key(explicit_key: Optional[str] = None) -> str:
    """
    Resolve Gemini API key with strict environment variable precedence.

    Parameters:
        explicit_key: Optional key directly passed in code.

    Returns:
        Clean string key, or empty string "" if not configured.
    """
    # 1. Explicit parameter (if caller supplied one)
    if explicit_key and str(explicit_key).strip():
        return str(explicit_key).strip()

    # 2. Environment Variable Priority (Google Cloud Run / Secret Manager / Docker)
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key

    # 3. Streamlit secrets fallback (guarded against missing secrets.toml)
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            try:
                sec_val = st.secrets.get("GEMINI_API_KEY", "")
                if sec_val and str(sec_val).strip():
                    return str(sec_val).strip()
            except Exception:
                pass
    except ImportError:
        pass

    return ""


def is_gemini_configured(explicit_key: Optional[str] = None) -> bool:
    """Return True if a valid non-empty Gemini API key is available."""
    return bool(resolve_gemini_api_key(explicit_key))
