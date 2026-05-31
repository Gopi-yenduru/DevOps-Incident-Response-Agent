"""
Analytics endpoints.
Provides dashboard data: overview stats, MTTR trends, severity breakdown,
agent accuracy, and error type rankings.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, case, and_, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.incident import (
    Incident,
    IncidentStatus,
    FixAccuracyRating,
    SeverityLevel,
)

logger = logging.getLogger("devops_agent.analytics")
router = APIRouter()


@router.get("/analytics/overview")
async def get_overview(
    db: AsyncSession = Depends(get_db),
):
    """
    Dashboard overview stats:
    - Total incidents, open, resolved, false positives
    - Average MTTR (seconds)
    - Incidents today
    - Agent accuracy percentage
    """
    # Total counts by status
    status_counts = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(Incident.status == IncidentStatus.OPEN).label("open"),
            func.count().filter(Incident.status == IncidentStatus.RESOLVED).label("resolved"),
            func.count().filter(Incident.status == IncidentStatus.FALSE_POSITIVE).label("false_positive"),
        ).select_from(Incident)
    )
    row = status_counts.one()

    # Average MTTR (only resolved incidents with MTTR data)
    mttr_result = await db.execute(
        select(func.avg(Incident.mttr_seconds)).where(
            and_(
                Incident.status == IncidentStatus.RESOLVED,
                Incident.mttr_seconds.isnot(None),
            )
        )
    )
    avg_mttr = mttr_result.scalar()

    # Incidents today
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today_result = await db.execute(
        select(func.count()).where(Incident.created_at >= today_start)
    )
    incidents_today = today_result.scalar() or 0

    # Resolved today
    resolved_today_result = await db.execute(
        select(func.count()).where(
            and_(
                Incident.resolved_at >= today_start,
                Incident.status == IncidentStatus.RESOLVED,
            )
        )
    )
    resolved_today = resolved_today_result.scalar() or 0

    # Agent accuracy (% of rated incidents marked correct)
    rated_result = await db.execute(
        select(
            func.count().filter(
                Incident.fix_accuracy_rating != FixAccuracyRating.UNRATED
            ).label("rated"),
            func.count().filter(
                Incident.fix_accuracy_rating == FixAccuracyRating.CORRECT
            ).label("correct"),
        ).select_from(Incident)
    )
    rated_row = rated_result.one()
    accuracy = (
        round((rated_row.correct / rated_row.rated) * 100, 1)
        if rated_row.rated > 0
        else None
    )

    return {
        "success": True,
        "data": {
            "total_incidents": row.total,
            "open_incidents": row.open,
            "resolved_incidents": row.resolved,
            "false_positives": row.false_positive,
            "avg_mttr_seconds": round(avg_mttr) if avg_mttr else None,
            "incidents_today": incidents_today,
            "resolved_today": resolved_today,
            "agent_accuracy_percent": accuracy,
            "rated_incidents": rated_row.rated,
        },
        "error": None,
    }


@router.get("/analytics/mttr")
async def get_mttr_trend(
    days: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """
    Average MTTR per day over the specified number of days.
    Returns data points for trend charts.
    """
    start_date = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            cast(Incident.resolved_at, Date).label("date"),
            func.avg(Incident.mttr_seconds).label("avg_mttr"),
            func.count().label("count"),
        )
        .where(
            and_(
                Incident.resolved_at >= start_date,
                Incident.status == IncidentStatus.RESOLVED,
                Incident.mttr_seconds.isnot(None),
            )
        )
        .group_by(cast(Incident.resolved_at, Date))
        .order_by(cast(Incident.resolved_at, Date))
    )
    rows = result.all()

    return {
        "success": True,
        "data": {
            "trend": [
                {
                    "date": row.date.isoformat() if row.date else None,
                    "avg_mttr_seconds": round(row.avg_mttr) if row.avg_mttr else 0,
                    "incidents_resolved": row.count,
                }
                for row in rows
            ],
            "period_days": days,
        },
        "error": None,
    }


@router.get("/analytics/severity")
async def get_severity_breakdown(
    db: AsyncSession = Depends(get_db),
):
    """
    Count of incidents grouped by severity level.
    Used for donut/pie chart visualization.
    """
    result = await db.execute(
        select(
            Incident.severity,
            func.count().label("count"),
        )
        .group_by(Incident.severity)
        .order_by(func.count().desc())
    )
    rows = result.all()

    return {
        "success": True,
        "data": {
            "breakdown": [
                {
                    "severity": row.severity.value if hasattr(row.severity, 'value') else row.severity,
                    "count": row.count,
                }
                for row in rows
            ],
        },
        "error": None,
    }


@router.get("/analytics/accuracy")
async def get_agent_accuracy(
    db: AsyncSession = Depends(get_db),
):
    """
    Agent fix accuracy stats.
    Returns counts of correct, incorrect, and unrated incidents.
    """
    result = await db.execute(
        select(
            Incident.fix_accuracy_rating,
            func.count().label("count"),
        )
        .group_by(Incident.fix_accuracy_rating)
    )
    rows = result.all()

    breakdown = {}
    total_rated = 0
    correct = 0

    for row in rows:
        rating = row.fix_accuracy_rating.value if hasattr(row.fix_accuracy_rating, 'value') else row.fix_accuracy_rating
        breakdown[rating] = row.count
        if rating != "unrated":
            total_rated += row.count
        if rating == "correct":
            correct = row.count

    accuracy_percent = (
        round((correct / total_rated) * 100, 1) if total_rated > 0 else None
    )

    return {
        "success": True,
        "data": {
            "accuracy_percent": accuracy_percent,
            "total_rated": total_rated,
            "correct": correct,
            "incorrect": breakdown.get("incorrect", 0),
            "unrated": breakdown.get("unrated", 0),
            "breakdown": breakdown,
        },
        "error": None,
    }


@router.get("/analytics/errors")
async def get_error_type_ranking(
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """
    Top N most frequent error types across all incidents.
    Used for bar chart or ranked list visualization.
    """
    result = await db.execute(
        select(
            Incident.error_type,
            func.count().label("count"),
        )
        .where(Incident.error_type.isnot(None))
        .group_by(Incident.error_type)
        .order_by(func.count().desc())
        .limit(limit)
    )
    rows = result.all()

    return {
        "success": True,
        "data": {
            "error_types": [
                {"error_type": row.error_type, "count": row.count}
                for row in rows
            ],
        },
        "error": None,
    }


@router.get("/analytics/correlation")
async def get_correlation_stats(
    db: AsyncSession = Depends(get_db),
):
    """
    Correlation statistics: percentage of incidents that were correlated
    with at least one other incident.
    """
    total_result = await db.execute(
        select(func.count()).select_from(Incident)
    )
    total = total_result.scalar() or 0

    # Incidents with non-empty correlated_incident_ids
    correlated_result = await db.execute(
        select(func.count()).where(
            and_(
                Incident.correlated_incident_ids.isnot(None),
                func.jsonb_array_length(Incident.correlated_incident_ids) > 0,
            )
        )
    )
    correlated = correlated_result.scalar() or 0

    correlation_rate = (
        round((correlated / total) * 100, 1) if total > 0 else 0
    )

    return {
        "success": True,
        "data": {
            "total_incidents": total,
            "correlated_incidents": correlated,
            "correlation_rate_percent": correlation_rate,
        },
        "error": None,
    }
