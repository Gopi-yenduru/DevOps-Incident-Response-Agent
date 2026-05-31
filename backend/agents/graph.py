"""
LangGraph Agent Pipeline — Sequential 5-Agent Incident Response Graph

Pipeline flow:
  START → anomaly_detector → incident_correlator → root_cause_analyzer
        → fix_suggestion → response_orchestrator → END

Each node:
  - Wrapped in try/except with safe defaults
  - Logs execution with timing and confidence
  - Stores raw agent output for timeline display
  - Passes accumulated state to next agent

The graph processes raw log text through the full diagnostic pipeline
and persists a complete Incident record to the database.
"""

import json
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, TypedDict, Optional

from sqlalchemy import select, and_

from config import get_settings
from database import get_db_context
from models.incident import Incident, IncidentStatus, LogEntry
from models.app_target import MonitoredApp

from agents.anomaly_detector import detect_anomaly
from agents.incident_correlator import correlate_incident
from agents.root_cause_analyzer import analyze_root_cause
from agents.fix_suggestion import suggest_fix
from agents.response_orchestrator import orchestrate_response

logger = logging.getLogger("devops_agent.graph")

settings = get_settings()


# ── Pipeline State ─────────────────────────────────────────────────────
class IncidentState(TypedDict, total=False):
    """
    State object passed through the LangGraph pipeline.
    Accumulates outputs from each agent node.
    """
    # Input
    log_text: str
    app_id: str
    log_entry_ids: list[str]
    app_name: str

    # Agent 1: Anomaly Detector
    anomaly_report: dict[str, Any]

    # Agent 2: Incident Correlator
    correlation_data: dict[str, Any]
    recent_incidents: list[dict[str, Any]]

    # Agent 3: Root Cause Analyzer
    root_cause_analysis: dict[str, Any]
    historical_incidents: list[dict[str, Any]]

    # Agent 4: Fix Suggestion
    fix_suggestion: dict[str, Any]

    # Agent 5: Response Orchestrator
    response_result: dict[str, Any]

    # Pipeline metadata
    incident_id: str
    pipeline_started_at: float
    pipeline_completed_at: float
    errors: list[str]


# ── Node Functions ─────────────────────────────────────────────────────

async def node_anomaly_detector(state: IncidentState) -> IncidentState:
    """Node 1: Detect anomalies in raw log text."""
    start = time.time()
    try:
        result = await detect_anomaly(state["log_text"])
        state["anomaly_report"] = result
        logger.info(
            f"[pipeline] anomaly_detector completed in {time.time()-start:.2f}s | "
            f"is_anomaly={result.get('is_anomaly')} confidence={result.get('confidence')}"
        )
    except Exception as e:
        logger.error(f"[pipeline] anomaly_detector failed: {e}", exc_info=True)
        state["anomaly_report"] = {
            "is_anomaly": True,
            "severity": "error",
            "error_type": "unknown",
            "affected_service": "unknown",
            "error_message": str(e),
            "frequency": "one-time",
            "confidence": 0.0,
        }
        state.setdefault("errors", []).append(f"anomaly_detector: {str(e)}")
    return state


async def node_incident_correlator(state: IncidentState) -> IncidentState:
    """Node 2: Find correlated incidents from the database."""
    start = time.time()
    try:
        # Fetch recent open incidents from DB for correlation
        recent_incidents = await _fetch_recent_incidents(
            state.get("app_id", ""),
            settings.CORRELATION_WINDOW_MINUTES,
        )
        state["recent_incidents"] = recent_incidents

        result = await correlate_incident(
            state.get("anomaly_report", {}),
            recent_incidents,
        )
        state["correlation_data"] = result
        logger.info(
            f"[pipeline] incident_correlator completed in {time.time()-start:.2f}s | "
            f"is_correlated={result.get('is_correlated')} "
            f"related={len(result.get('correlated_incident_ids', []))} "
            f"confidence={result.get('confidence')}"
        )
    except Exception as e:
        logger.error(f"[pipeline] incident_correlator failed: {e}", exc_info=True)
        state["correlation_data"] = {
            "is_correlated": False,
            "correlated_incident_ids": [],
            "correlation_reason": f"Correlation failed: {str(e)}",
            "is_new_incident": True,
            "confidence": 0.0,
        }
        state.setdefault("errors", []).append(f"incident_correlator: {str(e)}")
    return state


