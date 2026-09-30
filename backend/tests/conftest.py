"""
Shared pytest configuration.

Sets required environment variables BEFORE any application module is imported,
because several modules read settings (which require GEMINI_API_KEY) and build
a database engine at import time. No real API key or database is needed — these
tests never make network calls or touch a live DB.
"""

import os

os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
os.environ.setdefault("GEMINI_MODEL", "gemini-2.0-flash")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://user:pass@localhost:5432/devops_agent_test",
)
# Ensure no external integrations are treated as configured during tests.
os.environ.setdefault("GITHUB_TOKEN", "")
os.environ.setdefault("GITHUB_REPO", "")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "")
os.environ.setdefault("TELEGRAM_CHAT_ID", "")
