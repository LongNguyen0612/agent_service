"""Git Sync API Routes - UC-31

API endpoints for syncing artifacts to Git repositories.
"""
from fastapi import APIRouter, Depends, status, BackgroundTasks
from src.api.error import ClientError
from src.app.services.unit_of_work import UnitOfWork
from src.app.services.git_service import IGitService
from src.depends import get_unit_of_work, get_current_user, get_git_service
from src.app.use_cases.git_sync import (
    SyncToGitUseCase,
    GetGitSyncStatusUseCase,
    ProcessGitSyncJobUseCase,
    SyncToGitRequestDTO,
    SyncToGitResponseDTO,
    GitSyncStatusDTO,
)
from config import ApplicationConfig

router = APIRouter()


async def process_git_sync_in_background(
    job_id: str,
    git_service: IGitService,
):
    """Background task to process Git sync job"""
    from src.adapter.services.unit_of_work import SqlAlchemyUnitOfWork
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.orm import sessionmaker
    from sqlmodel.ext.asyncio.session import AsyncSession

    engine = create_async_engine(ApplicationConfig.DB_URI, echo=False, future=True)
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
    )

    async with AsyncSessionLocal() as session:
        uow = SqlAlchemyUnitOfWork(session)
        use_case = ProcessGitSyncJobUseCase(uow=uow, git_service=git_service)
        await use_case.execute(job_id)

    await engine.dispose()


@router.post(
    "/artifacts/{artifact_id}/sync-git",
    response_model=SyncToGitResponseDTO,
    status_code=status.HTTP_202_ACCEPTED,
)
async def sync_artifact_to_git(
    artifact_id: str,
    request: SyncToGitRequestDTO,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    git_service: IGitService = Depends(get_git_service),
):
    """
    Sync an artifact to a Git repository (UC-31)

    Creates an async job to push the approved artifact to the specified
    Git repository and branch. Returns immediately with job ID;
    poll status endpoint for completion.

    Only approved artifacts can be synced.
    """
    use_case = SyncToGitUseCase(uow, tenant_id=current_user["tenant_id"])
    result = await use_case.execute(artifact_id, request)

    if result.is_err():
        if result.error.code == "ARTIFACT_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        elif result.error.code == "ARTIFACT_NOT_APPROVED":
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)
        elif result.error.code == "INVALID_REPOSITORY_URL":
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    # Schedule background processing
    background_tasks.add_task(
        process_git_sync_in_background,
        job_id=result.value.sync_job_id,
        git_service=git_service,
    )

    return result.value


@router.get(
    "/git-sync/{job_id}",
    response_model=GitSyncStatusDTO,
    status_code=status.HTTP_200_OK,
)
async def get_git_sync_status(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Get Git sync job status (UC-31)

    Returns the current status of a Git sync job.
    When complete, includes the commit SHA.
    """
    use_case = GetGitSyncStatusUseCase(uow, tenant_id=current_user["tenant_id"])
    result = await use_case.execute(job_id)

    if result.is_err():
        if result.error.code == "GIT_SYNC_JOB_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    return result.value