async def node_root_cause_analyzer(state: IncidentState) -> IncidentState:
    """Node 3: Analyze root cause with historical context."""
    start = time.time()
    try:
        # Fetch historical incidents for pattern detection
        anomaly = state.get("anomaly_report", {})
        historical = await _fetch_historical_incidents(
            error_type=anomaly.get("error_type"),
            affected_service=anomaly.get("affected_service"),
        )
        state["historical_incidents"] = historical

        result = await analyze_root_cause(
            state.get("anomaly_report", {}),
            state.get("correlation_data", {}),
            historical,
        )
        state["root_cause_analysis"] = result
        logger.info(
            f"[pipeline] root_cause_analyzer completed in {time.time()-start:.2f}s | "
            f"blast_radius={result.get('blast_radius')} "
            f"confidence={result.get('confidence')}"
        )
    except Exception as e:
        logger.error(f"[pipeline] root_cause_analyzer failed: {e}", exc_info=True)
        state["root_cause_analysis"] = {
            "root_cause": f"Analysis failed: {str(e)}",
            "causal_chain": ["Error detected", "Analysis failed"],
            "blast_radius": "isolated",
            "historical_pattern": "first-occurrence",
            "confidence": 0.0,
        }
        state.setdefault("errors", []).append(f"root_cause_analyzer: {str(e)}")
    return state


async def node_fix_suggestion(state: IncidentState) -> IncidentState:
    """Node 4: Generate fix recommendations."""
    start = time.time()
    try:
        result = await suggest_fix(
            state.get("anomaly_report", {}),
            state.get("root_cause_analysis", {}),
        )
        state["fix_suggestion"] = result
        logger.info(
            f"[pipeline] fix_suggestion completed in {time.time()-start:.2f}s | "
            f"complexity={result.get('complexity')} "
            f"has_code={result.get('code_snippet') is not None} "
            f"confidence={result.get('confidence')}"
        )
    except Exception as e:
        logger.error(f"[pipeline] fix_suggestion failed: {e}", exc_info=True)
        state["fix_suggestion"] = {
            "fix_summary": f"Fix generation failed: {str(e)}",
            "fix_steps": ["Investigate manually"],
            "code_snippet": None,
            "complexity": "complex",
            "estimated_time": "unknown",
            "preventive_measure": "Add monitoring for this error type",
            "confidence": 0.0,
        }
        state.setdefault("errors", []).append(f"fix_suggestion: {str(e)}")
    return state


async def node_response_orchestrator(state: IncidentState) -> IncidentState:
    """Node 5: Execute automated response actions."""
    start = time.time()
    try:
        anomaly = state.get("anomaly_report", {})
        rca = state.get("root_cause_analysis", {})
        fix = state.get("fix_suggestion", {})

        # Build complete incident data for response actions
        incident_data = {
            "incident_id": state.get("incident_id", ""),
            "app_name": state.get("app_name", "unknown-app"),
            "severity": anomaly.get("severity", "error"),
            "error_type": anomaly.get("error_type", "unknown"),
            "affected_service": anomaly.get("affected_service", "unknown"),
            "error_message": anomaly.get("error_message", ""),
            "root_cause": rca.get("root_cause", ""),
            "causal_chain": rca.get("causal_chain", []),
            "blast_radius": rca.get("blast_radius", "isolated"),
            "fix_summary": fix.get("fix_summary", ""),
            "fix_steps": fix.get("fix_steps", []),
            "fix_code_snippet": fix.get("code_snippet"),
            "fix_complexity": fix.get("complexity", "moderate"),
            "estimated_time": fix.get("estimated_time", "unknown"),
            "preventive_measure": fix.get("preventive_measure", ""),
            "anomaly_confidence": anomaly.get("confidence", 0.0),
            "rootcause_confidence": rca.get("confidence", 0.0),
            "fix_confidence": fix.get("confidence", 0.0),
        }

        result = await orchestrate_response(incident_data)
        state["response_result"] = result
        logger.info(
            f"[pipeline] response_orchestrator completed in {time.time()-start:.2f}s | "
            f"actions={result.get('actions_taken', [])}"
        )
    except Exception as e:
        logger.error(f"[pipeline] response_orchestrator failed: {e}", exc_info=True)
        state["response_result"] = {
            "github_issue_url": None,
            "github_pr_url": None,
            "telegram_sent": False,
            "actions_taken": [f"orchestration_failed: {str(e)}"],
        }
        state.setdefault("errors", []).append(f"response_orchestrator: {str(e)}")
    return state


