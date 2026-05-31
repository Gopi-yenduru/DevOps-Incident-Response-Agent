"""
Incident and LogEntry models — core data models for the agent pipeline.

LogEntry: Raw log lines ingested from monitored applications.
Incident: Full incident record with all agent outputs, confidence scores,
          correlation data, and resolution tracking.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    String,
    Text,
    Float,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


# ── Enums ──────────────────────────────────────────────────────────────
import enum


class SeverityLevel(str, enum.Enum):
    """Log/incident severity classification."""
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    NORMAL = "normal"


class IncidentStatus(str, enum.Enum):
    """Incident lifecycle status."""
    OPEN = "open"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class FixAccuracyRating(str, enum.Enum):
    """Human feedback on agent fix quality."""
    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNRATED = "unrated"


class BlastRadius(str, enum.Enum):
    """Scope of incident impact."""
    ISOLATED = "isolated"
    PARTIAL = "partial"
    SYSTEM_WIDE = "system-wide"


class FixComplexity(str, enum.Enum):
    """Complexity rating for the suggested fix."""
    TRIVIAL = "trivial"
    MODERATE = "moderate"
    COMPLEX = "complex"


# ── LogEntry Model ─────────────────────────────────────────────────────
class LogEntry(Base):
    """
    A single log line ingested from a monitored application.

    Logs are stored raw and marked as processed once they've been
    sent through the agent pipeline. Batch IDs group logs that were
    ingested together for traceability.
    """

    __tablename__ = "log_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    app_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("monitored_apps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    raw_log: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=True,
        default="normal",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    processed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    batch_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    # ── Relationships ──────────────────────────────────────────────
    app = relationship(
        "MonitoredApp",
        back_populates="log_entries",
    )

    # ── Indexes ────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_log_entries_app_processed", "app_id", "processed"),
        Index("ix_log_entries_timestamp", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<LogEntry app={self.app_id} severity={self.severity} processed={self.processed}>"


# ── Incident Model ─────────────────────────────────────────────────────
class Incident(Base):
    """
    A fully-diagnosed incident produced by the 5-agent LangGraph pipeline.

    Contains outputs from every agent stage: anomaly detection, correlation,
    root cause analysis, fix suggestion, and response orchestration.
    All confidence scores are normalized to [0.0, 1.0].
    """

    __tablename__ = "incidents"

    # ── Identity ───────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    app_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("monitored_apps.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Anomaly Detection Output ───────────────────────────────────
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        SAEnum(SeverityLevel, name="severity_level", create_constraint=True),
        nullable=False,
        default=SeverityLevel.ERROR,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        SAEnum(IncidentStatus, name="incident_status", create_constraint=True),
        nullable=False,
        default=IncidentStatus.OPEN,
        index=True,
    )
    error_type: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    affected_service: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    frequency: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        default="one-time",
    )

    # ── Root Cause Analysis Output ─────────────────────────────────
    root_cause: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    causal_chain: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
    )
    blast_radius: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    historical_pattern: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # ── Fix Suggestion Output ──────────────────────────────────────
    fix_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    fix_steps: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
    )
    fix_code_snippet: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    fix_complexity: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    estimated_time: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    preventive_measure: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ── Confidence Scores ──────────────────────────────────────────
    anomaly_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=0.0,
    )
    rootcause_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=0.0,
    )
    fix_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        default=0.0,
    )

    # ── Correlation Data ───────────────────────────────────────────
    correlated_incident_ids: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
    )
    correlation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ── Response Orchestration Output ──────────────────────────────
    github_issue_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    github_pr_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )
    telegram_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # ── Human Feedback ─────────────────────────────────────────────
    fix_accuracy_rating: Mapped[str] = mapped_column(
        SAEnum(FixAccuracyRating, name="fix_accuracy_rating", create_constraint=True),
        nullable=False,
        default=FixAccuracyRating.UNRATED,
    )

    # ── Resolution Tracking ────────────────────────────────────────
    mttr_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # ── Raw Agent Outputs (for timeline/debugging) ─────────────────
    raw_anomaly_output: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    raw_correlation_output: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    raw_rootcause_output: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    raw_fix_output: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )
    raw_response_output: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
    )

    # ── Source Log Reference ───────────────────────────────────────
    source_log_ids: Mapped[Optional[list]] = mapped_column(
        JSONB,
        nullable=True,
        default=list,
    )

    # ── Relationships ──────────────────────────────────────────────
    app = relationship(
        "MonitoredApp",
        back_populates="incidents",
    )

    # ── Indexes ────────────────────────────────────────────────────
    __table_args__ = (
        Index("ix_incidents_app_status", "app_id", "status"),
        Index("ix_incidents_severity_status", "severity", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<Incident id={self.id} severity={self.severity} "
            f"status={self.status} service={self.affected_service}>"
        )
