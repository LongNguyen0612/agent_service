from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ArtifactVersionDTO(BaseModel):
    """Response DTO for a single artifact version"""

    id: str
    version: int
    pipeline_run_id: str
    step_run_id: str
    created_at: datetime


class ArtifactComparisonResponseDTO(BaseModel):
    """Response DTO for artifact version comparison"""

    task_id: str
    artifact_type: str
    versions: List[ArtifactVersionDTO]


class ArtifactDTO(BaseModel):
    """Response DTO for a single artifact (UC-26)"""

    id: str
    artifact_type: str
    version: int
    status: str
    is_approved: bool
    created_at: datetime
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None


class ListArtifactsResponseDTO(BaseModel):
    """Response DTO for listing artifacts (UC-26)"""

    artifacts: List[ArtifactDTO]


class GetArtifactResponseDTO(BaseModel):
    """Response DTO for getting a single artifact with content (UC-27)"""

    id: str
    task_id: str
    artifact_type: str
    version: int
    status: str
    content: Optional[Dict[str, Any]] = None
    created_at: datetime
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None


class ApproveArtifactResponseDTO(BaseModel):
    """Response DTO for approving an artifact (UC-28)"""

    id: str
    status: str
    approved_at: datetime
    pipeline_run_id: Optional[str] = None
    pipeline_resumed: bool = False


class RejectArtifactRequestDTO(BaseModel):
    """Request DTO for rejecting an artifact (UC-29)"""

    feedback: Optional[str] = None
    regenerate: bool = True


class RejectArtifactResponseDTO(BaseModel):
    """Response DTO for rejecting an artifact (UC-29)"""

    id: str
    status: str
    rejected_at: datetime
    new_pipeline_run_id: Optional[str] = None


class ArchiveArtifactResponseDTO(BaseModel):
    """Response DTO for archiving an artifact (UC-32)"""

    id: str
    status: str
