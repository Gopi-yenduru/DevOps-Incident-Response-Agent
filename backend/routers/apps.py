"""
Monitored application management endpoints.
Register, list, and manage applications being monitored by the agent system.
"""

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.app_target import MonitoredApp
from config import get_settings

logger = logging.getLogger("devops_agent.apps")
router = APIRouter()
settings = get_settings()


# ── Request/Response Schemas ───────────────────────────────────────────
class CreateAppRequest(BaseModel):
    """Request to register a new monitored application."""
    name: str = Field(..., min_length=1, max_length=255, description="Application name")
    description: Optional[str] = Field(None, description="Application description")


class UpdateAppRequest(BaseModel):
    """Request to update an existing application."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────
@router.post("/apps")
async def create_app(
    body: CreateAppRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new application for monitoring.
    Auto-generates a webhook_secret for secure log ingestion.
    """
    # Check for duplicate name
    existing = await db.execute(
        select(MonitoredApp).where(MonitoredApp.name == body.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"App with name '{body.name}' already exists",
        )

    app = MonitoredApp(
        name=body.name,
        description=body.description,
        webhook_secret=uuid.uuid4().hex,
    )
    db.add(app)
    await db.flush()

    logger.info(f"[app:created] name={app.name} id={app.id}")

    return {
        "success": True,
        "data": _serialize_app(app, include_secret=True),
        "error": None,
    }


@router.get("/apps")
async def list_apps(
    db: AsyncSession = Depends(get_db),
):
    """List all monitored applications."""
    result = await db.execute(
        select(MonitoredApp).order_by(MonitoredApp.created_at.desc())
    )
    apps = result.scalars().all()

    return {
        "success": True,
        "data": {
            "apps": [_serialize_app(a) for a in apps],
            "total": len(apps),
        },
        "error": None,
    }


@router.get("/apps/{app_id}")
async def get_app(
    app_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get application details including webhook integration instructions.
    Shows the webhook_secret for initial setup.
    """
    app = await _get_app_or_404(app_id, db)

    base_url = "http://localhost:8000"  # Will be dynamic in production

    return {
        "success": True,
        "data": {
            **_serialize_app(app, include_secret=True),
            "integration": {
                "webhook_url": f"{base_url}/api/v1/logs/webhook/{app.id}",
                "ingest_url": f"{base_url}/api/v1/logs/ingest",
                "instructions": (
                    "Send POST requests with JSON body: "
                    '{"logs": ["log line 1", "log line 2"]}. '
                    "Include X-Signature header with HMAC-SHA256 of the body "
                    "using your webhook_secret for secure delivery."
                ),
                "example_curl": (
                    f'curl -X POST {base_url}/api/v1/logs/webhook/{app.id} '
                    f'-H "Content-Type: application/json" '
                    f'-H "X-Signature: sha256=<hmac_hex>" '
                    f'-d \'{{"logs": ["ERROR: Connection timeout in auth-service"]}}\''
                ),
            },
        },
        "error": None,
    }


@router.put("/apps/{app_id}")
async def update_app(
    app_id: str,
    body: UpdateAppRequest,
    db: AsyncSession = Depends(get_db),
):
    """Update an application's name or description."""
    app = await _get_app_or_404(app_id, db)

    if body.name is not None:
        # Check duplicate
        existing = await db.execute(
            select(MonitoredApp)
            .where(MonitoredApp.name == body.name)
            .where(MonitoredApp.id != app.id)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail=f"App with name '{body.name}' already exists",
            )
        app.name = body.name

    if body.description is not None:
        app.description = body.description

    logger.info(f"[app:updated] id={app.id}")

    return {
        "success": True,
        "data": _serialize_app(app),
        "error": None,
    }


@router.delete("/apps/{app_id}")
async def delete_app(
    app_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete an application and all its associated logs and incidents.
    This is a destructive operation — use with caution.
    """
    app = await _get_app_or_404(app_id, db)

    app_name = app.name
    await db.delete(app)

    logger.info(f"[app:deleted] name={app_name} id={app_id}")

    return {
        "success": True,
        "data": {"deleted": True, "app_id": app_id, "name": app_name},
        "error": None,
    }


@router.post("/apps/{app_id}/regenerate-secret")
async def regenerate_webhook_secret(
    app_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Regenerate the webhook secret for an application."""
    app = await _get_app_or_404(app_id, db)

    app.webhook_secret = uuid.uuid4().hex
    logger.info(f"[app:secret-regenerated] id={app.id}")

    return {
        "success": True,
        "data": _serialize_app(app, include_secret=True),
        "error": None,
    }


# ── Helpers ────────────────────────────────────────────────────────────
async def _get_app_or_404(app_id: str, db: AsyncSession) -> MonitoredApp:
    """Fetch an app by ID or raise 404."""
    try:
        app_uuid = uuid.UUID(app_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid app_id format")

    app = await db.get(MonitoredApp, app_uuid)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return app


def _serialize_app(app: MonitoredApp, include_secret: bool = False) -> dict:
    """Serialize a MonitoredApp for API responses."""
    data = {
        "id": str(app.id),
        "name": app.name,
        "description": app.description,
        "created_at": app.created_at.isoformat() if app.created_at else None,
    }
    if include_secret:
        data["webhook_secret"] = app.webhook_secret
    return data
