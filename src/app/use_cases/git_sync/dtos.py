"""Git Sync DTOs - UC-31"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel


class SyncToGitRequestDTO(BaseModel):
    """Request DTO for syncing artifact to Git - UC-31"""
    repository_url: str
    branch: str = "main"
    commit_message: str


class SyncToGitResponseDTO(BaseModel):
    """Response DTO for sync job creation - UC-31"""
    sync_job_id: str
    status: str


class GitSyncStatusDTO(BaseModel):
    """Response DTO for Git sync job status - UC-31"""
    id: str
    artifact_id: str
    repository_url: str
    branch: str
    status: str
    commit_sha: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
