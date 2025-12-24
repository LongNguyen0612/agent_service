"""Artifact Entity - AC-2.1.4

Tracks pipeline step outputs with approval workflow and supersession tracking.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import Field, Column
from sqlalchemy import JSON as SQLJSON
from src.domain.base import BaseModel, generate_uuid
from src.domain.enums import ArtifactType, ArtifactStatus


class Artifact(BaseModel, table=True):
    """
    Artifact Entity - AC-2.1.4

    Tracks outputs from pipeline steps (ANALYSIS_REPORT, USER_STORIES, CODE_FILES, TEST_SUITE)
    with draft/approved/rejected/superseded status tracking.
    """
    __tablename__ = "artifacts"

    # Primary identifier
    id: str = Field(default_factory=generate_uuid, primary_key=True)

    # Foreign keys
    task_id: str = Field(
        foreign_key="tasks.id",
        index=True,
        nullable=False
    )

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

    # Artifact metadata
    artifact_type: ArtifactType = Field(nullable=False, index=True)
    status: ArtifactStatus = Field(default=ArtifactStatus.draft, nullable=False, index=True)
    version: int = Field(default=1, nullable=False)

    # Artifact content (JSONB)
    content: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(SQLJSON))

    # Extra data for additional info like rejection feedback
    extra_data: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(SQLJSON))

    # Supersession tracking
    superseded_by: Optional[str] = Field(
        default=None,
        foreign_key="artifacts.id",
        nullable=True
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    approved_at: Optional[datetime] = Field(default=None)
    rejected_at: Optional[datetime] = Field(default=None)

    class Config:
        use_enum_values = True

    # Business logic methods

    def approve(self) -> None:
        """Mark artifact as approved"""
        self.status = ArtifactStatus.approved
        self.approved_at = datetime.utcnow()

    def reject(self, feedback: str = None) -> None:
        """Mark artifact as rejected with optional feedback"""
        self.status = ArtifactStatus.rejected
        self.rejected_at = datetime.utcnow()
        if feedback:
            if self.extra_data is None:
                self.extra_data = {}
            self.extra_data["rejection_feedback"] = feedback

    def supersede(self, new_artifact_id: str) -> None:
        """Mark this artifact as superseded by a newer version"""
        self.status = ArtifactStatus.superseded
        self.superseded_by = new_artifact_id
