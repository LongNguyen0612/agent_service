from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from src.domain.enums import ProjectStatus


class CreateProjectRequest(BaseModel):
    """Request DTO for creating a project (API layer - from user input)"""

    name: str
    description: Optional[str] = None


class CreateProjectCommand(BaseModel):
    """Command DTO for creating a project (Use case layer - includes auth context)"""

    name: str
    description: Optional[str] = None
    tenant_id: str
    user_id: str  # For audit logging


class CreateProjectResponse(BaseModel):
    """Response DTO for CreateProjectUseCase"""

    id: str
    tenant_id: str
    name: str
    description: Optional[str]
    status: ProjectStatus
    created_at: datetime


class UpdateProjectRequest(BaseModel):
    """Request DTO for updating a project (API layer)"""

    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None


class UpdateProjectCommand(BaseModel):
    """Command DTO for updating a project (Use case layer)"""

    project_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[ProjectStatus] = None
    tenant_id: str
    user_id: str  # For audit logging


class UpdateProjectResponse(BaseModel):
    """Response DTO for UpdateProjectUseCase"""

    id: str
    tenant_id: str
    name: str
    description: Optional[str]
    status: ProjectStatus
    created_at: datetime


class ProjectDTO(BaseModel):
    """Project DTO for listing and single project retrieval"""

    id: str
    tenant_id: str
    name: str
    description: Optional[str]
    status: ProjectStatus
    created_at: datetime
    updated_at: datetime
    task_count: int = 0  # Number of tasks in this project


class GetProjectsResponse(BaseModel):
    """Response DTO for GetProjectsUseCase"""

    projects: list[ProjectDTO]


class ExportProjectRequestDTO(BaseModel):
    """Request DTO for exporting a project (UC-30)"""

    project_id: str
    tenant_id: str


class ExportProjectResponseDTO(BaseModel):
    """Response DTO for export job creation (UC-30)"""

    export_job_id: str
    status: str


class ExportStatusResponseDTO(BaseModel):
    """Response DTO for export job status (UC-30)"""

    status: str
    download_url: Optional[str] = None
    expires_at: Optional[datetime] = None
