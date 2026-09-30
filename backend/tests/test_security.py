"""
Tests for the opt-in API-key guard (security.require_api_key).
"""

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from config import Settings
from security import require_api_key


def _settings(api_key: str) -> Settings:
    return Settings(GEMINI_API_KEY="x", API_KEY=api_key)


async def test_disabled_when_no_key_configured():
    # No API_KEY set → guard is a no-op even with no header.
    with patch("security.get_settings", return_value=_settings("")):
        assert await require_api_key(None) is None


async def test_allows_matching_key():
    with patch("security.get_settings", return_value=_settings("s3cret")):
        assert await require_api_key("s3cret") is None


async def test_rejects_missing_key_when_enabled():
    with patch("security.get_settings", return_value=_settings("s3cret")):
        with pytest.raises(HTTPException) as exc:
            await require_api_key(None)
        assert exc.value.status_code == 401


async def test_rejects_wrong_key_when_enabled():
    with patch("security.get_settings", return_value=_settings("s3cret")):
        with pytest.raises(HTTPException) as exc:
            await require_api_key("wrong")
        assert exc.value.status_code == 401
