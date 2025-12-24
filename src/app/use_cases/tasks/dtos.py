from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
from src.domain.enums import TaskStatus


class CreateTaskRequest(BaseModel):
    """Request DTO for creating a task (API layer - from user input)"""

    title: str
    input_spec: Dict[str, Any]


class CreateTaskCommand(BaseModel):
    """Command DTO for creating a task (Use case layer)"""

    project_id: str
    title: str
    input_spec: Dict[str, Any]
    tenant_id: str
    user_id: str  # For audit logging


class CreateTaskResponse(BaseModel):
    """Response DTO for CreateTaskUseCase"""

    id: str
    project_id: str
    tenant_id: str
    title: str
    input_spec: Dict[str, Any]
    status: TaskStatus
    created_at: datetime


class ListProjectTasksCommand(BaseModel):
    """Command DTO for listing project tasks (Use case layer)"""

    project_id: str
    tenant_id: str
    status: Optional[TaskStatus] = None  # Optional filter


class TaskSummaryDTO(BaseModel):
    """Summary DTO for a single task in a list"""

    id: str
    title: str
    status: TaskStatus
    created_at: datetime


class ListProjectTasksResponse(BaseModel):
    """Response DTO for ListProjectTasksUseCase"""

    tasks: List[TaskSummaryDTO]


class QueueTaskResponse(BaseModel):
    """Response DTO for QueueTaskUseCase"""

    id: str
    status: TaskStatus
    message: str


class GetTaskResponse(BaseModel):
    """Response DTO for GetTaskByIdUseCase"""

    id: str
    project_id: str
    project_name: str
    tenant_id: str
    title: str
    input_spec: Dict[str, Any]
    status: TaskStatus
    created_at: datetime
