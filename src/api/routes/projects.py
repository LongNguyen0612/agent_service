from fastapi import APIRouter, Depends, status
from src.api.error import ClientError
from src.app.services.unit_of_work import UnitOfWork
from src.app.services.audit_service import AuditService
from src.depends import get_unit_of_work, get_audit_service, get_current_user
from src.app.use_cases.projects import (
    CreateProjectUseCase,
    CreateProjectRequest,
    CreateProjectCommand,
    CreateProjectResponse,
    UpdateProjectUseCase,
    UpdateProjectRequest,
    UpdateProjectCommand,
    UpdateProjectResponse,
    GetProjectsUseCase,
    GetProjectsResponse,
    GetProjectByIdUseCase,
    ProjectDTO,
)

router = APIRouter()


@router.get("/projects", response_model=GetProjectsResponse, status_code=status.HTTP_200_OK)
async def get_projects(
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get all projects for the current tenant (requires authentication)"""
    use_case = GetProjectsUseCase(uow)
    result = await use_case.execute(tenant_id=current_user["tenant_id"])

    if result.is_err():
        raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    return result.value


@router.get("/projects/{project_id}", response_model=ProjectDTO, status_code=status.HTTP_200_OK)
async def get_project_by_id(
    project_id: str,
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """Get a single project by ID (requires authentication)"""
    use_case = GetProjectByIdUseCase(uow)
    result = await use_case.execute(project_id=project_id, tenant_id=current_user["tenant_id"])

    if result.is_err():
        if result.error.code == "NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        elif result.error.code == "INSUFFICIENT_PERMISSIONS":
            raise ClientError(result.error, status_code=status.HTTP_403_FORBIDDEN)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    return result.value


@router.post("/projects", response_model=CreateProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: CreateProjectRequest,
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    audit_service: AuditService = Depends(get_audit_service),
):
    """Create a new project (requires authentication)"""
    # Build command with tenant_id and user_id from JWT to ensure tenant isolation
    command = CreateProjectCommand(
        name=request.name,
        description=request.description,
        tenant_id=current_user["tenant_id"],
        user_id=current_user["user_id"],
    )

    use_case = CreateProjectUseCase(uow, audit_service)
    result = await use_case.execute(command)

    if result.is_err():
        raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    return result.value


@router.put(
    "/projects/{project_id}", response_model=UpdateProjectResponse, status_code=status.HTTP_200_OK
)
async def update_project(
    project_id: str,
    request: UpdateProjectRequest,
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    audit_service: AuditService = Depends(get_audit_service),
):
    """Update an existing project (requires authentication)"""
    # Convert request DTO to command DTO, adding project_id from path
    # Use tenant_id and user_id from JWT for security
    command = UpdateProjectCommand(
        project_id=project_id,
        name=request.name,
        description=request.description,
        status=request.status,
        tenant_id=current_user["tenant_id"],
        user_id=current_user["user_id"],
    )

    use_case = UpdateProjectUseCase(uow, audit_service)
    result = await use_case.execute(command)

    if result.is_err():
        # Return appropriate status code based on error
        if result.error.code == "NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        elif result.error.code == "INSUFFICIENT_PERMISSIONS":
            raise ClientError(result.error, status_code=status.HTTP_403_FORBIDDEN)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    return result.value
