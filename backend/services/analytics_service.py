"""
Analytics service.

Provides aggregated metrics for the dashboard:
overview stats, MTTR trends, severity breakdown,
accuracy tracking, and correlation statistics.

This service contains the business logic used by the analytics router.
For simpler analytics, the router queries the DB directly.
This service is used for complex aggregations and derived metrics.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from sqlalchemy import select, func, and_, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from models.incident import (
    Incident,
    IncidentStatus,
    FixAccuracyRating,
)

logger = logging.getLogger("devops_agent.service.analytics")


async def get_overview(db: AsyncSession) -> dict[str, Any]:
    """
    Compute dashboard overview metrics.

    Returns:
        Dict with total/open/resolved counts, avg MTTR,
        incidents today, and agent accuracy.
    """
    # Status counts
    result = await db.execute(
        select(
            func.count().label("total"),
            func.count().filter(Incident.status == IncidentStatus.OPEN).label("open"),
            func.count().filter(Incident.status == IncidentStatus.RESOLVED).label("resolved"),
            func.count().filter(Incident.status == IncidentStatus.FALSE_POSITIVE).label("false_positive"),
        ).select_from(Incident)
    )
    counts = result.one()

    # Average MTTR
    mttr_result = await db.execute(
        select(func.avg(Incident.mttr_seconds)).where(
            and_(
                Incident.status == IncidentStatus.RESOLVED,
                Incident.mttr_seconds.isnot(None),
            )
        )
    )
    avg_mttr = mttr_result.scalar()

    # Today's incidents
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    today_result = await db.execute(
        select(func.count()).where(Incident.created_at >= today_start)
    )
    incidents_today = today_result.scalar() or 0

    # Accuracy
    accuracy_result = await db.execute(
        select(
            func.count().filter(
                Incident.fix_accuracy_rating != FixAccuracyRating.UNRATED
            ).label("rated"),
            func.count().filter(
                Incident.fix_accuracy_rating == FixAccuracyRating.CORRECT
            ).label("correct"),
        ).select_from(Incident)
    )
    acc = accuracy_result.one()
    accuracy = (
        round((acc.correct / acc.rated) * 100, 1) if acc.rated > 0 else None
    )

    return {
        "total_incidents": counts.total,
        "open_incidents": counts.open,
        "resolved_incidents": counts.resolved,
        "false_positives": counts.false_positive,
        "avg_mttr_seconds": round(avg_mttr) if avg_mttr else None,
        "incidents_today": incidents_today,
        "agent_accuracy_percent": accuracy,
    }


async def get_mttr_trend(
    db: AsyncSession,
    days: int = 30,
) -> list[dict[str, Any]]:
    """
    Compute average MTTR per day for trend charting.

    Args:
        db: Database session.
        days: Number of days to look back.

    Returns:
        List of {date, avg_mttr_seconds, count} dicts.
    """
    start = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            cast(Incident.resolved_at, Date).label("date"),
            func.avg(Incident.mttr_seconds).label("avg_mttr"),
            func.count().label("count"),
        )
        .where(
            and_(
                Incident.resolved_at >= start,
                Incident.status == IncidentStatus.RESOLVED,
                Incident.mttr_seconds.isnot(None),
            )
        )
        .group_by(cast(Incident.resolved_at, Date))
        .order_by(cast(Incident.resolved_at, Date))
    )
    rows = result.all()

    return [
        {
            "date": row.date.isoformat() if row.date else None,
            "avg_mttr_seconds": round(row.avg_mttr) if row.avg_mttr else 0,
            "incidents_resolved": row.count,
        }
        for row in rows
    ]


async def get_severity_breakdown(db: AsyncSession) -> list[dict[str, Any]]:
    """Count of incidents by severity level."""
    result = await db.execute(
        select(
            Incident.severity,
            func.count().label("count"),
        )
        .group_by(Incident.severity)
        .order_by(func.count().desc())
    )
    return [
        {
            "severity": row.severity.value if hasattr(row.severity, 'value') else row.severity,
            "count": row.count,
        }
        for row in result.all()
    ]


async def get_error_type_ranking(
    db: AsyncSession,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Top N most frequent error types."""
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
    return [
        {"error_type": row.error_type, "count": row.count}
        for row in result.all()
    ]


async def get_agent_accuracy(db: AsyncSession) -> dict[str, Any]:
    """
    Compute agent fix accuracy stats.

    Returns:
        Dict with accuracy_percent, total_rated, correct, incorrect counts.
    """
    result = await db.execute(
        select(
            Incident.fix_accuracy_rating,
            func.count().label("count"),
        )
        .group_by(Incident.fix_accuracy_rating)
    )

    breakdown = {}
    total_rated = 0
    correct = 0

    for row in result.all():
        rating = row.fix_accuracy_rating.value if hasattr(row.fix_accuracy_rating, 'value') else row.fix_accuracy_rating
        breakdown[rating] = row.count
        if rating != "unrated":
            total_rated += row.count
        if rating == "correct":
            correct = row.count

    accuracy = round((correct / total_rated) * 100, 1) if total_rated > 0 else None

    return {
        "accuracy_percent": accuracy,
        "total_rated": total_rated,
        "correct": correct,
        "incorrect": breakdown.get("incorrect", 0),
        "unrated": breakdown.get("unrated", 0),
    }


async def get_correlation_stats(db: AsyncSession) -> dict[str, Any]:
    """Percentage of incidents that were correlated."""
    total_result = await db.execute(
        select(func.count()).select_from(Incident)
    )
    total = total_result.scalar() or 0

    correlated_result = await db.execute(
        select(func.count()).where(
            and_(
                Incident.correlated_incident_ids.isnot(None),
                func.jsonb_array_length(Incident.correlated_incident_ids) > 0,
            )
        )
    )
    correlated = correlated_result.scalar() or 0

    rate = round((correlated / total) * 100, 1) if total > 0 else 0

    return {
        "total_incidents": total,
        "correlated_incidents": correlated,
        "correlation_rate_percent": rate,
    }
