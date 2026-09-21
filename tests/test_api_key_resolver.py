"""
Unit tests for SDOC API Key Resolver.
Verifies Cloud Run environment variable precedence and graceful fallback behavior.
"""

import os
import unittest
from unittest.mock import patch, MagicMock

from src.api_key_resolver import resolve_gemini_api_key, is_gemini_configured


class TestApiKeyResolver(unittest.TestCase):

    def test_environment_variable_precedence(self):
        """Confirm os.environ['GEMINI_API_KEY'] is returned and takes precedence."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "AIzaSyTestCloudRunKey123"}, clear=False):
            key = resolve_gemini_api_key()
            self.assertEqual(key, "AIzaSyTestCloudRunKey123")
            self.assertTrue(is_gemini_configured())

    def test_explicit_argument_precedence(self):
        """Explicit parameter should override environment variable."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "EnvKey"}, clear=False):
            key = resolve_gemini_api_key("ExplicitKey456")
            self.assertEqual(key, "ExplicitKey456")

    def test_empty_environment_variable_handled_gracefully(self):
        """When GEMINI_API_KEY is not set or empty, returns empty string without crashing."""
        env_without_key = os.environ.copy()
        env_without_key.pop("GEMINI_API_KEY", None)
        with patch.dict(os.environ, env_without_key, clear=True):
            key = resolve_gemini_api_key()
            self.assertEqual(key, "")
            self.assertFalse(is_gemini_configured())

    def test_whitespace_only_key_is_stripped(self):
        """Whitespace only is treated as unconfigured."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "   "}, clear=True):
            key = resolve_gemini_api_key()
            self.assertEqual(key, "")
            self.assertFalse(is_gemini_configured())

    def test_st_secrets_fallback_when_env_empty(self):
        """If env var is missing, safely falls back to st.secrets if present."""
        mock_st = MagicMock()
        mock_st.secrets = {"GEMINI_API_KEY": "StreamlitSecretKey789"}

        env_without_key = os.environ.copy()
        env_without_key.pop("GEMINI_API_KEY", None)
        with patch.dict(os.environ, env_without_key, clear=True):
            with patch.dict("sys.modules", {"streamlit": mock_st}):
                key = resolve_gemini_api_key()
                self.assertEqual(key, "StreamlitSecretKey789")


if __name__ == "__main__":
    unittest.main()
