"""Pipeline Run Entity - AC-2.1.1

Tracks the execution state of a multi-step AI pipeline including pause/resume logic.
"""
from datetime import datetime
from typing import Optional, List
from sqlmodel import Field, Column
from sqlalchemy import JSON as SQLJSON, String
from src.domain.base import BaseModel, generate_uuid
from src.domain.enums import PipelineStatus, PauseReason


class PipelineRun(BaseModel, table=True):
    """
    PipelineRun Entity - AC-2.1.1

    Tracks pipeline execution with support for pausing/resuming based on rejection
    or insufficient credits.
    """
    __tablename__ = "pipeline_runs"

    # Primary identifiers
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    task_id: str = Field(foreign_key="tasks.id", index=True, nullable=False)
    tenant_id: str = Field(index=True, nullable=False)

    # Status tracking
    status: PipelineStatus = Field(default=PipelineStatus.running, nullable=False, index=True)
    pause_reasons: List[str] = Field(
        default_factory=list,
        sa_column=Column(SQLJSON, default=[])
    )
    current_step: int = Field(default=1, nullable=False)

    # Error tracking
    error_message: Optional[str] = Field(default=None, sa_column=Column(String(1000)))

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    started_at: Optional[datetime] = Field(default=None)
    paused_at: Optional[datetime] = Field(default=None)
    pause_expires_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    class Config:
        use_enum_values = True

    # Business logic methods - AC-2.1.1

    def can_resume(self) -> bool:
        """Check if pipeline can be resumed (no blocking pause reasons)"""
        return len(self.pause_reasons) == 0

    def add_pause_reason(self, reason: PauseReason) -> None:
        """Add a pause reason if not already present"""
        if reason.value not in self.pause_reasons:
            self.pause_reasons.append(reason.value)
            self.updated_at = datetime.utcnow()

    def remove_pause_reason(self, reason: PauseReason) -> None:
        """Remove a pause reason if present"""
        if reason.value in self.pause_reasons:
            self.pause_reasons.remove(reason.value)
            self.updated_at = datetime.utcnow()

    def is_expired(self) -> bool:
        """Check if pause has expired"""
        if self.pause_expires_at is None:
            return False
        return datetime.utcnow() > self.pause_expires_at

    # Legacy methods for backward compatibility

    def mark_completed(self) -> None:
        """Mark pipeline run as completed"""
        self.status = PipelineStatus.completed
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def mark_failed(self, error_message: str = None) -> None:
        """Mark pipeline run as failed"""
        self.status = PipelineStatus.completed  # Use completed instead of failed
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