# ── Pipeline Execution ─────────────────────────────────────────────────

async def run_incident_pipeline(
    log_text: str,
    app_id: str,
    log_entry_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Execute the full 5-agent incident pipeline.

    This is the main entry point called by log ingestion endpoints
    and the background monitoring loop.

    Pipeline: anomaly_detector → incident_correlator → root_cause_analyzer
              → fix_suggestion → response_orchestrator

    Args:
        log_text: Raw log line(s) to analyze.
        app_id: UUID of the monitored application.
        log_entry_ids: Optional list of source log entry IDs.

    Returns:
        Complete incident state dict with all agent outputs.
    """
    pipeline_start = time.time()
    incident_id = str(uuid.uuid4())

    # Fetch app name
    app_name = "unknown-app"
    try:
        async with get_db_context() as db:
            app = await db.get(MonitoredApp, uuid.UUID(app_id))
            if app:
                app_name = app.name
    except Exception:
        pass

    logger.info(
        f"[pipeline:start] incident={incident_id} app={app_name} "
        f"log_length={len(log_text)}"
    )

    # Initialize state
    state: IncidentState = {
        "log_text": log_text,
        "app_id": app_id,
        "log_entry_ids": log_entry_ids or [],
        "app_name": app_name,
        "incident_id": incident_id,
        "pipeline_started_at": pipeline_start,
        "errors": [],
    }

    # ── Execute sequential pipeline ────────────────────────────────
    # Node 1: Anomaly Detection
    state = await node_anomaly_detector(state)

    # Skip rest of pipeline if not an anomaly
    anomaly = state.get("anomaly_report", {})
    if not anomaly.get("is_anomaly", False):
        logger.info(
            f"[pipeline:skip] incident={incident_id} — not an anomaly "
            f"(confidence={anomaly.get('confidence', 0)})"
        )
        # Mark source logs as processed
        await _mark_logs_processed(log_entry_ids or [])
        state["pipeline_completed_at"] = time.time()
        return state

    # Node 2: Incident Correlation
    state = await node_incident_correlator(state)

    # Node 3: Root Cause Analysis
    state = await node_root_cause_analyzer(state)

    # Node 4: Fix Suggestion
    state = await node_fix_suggestion(state)

    # Node 5: Response Orchestration
    state = await node_response_orchestrator(state)

    state["pipeline_completed_at"] = time.time()

    # ── Persist incident to database ───────────────────────────────
    await _persist_incident(state)

    # ── Mark source logs as processed ──────────────────────────────
    await _mark_logs_processed(log_entry_ids or [])

    total_time = time.time() - pipeline_start
    logger.info(
        f"[pipeline:complete] incident={incident_id} "
        f"total_time={total_time:.2f}s "
        f"severity={anomaly.get('severity')} "
        f"errors={len(state.get('errors', []))}"
    )

    return state


# ── Database Helpers ───────────────────────────────────────────────────

async def _fetch_recent_incidents(
    app_id: str,
    window_minutes: int,
) -> list[dict[str, Any]]:
    """Fetch recent open incidents within the correlation window."""
    try:
        async with get_db_context() as db:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
            result = await db.execute(
                select(Incident)
                .where(
                    and_(
                        Incident.status == IncidentStatus.OPEN,
                        Incident.created_at >= cutoff,
                    )
                )
                .order_by(Incident.created_at.desc())
                .limit(20)
            )
            incidents = result.scalars().all()

            return [
                {
                    "id": str(inc.id),
                    "error_type": inc.error_type,
                    "affected_service": inc.affected_service,
                    "error_message": inc.error_message,
                    "severity": inc.severity.value if hasattr(inc.severity, 'value') else inc.severity,
                    "created_at": inc.created_at.isoformat() if inc.created_at else None,
                    "root_cause": inc.root_cause,
                }
                for inc in incidents
            ]
    except Exception as e:
        logger.error(f"[pipeline] Failed to fetch recent incidents: {e}")
        return []


async def _fetch_historical_incidents(
    error_type: str | None = None,
    affected_service: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Fetch historical incidents matching error type or service."""
    try:
        async with get_db_context() as db:
            from sqlalchemy import or_

            conditions = []
            if error_type and error_type != "unknown":
                conditions.append(Incident.error_type == error_type)
            if affected_service and affected_service != "unknown":
                conditions.append(Incident.affected_service == affected_service)

            if not conditions:
                return []

            result = await db.execute(
                select(Incident)
                .where(or_(*conditions))
                .order_by(Incident.created_at.desc())
                .limit(limit)
            )
            incidents = result.scalars().all()

            return [
                {
                    "id": str(inc.id),
                    "error_type": inc.error_type,
                    "affected_service": inc.affected_service,
                    "severity": inc.severity.value if hasattr(inc.severity, 'value') else inc.severity,
                    "root_cause": inc.root_cause,
                    "fix_summary": inc.fix_summary,
                    "created_at": inc.created_at.isoformat() if inc.created_at else None,
                    "status": inc.status.value if hasattr(inc.status, 'value') else inc.status,
                }
                for inc in incidents
            ]
    except Exception as e:
        logger.error(f"[pipeline] Failed to fetch historical incidents: {e}")
        return []


async def _persist_incident(state: IncidentState) -> None:
    """Persist the complete incident to the database."""
    try:
        anomaly = state.get("anomaly_report", {})
        correlation = state.get("correlation_data", {})
        rca = state.get("root_cause_analysis", {})
        fix = state.get("fix_suggestion", {})
        response = state.get("response_result", {})

        async with get_db_context() as db:
            incident = Incident(
                id=uuid.UUID(state["incident_id"]),
                app_id=uuid.UUID(state["app_id"]),
                # Anomaly detection
                title=f"[{anomaly.get('severity', 'error').upper()}] "
                      f"{anomaly.get('error_type', 'Unknown Error')} "
                      f"in {anomaly.get('affected_service', 'unknown')}",
                severity=anomaly.get("severity", "error"),
                status=IncidentStatus.OPEN,
                error_type=anomaly.get("error_type"),
                affected_service=anomaly.get("affected_service"),
                error_message=anomaly.get("error_message"),
                frequency=anomaly.get("frequency"),
                # Root cause
                root_cause=rca.get("root_cause"),
                causal_chain=rca.get("causal_chain", []),
                blast_radius=rca.get("blast_radius"),
                historical_pattern=rca.get("historical_pattern"),
                # Fix
                fix_summary=fix.get("fix_summary"),
                fix_steps=fix.get("fix_steps", []),
                fix_code_snippet=fix.get("code_snippet"),
                fix_complexity=fix.get("complexity"),
                estimated_time=fix.get("estimated_time"),
                preventive_measure=fix.get("preventive_measure"),
                # Confidence
                anomaly_confidence=anomaly.get("confidence", 0.0),
                rootcause_confidence=rca.get("confidence", 0.0),
                fix_confidence=fix.get("confidence", 0.0),
                # Correlation
                correlated_incident_ids=correlation.get("correlated_incident_ids", []),
                correlation_reason=correlation.get("correlation_reason"),
                # Response
                github_issue_url=response.get("github_issue_url"),
                github_pr_url=response.get("github_pr_url"),
                telegram_sent=response.get("telegram_sent", False),
                # Raw agent outputs (for timeline display)
                raw_anomaly_output=anomaly,
                raw_correlation_output=correlation,
                raw_rootcause_output=rca,
                raw_fix_output=fix,
                raw_response_output=response,
                # Source logs
                source_log_ids=state.get("log_entry_ids", []),
            )
            db.add(incident)

        logger.info(f"[pipeline] Incident {state['incident_id']} persisted to database")

    except Exception as e:
        logger.error(
            f"[pipeline] Failed to persist incident {state.get('incident_id')}: {e}",
            exc_info=True,
        )


async def _mark_logs_processed(log_entry_ids: list[str]) -> None:
    """Mark source log entries as processed."""
    if not log_entry_ids:
        return

    try:
        async with get_db_context() as db:
            for lid in log_entry_ids:
                try:
                    entry = await db.get(LogEntry, uuid.UUID(lid))
                    if entry:
                        entry.processed = True
                except (ValueError, Exception):
                    continue
    except Exception as e:
        logger.error(f"[pipeline] Failed to mark logs processed: {e}")
