"""
Background log monitoring service.

Runs a polling loop that:
1. Fetches unprocessed log entries from the database
2. Batches them by app_id
3. Sends anomalous logs through the 5-agent pipeline
4. Marks processed logs

Also handles auto-resolution: incidents with no recurrence
within AUTO_RESOLVE_MINUTES are automatically resolved.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, and_, func

from config import get_settings
from database import get_db_context
from models.incident import LogEntry, Incident, IncidentStatus
from models.app_target import MonitoredApp

logger = logging.getLogger("devops_agent.service.log_monitor")

settings = get_settings()

# Track the background task for clean shutdown
_monitor_task: asyncio.Task | None = None


async def start_log_monitor() -> None:
    """Start the background log monitoring loop."""
    global _monitor_task
    if _monitor_task and not _monitor_task.done():
        logger.warning("[log_monitor] Already running, skipping start")
        return

    _monitor_task = asyncio.create_task(_monitor_loop())
    logger.info(
        f"[log_monitor] Started — polling every {settings.LOG_POLL_INTERVAL}s"
    )


async def stop_log_monitor() -> None:
    """Stop the background monitoring loop gracefully."""
    global _monitor_task
    if _monitor_task and not _monitor_task.done():
        _monitor_task.cancel()
        try:
            await _monitor_task
        except asyncio.CancelledError:
            pass
    _monitor_task = None
    logger.info("[log_monitor] Stopped")


async def _monitor_loop() -> None:
    """
    Main monitoring loop.

    Runs continuously, polling for unprocessed logs and checking
    for auto-resolution candidates.
    """
    while True:
        try:
            await _process_pending_logs()
            await _check_auto_resolution()
        except asyncio.CancelledError:
            logger.info("[log_monitor] Loop cancelled")
            break
        except Exception as e:
            logger.error(f"[log_monitor] Loop error: {e}", exc_info=True)

        await asyncio.sleep(settings.LOG_POLL_INTERVAL)


async def _process_pending_logs() -> None:
    """
    Fetch unprocessed logs, batch by app, and send anomalous
    ones through the agent pipeline.
    """
    try:
        async with get_db_context() as db:
            # Fetch unprocessed logs
            result = await db.execute(
                select(LogEntry)
                .where(LogEntry.processed == False)  # noqa: E712
                .order_by(LogEntry.timestamp.asc())
                .limit(100)
            )
            logs = result.scalars().all()

            if not logs:
                return

            logger.info(f"[log_monitor] Found {len(logs)} unprocessed logs")

            # Group by app_id
            batches: dict[str, list[LogEntry]] = {}
            for log in logs:
                app_key = str(log.app_id)
                batches.setdefault(app_key, []).append(log)

        # Process each batch
        for app_id, log_batch in batches.items():
            # Filter for anomalous logs
            anomalous_logs = [
                log for log in log_batch
                if log.severity in ("critical", "error", "warning")
            ]

            if anomalous_logs:
                # Combine log text for analysis
                combined_text = "\n".join(log.raw_log for log in anomalous_logs)
                log_ids = [str(log.id) for log in anomalous_logs]

                logger.info(
                    f"[log_monitor] Processing {len(anomalous_logs)} anomalous logs "
                    f"for app {app_id}"
                )

                try:
                    from agents.graph import run_incident_pipeline
                    await run_incident_pipeline(
                        log_text=combined_text,
                        app_id=app_id,
                        log_entry_ids=log_ids,
                    )
                except Exception as e:
                    logger.error(
                        f"[log_monitor] Pipeline failed for app {app_id}: {e}",
                        exc_info=True,
                    )

            # Mark all logs in this batch as processed (including non-anomalous)
            async with get_db_context() as db:
                for log in log_batch:
                    entry = await db.get(LogEntry, log.id)
                    if entry:
                        entry.processed = True

    except Exception as e:
        logger.error(f"[log_monitor] Processing failed: {e}", exc_info=True)


async def _check_auto_resolution() -> None:
    """
    Check for incidents that can be auto-resolved.

    An incident is auto-resolved if:
    1. It's currently open
    2. No new incidents with the same error_type and affected_service
       have been created within AUTO_RESOLVE_MINUTES
    """
    try:
        async with get_db_context() as db:
            cutoff = datetime.now(timezone.utc) - timedelta(
                minutes=settings.AUTO_RESOLVE_MINUTES
            )

            # Find open incidents older than the auto-resolve window
            result = await db.execute(
                select(Incident)
                .where(
                    and_(
                        Incident.status == IncidentStatus.OPEN,
                        Incident.created_at <= cutoff,
                    )
                )
                .limit(50)
            )
            old_incidents = result.scalars().all()

            for incident in old_incidents:
                # Check if there are newer incidents with the same signature
                recent_result = await db.execute(
                    select(func.count())
                    .where(
                        and_(
                            Incident.error_type == incident.error_type,
                            Incident.affected_service == incident.affected_service,
                            Incident.created_at > cutoff,
                            Incident.id != incident.id,
                        )
                    )
                )
                recent_count = recent_result.scalar() or 0

                if recent_count == 0:
                    # No recurrence — auto-resolve
                    now = datetime.now(timezone.utc)
                    incident.status = IncidentStatus.RESOLVED
                    incident.resolved_at = now

                    created = incident.created_at
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    incident.mttr_seconds = int((now - created).total_seconds())

                    logger.info(
                        f"[log_monitor] Auto-resolved incident {incident.id} "
                        f"(no recurrence in {settings.AUTO_RESOLVE_MINUTES}min, "
                        f"MTTR={incident.mttr_seconds}s)"
                    )

    except Exception as e:
        logger.error(f"[log_monitor] Auto-resolution check failed: {e}", exc_info=True)
