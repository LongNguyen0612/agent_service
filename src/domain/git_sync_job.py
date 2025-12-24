"""GitSyncJob Entity - UC-31

Tracks Git sync jobs for pushing artifacts to external repositories.
"""
from datetime import datetime
from typing import Optional
from sqlmodel import Field
from src.domain.base import BaseModel, generate_uuid
from src.domain.enums import GitSyncJobStatus


class GitSyncJob(BaseModel, table=True):
    """
    GitSyncJob Entity - UC-31

    Tracks async jobs that sync approved artifacts to Git repositories.
    """
    __tablename__ = "git_sync_jobs"

    id: str = Field(default_factory=generate_uuid, primary_key=True)

    # Foreign keys
    artifact_id: str = Field(foreign_key="artifacts.id", index=True, nullable=False)
    tenant_id: str = Field(index=True, nullable=False)

    # Git configuration
    repository_url: str = Field(nullable=False)
    branch: str = Field(default="main", nullable=False)
    commit_message: str = Field(nullable=False)

    # Job status
    status: GitSyncJobStatus = Field(
        default=GitSyncJobStatus.pending, nullable=False, index=True
    )

    # Result tracking
    commit_sha: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)

    # Retry tracking
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    class Config:
        use_enum_values = True

    # Business logic methods

    def start_processing(self) -> None:
        """Mark job as processing"""
        self.status = GitSyncJobStatus.processing
        self.started_at = datetime.utcnow()

    def complete(self, commit_sha: str) -> None:
        """Mark job as completed with commit SHA"""
        self.status = GitSyncJobStatus.completed
        self.commit_sha = commit_sha
        self.completed_at = datetime.utcnow()

    def fail(self, error_message: str) -> None:
        """Mark job as failed with error message"""
        self.status = GitSyncJobStatus.failed
        self.error_message = error_message
        self.completed_at = datetime.utcnow()

    def can_retry(self) -> bool:
        """Check if job can be retried"""
        return self.retry_count < self.max_retries

    def increment_retry(self) -> None:
        """Increment retry count and reset for next attempt"""
        self.retry_count += 1
        self.status = GitSyncJobStatus.pending
        self.started_at = None
        self.completed_at = None
        self.error_message = None
