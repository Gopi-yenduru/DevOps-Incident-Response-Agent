"""
MonitoredApp model — represents an application being monitored by the agent system.
Each app has a unique webhook secret for secure log ingestion.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class MonitoredApp(Base):
    """
    A monitored application target.

    Attributes:
        id: Unique identifier (UUID).
        name: Human-readable app name (e.g., "auth-service").
        description: Optional description of the app's purpose.
        webhook_secret: HMAC-SHA256 secret for webhook signature verification.
        created_at: Timestamp when the app was registered.
    """

    __tablename__ = "monitored_apps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    webhook_secret: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=lambda: uuid.uuid4().hex,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ──────────────────────────────────────────────────
    log_entries = relationship(
        "LogEntry",
        back_populates="app",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    incidents = relationship(
        "Incident",
        back_populates="app",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<MonitoredApp name={self.name!r} id={self.id}>"
