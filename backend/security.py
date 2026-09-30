"""
Lightweight API-key protection for machine-to-machine endpoints.

Behaviour is opt-in: when settings.API_KEY is empty (the default) the guard is
a no-op, so nothing breaks out of the box. When API_KEY is set, callers must
send a matching `X-API-Key` header. The webhook endpoint keeps its own HMAC
verification and is not affected by this.
"""

import hmac
from typing import Optional

from fastapi import Header, HTTPException

from config import get_settings


async def require_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> None:
    """FastAPI dependency that enforces the API key only when one is configured."""
    settings = get_settings()

    # Auth disabled — endpoint is open.
    if not settings.API_KEY:
        return

    # Constant-time comparison to avoid timing side channels.
    if not x_api_key or not hmac.compare_digest(x_api_key, settings.API_KEY):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
