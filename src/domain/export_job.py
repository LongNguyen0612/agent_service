"""ExportJob Entity - UC-30

Tracks project export jobs for ZIP file generation.
"""
from datetime import datetime
from typing import Optional
from sqlmodel import Field
from src.domain.base import BaseModel, generate_uuid
from src.domain.enums import ExportJobStatus


class ExportJob(BaseModel, table=True):
    """
    ExportJob Entity - UC-30

    Tracks async export jobs that generate ZIP files of project artifacts.
    """
    __tablename__ = "export_jobs"

    id: str = Field(default_factory=generate_uuid, primary_key=True)

    # Foreign keys
    project_id: str = Field(foreign_key="projects.id", index=True, nullable=False)
    tenant_id: str = Field(index=True, nullable=False)

    # Job status
    status: ExportJobStatus = Field(default=ExportJobStatus.pending, nullable=False, index=True)

    # File storage
    file_path: Optional[str] = Field(default=None)
    download_url: Optional[str] = Field(default=None)
    expires_at: Optional[datetime] = Field(default=None)

    # Error tracking
    error_message: Optional[str] = Field(default=None)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    class Config:
        use_enum_values = True

    # Business logic methods

    def start_processing(self) -> None:
        """Mark job as processing"""
        self.status = ExportJobStatus.processing
        self.started_at = datetime.utcnow()

    def complete(self, file_path: str, download_url: str, expires_at: datetime) -> None:
        """Mark job as completed with download URL"""
        self.status = ExportJobStatus.completed
        self.file_path = file_path
        self.download_url = download_url
        self.expires_at = expires_at
        self.completed_at = datetime.utcnow()

    def fail(self, error_message: str) -> None:
        """Mark job as failed with error message"""
        self.status = ExportJobStatus.failed
        self.error_message = error_message
        self.completed_at = datetime.utcnow()
