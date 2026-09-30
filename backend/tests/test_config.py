"""
Tests for configuration parsing in config.Settings.
"""

from config import Settings


def test_cors_origins_list_splits_and_strips():
    settings = Settings(
        GEMINI_API_KEY="x",
        CORS_ORIGINS="http://a.com, http://b.com ,http://c.com",
    )
    assert settings.cors_origins_list == [
        "http://a.com",
        "http://b.com",
        "http://c.com",
    ]


def test_cors_origins_list_ignores_empty_entries():
    settings = Settings(GEMINI_API_KEY="x", CORS_ORIGINS="http://a.com,,")
    assert settings.cors_origins_list == ["http://a.com"]


def test_public_api_url_defaults_to_published_backend_port():
    settings = Settings(GEMINI_API_KEY="x")
    # Must match the port the backend is published on in docker-compose (8080),
    # otherwise webhook URLs shown to users point at the wrong place.
    assert settings.PUBLIC_API_URL == "http://localhost:8080"
