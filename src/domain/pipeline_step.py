"""Pipeline Step Run Entity - AC-2.1.2

Tracks individual step execution within a pipeline with retry logic.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import Field, Column
from sqlalchemy import JSON as SQLJSON
from src.domain.base import BaseModel, generate_uuid
from src.domain.enums import StepStatus, StepType


class PipelineStepRun(BaseModel, table=True):
    """
    PipelineStepRun Entity - AC-2.1.2

    Tracks individual step execution (ANALYSIS, USER_STORIES, CODE_SKELETON, TEST_CASES)
    with support for retries and immutable input snapshots.
    """
    __tablename__ = "pipeline_step_runs"

    # Primary identifiers
    id: str = Field(default_factory=generate_uuid, primary_key=True)
    pipeline_run_id: str = Field(foreign_key="pipeline_runs.id", index=True, nullable=False)

    # Step information
    step_number: int = Field(nullable=False, index=True)
    step_name: str = Field(nullable=False, max_length=255)
    step_type: StepType = Field(nullable=False)

    # Status and retry tracking
    status: StepStatus = Field(default=StepStatus.pending, nullable=False)
    retry_count: int = Field(default=0, nullable=False)
    max_retries: int = Field(default=3, nullable=False)

    # Input snapshot (immutable)
    input_snapshot: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(SQLJSON))

    # Output and error tracking
    output: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(SQLJSON))
    error_message: Optional[str] = Field(default=None, max_length=1000)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    class Config:
        use_enum_values = True

    # Business logic methods - AC-2.1.2

    def is_retryable(self) -> bool:
        """Check if step can be retried"""
        return self.retry_count < self.max_retries and self.status == StepStatus.failed

    def increment_retry(self) -> None:
        """Increment retry count"""
        self.retry_count += 1

    # Legacy methods for backward compatibility

    def mark_running(self) -> None:
        """Mark step as running"""
        self.status = StepStatus.running
        self.started_at = datetime.utcnow()

    def mark_completed(self, output: Optional[Dict[str, Any]] = None) -> None:
        """Mark step as completed with optional output"""
        self.status = StepStatus.completed
        self.completed_at = datetime.utcnow()
        if output is not None:
            self.output = output

    def mark_failed(self, error_message: str = None) -> None:
        """Mark step as failed with optional error message"""
        self.status = StepStatus.failed
        self.completed_at = datetime.utcnow()
        if error_message is not None:
            self.error_message = error_message


# Backward compatibility alias
PipelineStep = PipelineStepRun
