"""Dead Letter Event Entity - AC-2.5.3

Captures failed pipeline steps that have exhausted all retries.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import Field, Column
from sqlalchemy import JSON as SQLJSON
from src.domain.base import BaseModel, generate_uuid


class DeadLetterEvent(BaseModel, table=True):
    """
    DeadLetterEvent Entity - AC-2.5.3

    Records pipeline steps that have failed after all retries are exhausted.
    Requires manual intervention for resolution.
    """
    __tablename__ = "dead_letter_events"

    # Primary identifier
    id: str = Field(default_factory=generate_uuid, primary_key=True)

    # Foreign keys
    pipeline_run_id: str = Field(
        foreign_key="pipeline_runs.id",
        index=True,
        nullable=False
    )
    step_run_id: str = Field(
        foreign_key="pipeline_step_runs.id",
        index=True,
        nullable=False
    )

    # Failure information
    failure_reason: str = Field(nullable=False)
    retry_count: int = Field(nullable=False)

    # Additional context (error details, stack trace, etc.)
    context: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(SQLJSON))

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    # Resolution tracking (for future admin panel)
    resolved: bool = Field(default=False, nullable=False)
    resolved_at: Optional[datetime] = Field(default=None)
    resolution_notes: Optional[str] = Field(default=None)

    def mark_resolved(self, notes: Optional[str] = None) -> None:
        """Mark dead letter event as resolved"""
        self.resolved = True
        self.resolved_at = datetime.utcnow()
        if notes:
            self.resolution_notes = notes
