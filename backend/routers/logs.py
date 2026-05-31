"""
Log ingestion and webhook endpoints.
Handles raw log reception from monitored applications
and queues anomalous logs for the agent pipeline.
"""

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.incident import LogEntry
from models.app_target import MonitoredApp

logger = logging.getLogger("devops_agent.logs")
router = APIRouter()


# ── Request/Response Schemas ───────────────────────────────────────────
class LogIngestRequest(BaseModel):
    """Request body for log ingestion."""
    app_id: str = Field(..., description="UUID of the monitored application")
    logs: list[str] = Field(..., min_length=1, description="List of raw log lines")
    timestamp: Optional[str] = Field(None, description="ISO timestamp for the log batch")


class LogIngestResponse(BaseModel):
    """Response for log ingestion."""
    received: int
    queued_for_analysis: int
    batch_id: str


class LogEntryResponse(BaseModel):
    """Single log entry in API responses."""
    id: str
    app_id: str
    raw_log: str
    severity: str | None
    timestamp: str
    processed: bool
    batch_id: str | None

    model_config = {"from_attributes": True}


# ── Severity Detection Heuristic ──────────────────────────────────────
ERROR_KEYWORDS = [
    "error", "exception", "fatal", "critical", "fail", "crash",
    "timeout", "refused", "denied", "500", "503", "502",
    "outofmemory", "oom", "segfault", "panic", "abort",
    "nullpointer", "null pointer", "unhandled", "traceback",
    "stack overflow", "deadlock", "connection reset",
]


def classify_log_severity(log_line: str) -> tuple[str, bool]:
    """
    Simple keyword-based severity classification.
    Returns (severity, is_anomaly) tuple.

    This is a pre-filter — the LLM agent does the real classification.
    """
    lower = log_line.lower()

    if any(kw in lower for kw in ["fatal", "critical", "panic", "abort", "segfault"]):
        return "critical", True
    if any(kw in lower for kw in ["error", "exception", "fail", "crash", "500", "502", "503", "outofmemory", "oom", "nullpointer", "null pointer", "unhandled", "traceback"]):
        return "error", True
    if any(kw in lower for kw in ["warn", "timeout", "refused", "denied", "retry", "slow"]):
        return "warning", True

    return "normal", False


async def process_logs_background(
    log_entry_ids: list[str],
    app_id: str,
):
    """
    Background task: send queued logs through the agent pipeline.
    This is a placeholder that will be wired to the LangGraph pipeline in Phase 2.
    """
    logger.info(
        f"[background] Processing {len(log_entry_ids)} anomalous logs "
        f"for app {app_id}"
    )
    # Phase 2 will import and call: await run_incident_pipeline(log_entry_ids, app_id)


# ── Endpoints ──────────────────────────────────────────────────────────
@router.post("/logs/ingest", response_model=None)
async def ingest_logs(
    request: LogIngestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest raw log lines from a monitored application.

    - Validates the app exists
    - Saves each log line to the database with severity classification
    - If any log is classified as error/critical, queues the batch for
      agent pipeline analysis as a background task
    - Returns immediately with count of received and queued logs
    """
    # Validate app exists
    try:
        app_uuid = uuid.UUID(request.app_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid app_id format")

    app = await db.get(MonitoredApp, app_uuid)
    if not app:
        raise HTTPException(status_code=404, detail=f"App {request.app_id} not found")

    batch_id = uuid.uuid4().hex[:16]
    anomalous_ids: list[str] = []

    # Process each log line
    for raw_log in request.logs:
        severity, is_anomaly = classify_log_severity(raw_log)

        log_entry = LogEntry(
            app_id=app_uuid,
            raw_log=raw_log,
            severity=severity,
            timestamp=datetime.now(timezone.utc),
            processed=False,
            batch_id=batch_id,
        )
        db.add(log_entry)
        await db.flush()

        if is_anomaly:
            anomalous_ids.append(str(log_entry.id))

    # Queue anomalous logs for agent pipeline
    if anomalous_ids:
        background_tasks.add_task(
            process_logs_background,
            anomalous_ids,
            request.app_id,
        )
        logger.info(
            f"[ingest] app={request.app_id} received={len(request.logs)} "
            f"anomalous={len(anomalous_ids)} batch={batch_id}"
        )

    return {
        "success": True,
        "data": {
            "received": len(request.logs),
            "queued_for_analysis": len(anomalous_ids),
            "batch_id": batch_id,
        },
        "error": None,
    }


@router.post("/logs/webhook/{app_id}")
async def webhook_receiver(
    app_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook endpoint for receiving logs from external applications.

    Verifies HMAC-SHA256 signature using the app's webhook_secret,
    then processes logs identically to the ingest endpoint.
    """
    # Validate app
    try:
        app_uuid = uuid.UUID(app_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid app_id format")

    app = await db.get(MonitoredApp, app_uuid)
    if not app:
        raise HTTPException(status_code=404, detail=f"App {app_id} not found")

    # Read and verify body
    body = await request.body()

    if x_signature:
        expected_sig = hmac.new(
            app.webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(f"sha256={expected_sig}", x_signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Parse body
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    logs = payload.get("logs", [])
    if not logs:
        raise HTTPException(status_code=400, detail="No logs provided")

    batch_id = uuid.uuid4().hex[:16]
    anomalous_ids: list[str] = []

    for raw_log in logs:
        severity, is_anomaly = classify_log_severity(str(raw_log))

        log_entry = LogEntry(
            app_id=app_uuid,
            raw_log=str(raw_log),
            severity=severity,
            timestamp=datetime.now(timezone.utc),
            processed=False,
            batch_id=batch_id,
        )
        db.add(log_entry)
        await db.flush()

        if is_anomaly:
            anomalous_ids.append(str(log_entry.id))

    if anomalous_ids:
        background_tasks.add_task(
            process_logs_background,
            anomalous_ids,
            app_id,
        )

    logger.info(
        f"[webhook] app={app_id} received={len(logs)} "
        f"anomalous={len(anomalous_ids)} batch={batch_id}"
    )

    return {
        "success": True,
        "data": {
            "received": len(logs),
            "queued_for_analysis": len(anomalous_ids),
            "batch_id": batch_id,
        },
        "error": None,
    }


@router.get("/logs/{app_id}")
async def get_logs(
    app_id: str,
    severity: Optional[str] = None,
    processed: Optional[bool] = None,
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """
    Get paginated log history for an application.
    Supports filtering by severity and processed status.
    """
    try:
        app_uuid = uuid.UUID(app_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid app_id format")

    # Build query
    query = select(LogEntry).where(LogEntry.app_id == app_uuid)

    if severity:
        query = query.where(LogEntry.severity == severity)
    if processed is not None:
        query = query.where(LogEntry.processed == processed)

    # Count total
    count_query = select(func.count()).select_from(
        query.subquery()
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate
    query = (
        query
        .order_by(LogEntry.timestamp.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    entries = result.scalars().all()

    return {
        "success": True,
        "data": {
            "logs": [
                {
                    "id": str(e.id),
                    "app_id": str(e.app_id),
                    "raw_log": e.raw_log,
                    "severity": e.severity,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "processed": e.processed,
                    "batch_id": e.batch_id,
                }
                for e in entries
            ],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "pages": (total + page_size - 1) // page_size if page_size > 0 else 0,
            },
        },
        "error": None,
    }
