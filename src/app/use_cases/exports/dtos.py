"""Export DTOs - UC-30

Data Transfer Objects for project export functionality.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class CreateExportJobResponseDTO(BaseModel):
    """Response DTO for creating an export job"""
    export_job_id: str
    status: str


class ExportJobStatusDTO(BaseModel):
    """Response DTO for export job status"""
    export_job_id: str
    project_id: str
    status: str
    download_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
