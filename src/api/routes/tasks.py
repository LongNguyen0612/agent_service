from typing import Optional
from fastapi import APIRouter, Depends, Query, BackgroundTasks, status
from src.api.error import ClientError
from src.app.services.unit_of_work import UnitOfWork
from src.app.services.audit_service import AuditService
from src.app.services.input_spec_validator import InputSpecValidator
from src.depends import get_unit_of_work, get_audit_service, get_input_spec_validator, get_current_user
from src.app.use_cases.tasks import (
    CreateTaskUseCase,
    CreateTaskRequest,
    CreateTaskCommand,
    CreateTaskResponse,
    ListProjectTasksUseCase,
    ListProjectTasksCommand,
    ListProjectTasksResponse,
    GetTaskByIdUseCase,
    GetTaskResponse,
)
from src.app.use_cases.tasks.queue_task_use_case import QueueTaskUseCase, QueueTaskResponse
from src.app.use_cases.pipelines import (
    GetPipelineTimelineUseCase,
    PipelineTimelineResponseDTO,
)
from src.app.use_cases.artifacts import (
    CompareArtifactsUseCase,
    ArtifactComparisonResponseDTO,
    ListArtifactsUseCase,
    ListArtifactsResponseDTO,
)
from src.domain.enums import TaskStatus

router = APIRouter()


@router.post(
    "/projects/{project_id}/tasks",
    response_model=CreateTaskResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_task(
    project_id: str,
    request: CreateTaskRequest,
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    audit_service: AuditService = Depends(get_audit_service),
    input_spec_validator: InputSpecValidator = Depends(get_input_spec_validator),
):
    """Create a new task for a project (requires authentication)"""
    # Convert request DTO to command DTO, adding project_id from path
    # Use tenant_id and user_id from JWT for security
    command = CreateTaskCommand(
        project_id=project_id,
        title=request.title,
        input_spec=request.input_spec,
        tenant_id=current_user["tenant_id"],
        user_id=current_user["user_id"],
    )

    use_case = CreateTaskUseCase(uow, audit_service, input_spec_validator)
    result = await use_case.execute(command)

    if result.is_err():
        # Return appropriate status code based on error
        if result.error.code == "PROJECT_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        elif result.error.code == "PROJECT_NOT_ACTIVE":
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    return result.value


@router.get(
    "/projects/{project_id}/tasks",
    response_model=ListProjectTasksResponse,
    status_code=status.HTTP_200_OK,
)
async def list_project_tasks(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    status_filter: Optional[TaskStatus] = Query(
        None, alias="status", description="Filter by task status"
    ),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """List all tasks in a project with optional status filtering (requires authentication)"""
    # Use tenant_id from JWT for security
    command = ListProjectTasksCommand(
        project_id=project_id,
        tenant_id=current_user["tenant_id"],
        status=status_filter,
    )

    use_case = ListProjectTasksUseCase(uow)
    result = await use_case.execute(command)

    # This use case doesn't return errors in normal operation
    # It returns empty list for non-existent projects
    return result.value


@router.get(
    "/tasks/{task_id}",
    response_model=GetTaskResponse,
    status_code=status.HTTP_200_OK,
)
async def get_task_by_id(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get a single task by ID (requires authentication)"""
    # Use tenant_id from JWT for security
    tenant_id = current_user["tenant_id"]

    use_case = GetTaskByIdUseCase(uow)
    result = await use_case.execute(task_id, tenant_id)

    if result.is_err():
        if result.error.code == "TASK_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        elif result.error.code == "INSUFFICIENT_PERMISSIONS":
            raise ClientError(result.error, status_code=status.HTTP_403_FORBIDDEN)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    return result.value


@router.post(
    "/tasks/{task_id}/queue",
    response_model=QueueTaskResponse,
    status_code=status.HTTP_200_OK,
)
async def queue_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    audit_service: AuditService = Depends(get_audit_service),
):
    """
    Queue a task for pipeline execution (draft → queued → running)
    Requires authentication.

    The pipeline execution happens asynchronously in the background.
    The API returns immediately with the queued task status.
    """
    # Use tenant_id from JWT for security
    tenant_id = current_user["tenant_id"]

    use_case = QueueTaskUseCase(uow, audit_service)
    result = await use_case.execute(task_id, tenant_id)

    if result.is_err():
        if result.error.code == "TASK_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    # Trigger pipeline execution in background
    background_tasks.add_task(use_case.execute_pipeline_in_background, task_id, tenant_id)

    return result.value


@router.get(
    "/tasks/{task_id}/pipeline",
    response_model=PipelineTimelineResponseDTO,
    status_code=status.HTTP_200_OK,
)
async def get_pipeline_timeline(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    run_id: Optional[str] = Query(
        None, description="Specific pipeline run ID (defaults to most recent)"
    ),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Get pipeline timeline for a task showing all steps with their status.
    Requires authentication.

    Returns the most recent pipeline run by default, or a specific run if run_id is provided.
    """
    # Use tenant_id from JWT for security
    use_case = GetPipelineTimelineUseCase(uow=uow, tenant_id=current_user["tenant_id"])
    result = await use_case.execute(task_id, run_id)

    if result.is_err():
        if result.error.code in ["TASK_NOT_FOUND", "PIPELINE_RUN_NOT_FOUND", "NO_PIPELINE_RUN"]:
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        elif result.error.code == "INSUFFICIENT_PERMISSIONS":
            raise ClientError(result.error, status_code=status.HTTP_403_FORBIDDEN)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    return result.value


@router.get(
    "/tasks/{task_id}/artifacts",
    response_model=ListArtifactsResponseDTO,
    status_code=status.HTTP_200_OK,
)
async def list_artifacts(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    List all artifacts for a task (UC-26).
    Requires authentication.

    Returns artifacts in creation order with type, status, version, and approval metadata.
    """
    # Use tenant_id from JWT for security
    use_case = ListArtifactsUseCase(uow=uow, tenant_id=current_user["tenant_id"])
    result = await use_case.execute(task_id)

    if result.is_err():
        if result.error.code == "TASK_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    return result.value


@router.get(
    "/tasks/{task_id}/artifacts/compare",
    response_model=ArtifactComparisonResponseDTO,
    status_code=status.HTTP_200_OK,
)
async def compare_artifact_versions(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    artifact_type: str = Query(..., alias="type", description="Artifact type to compare"),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Compare artifact versions for a task.
    Requires authentication.

    Returns all versions of artifacts for the specified type, sorted by version number.
    """
    # Use tenant_id from JWT for security
    use_case = CompareArtifactsUseCase(uow=uow, tenant_id=current_user["tenant_id"])
    result = await use_case.execute(task_id, artifact_type)

    if result.is_err():
        if result.error.code == "TASK_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        elif result.error.code == "INVALID_ARTIFACT_TYPE":
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    return result.value
