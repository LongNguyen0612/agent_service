"""Retry Job Entity - AC-2.1.5

Operational entity for managing failed step retries with exponential backoff.
"""
from datetime import datetime
from typing import Optional
from sqlmodel import Field
from src.domain.base import BaseModel, generate_uuid
from src.domain.enums import RetryStatus


class RetryJob(BaseModel, table=True):
    """
    RetryJob Entity - AC-2.1.5

    Manages retry scheduling for failed pipeline steps with exponential backoff.
    Used by background workers to process retries at scheduled times.
    """
    __tablename__ = "retry_jobs"

    # Primary identifier
    id: str = Field(default_factory=generate_uuid, primary_key=True)

    # Foreign key to step run
    step_run_id: str = Field(
        foreign_key="pipeline_step_runs.id",
        index=True,
        nullable=False
    )

    # Retry information
    retry_attempt: int = Field(nullable=False)
    scheduled_at: datetime = Field(nullable=False, index=True)

    # Status tracking
    status: RetryStatus = Field(default=RetryStatus.pending, nullable=False, index=True)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    processed_at: Optional[datetime] = Field(default=None)

    class Config:
        use_enum_values = True

    def mark_processing(self) -> None:
        """Mark retry job as being processed"""
        self.status = RetryStatus.processing

    def mark_completed(self) -> None:
        """Mark retry job as completed"""
        self.status = RetryStatus.completed
        self.processed_at = datetime.utcnow()

    def mark_failed(self) -> None:
        """Mark retry job as failed"""
        self.status = RetryStatus.failed
        self.processed_at = datetime.utcnow()

    def is_ready(self) -> bool:
        """Check if retry job is ready to be processed"""
        return (
            self.status == RetryStatus.pending
            and self.scheduled_at <= datetime.utcnow()
        )
