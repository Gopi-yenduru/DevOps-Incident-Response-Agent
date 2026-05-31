"""
Incident management endpoints.
Full CRUD + resolution tracking + accuracy feedback + correlation queries.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.incident import Incident, IncidentStatus, FixAccuracyRating, SeverityLevel

logger = logging.getLogger("devops_agent.incidents")
router = APIRouter()


# ── Request Schemas ────────────────────────────────────────────────────
class ResolveRequest(BaseModel):
    """Request to resolve an incident."""
    resolution_note: Optional[str] = None


class RateRequest(BaseModel):
    """Request to rate agent fix accuracy."""
    rating: str = Field(..., pattern="^(correct|incorrect)$")


class UpdateStatusRequest(BaseModel):
    """Request to update incident status."""
    status: str = Field(..., pattern="^(open|resolved|false_positive)$")


# ── Endpoints ──────────────────────────────────────────────────────────
@router.get("/incidents")
async def list_incidents(
    severity: Optional[str] = None,
    status: Optional[str] = None,
    app_id: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    List incidents with pagination and filtering.
    Supports filtering by severity, status, and app_id.
    """
    query = select(Incident)

    # Apply filters
    if severity:
        query = query.where(Incident.severity == severity)
    if status:
        query = query.where(Incident.status == status)
    if app_id:
        try:
            query = query.where(Incident.app_id == uuid.UUID(app_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid app_id format")

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = (
        query
        .order_by(Incident.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(query)
    incidents = result.scalars().all()

    return {
        "success": True,
        "data": {
            "incidents": [_serialize_incident_summary(i) for i in incidents],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
            },
        },
        "error": None,
    }


@router.get("/incidents/{incident_id}")
async def get_incident(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get full incident detail including all agent outputs.
    Used by the IncidentDetail page for timeline display.
    """
    incident = await _get_incident_or_404(incident_id, db)

    return {
        "success": True,
        "data": _serialize_incident_full(incident),
        "error": None,
    }


@router.patch("/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    body: ResolveRequest = ResolveRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark an incident as resolved and calculate MTTR.
    MTTR = time from incident creation to resolution.
    """
    incident = await _get_incident_or_404(incident_id, db)

    if incident.status == IncidentStatus.RESOLVED:
        raise HTTPException(status_code=400, detail="Incident already resolved")

    now = datetime.now(timezone.utc)
    incident.status = IncidentStatus.RESOLVED
    incident.resolved_at = now

    # Calculate MTTR in seconds
    if incident.created_at:
        created = incident.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        delta = now - created
        incident.mttr_seconds = int(delta.total_seconds())

    logger.info(
        f"[incident:{incident_id}] resolved | "
        f"mttr={incident.mttr_seconds}s"
    )

    return {
        "success": True,
        "data": _serialize_incident_full(incident),
        "error": None,
    }


@router.patch("/incidents/{incident_id}/status")
async def update_incident_status(
    incident_id: str,
    body: UpdateStatusRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Update incident status (open, resolved, false_positive).
    Calculates MTTR when resolving.
    """
    incident = await _get_incident_or_404(incident_id, db)

    incident.status = body.status

    if body.status == "resolved" and not incident.resolved_at:
        now = datetime.now(timezone.utc)
        incident.resolved_at = now
        if incident.created_at:
            created = incident.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            incident.mttr_seconds = int((now - created).total_seconds())

    return {
        "success": True,
        "data": _serialize_incident_full(incident),
        "error": None,
    }


@router.patch("/incidents/{incident_id}/rate")
async def rate_incident_fix(
    incident_id: str,
    body: RateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Rate the agent's fix suggestion as correct or incorrect.
    Used for agent accuracy tracking and continuous improvement.
    """
    incident = await _get_incident_or_404(incident_id, db)

    incident.fix_accuracy_rating = body.rating

    logger.info(
        f"[incident:{incident_id}] rated as {body.rating}"
    )

    return {
        "success": True,
        "data": {
            "id": str(incident.id),
            "fix_accuracy_rating": incident.fix_accuracy_rating,
        },
        "error": None,
    }


@router.get("/incidents/{incident_id}/correlated")
async def get_correlated_incidents(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get all incidents correlated with the given incident.
    Uses the correlated_incident_ids JSONB field.
    """
    incident = await _get_incident_or_404(incident_id, db)

    correlated = []
    if incident.correlated_incident_ids:
        for cid in incident.correlated_incident_ids:
            try:
                corr_incident = await db.get(Incident, uuid.UUID(str(cid)))
                if corr_incident:
                    correlated.append(_serialize_incident_summary(corr_incident))
            except (ValueError, Exception):
                continue

    return {
        "success": True,
        "data": {
            "incident_id": str(incident.id),
            "correlation_reason": incident.correlation_reason,
            "correlated_incidents": correlated,
        },
        "error": None,
    }


# ── Helpers ────────────────────────────────────────────────────────────
async def _get_incident_or_404(
    incident_id: str,
    db: AsyncSession,
) -> Incident:
    """Fetch an incident by ID or raise 404."""
    try:
        inc_uuid = uuid.UUID(incident_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident_id format")

    incident = await db.get(Incident, inc_uuid)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


def _serialize_incident_summary(incident: Incident) -> dict:
    """Serialize an incident for list views (summary fields only)."""
    return {
        "id": str(incident.id),
        "app_id": str(incident.app_id),
        "title": incident.title,
        "severity": incident.severity.value if hasattr(incident.severity, 'value') else incident.severity,
        "status": incident.status.value if hasattr(incident.status, 'value') else incident.status,
        "error_type": incident.error_type,
        "affected_service": incident.affected_service,
        "anomaly_confidence": incident.anomaly_confidence,
        "is_correlated": bool(incident.correlated_incident_ids),
        "fix_accuracy_rating": incident.fix_accuracy_rating.value if hasattr(incident.fix_accuracy_rating, 'value') else incident.fix_accuracy_rating,
        "github_issue_url": incident.github_issue_url,
        "created_at": incident.created_at.isoformat() if incident.created_at else None,
        "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
        "mttr_seconds": incident.mttr_seconds,
    }


def _serialize_incident_full(incident: Incident) -> dict:
    """Serialize an incident with all agent outputs for detail view."""
    return {
        **_serialize_incident_summary(incident),
        "error_message": incident.error_message,
        "frequency": incident.frequency,
        # Root cause
        "root_cause": incident.root_cause,
        "causal_chain": incident.causal_chain or [],
        "blast_radius": incident.blast_radius,
        "historical_pattern": incident.historical_pattern,
        # Fix
        "fix_summary": incident.fix_summary,
        "fix_steps": incident.fix_steps or [],
        "fix_code_snippet": incident.fix_code_snippet,
        "fix_complexity": incident.fix_complexity,
        "estimated_time": incident.estimated_time,
        "preventive_measure": incident.preventive_measure,
        # Confidence
        "rootcause_confidence": incident.rootcause_confidence,
        "fix_confidence": incident.fix_confidence,
        # Correlation
        "correlated_incident_ids": incident.correlated_incident_ids or [],
        "correlation_reason": incident.correlation_reason,
        # Response
        "github_pr_url": incident.github_pr_url,
        "telegram_sent": incident.telegram_sent,
        # Raw agent outputs (for timeline)
        "agent_outputs": {
            "anomaly_detector": incident.raw_anomaly_output,
            "incident_correlator": incident.raw_correlation_output,
            "root_cause_analyzer": incident.raw_rootcause_output,
            "fix_suggestion": incident.raw_fix_output,
            "response_orchestrator": incident.raw_response_output,
        },
        # Source logs
        "source_log_ids": incident.source_log_ids or [],
    }
