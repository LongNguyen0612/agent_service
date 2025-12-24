"""Export API Routes - UC-30

API endpoints for exporting project artifacts as ZIP.
"""
from fastapi import APIRouter, Depends, status, BackgroundTasks
from src.api.error import ClientError
from src.app.services.unit_of_work import UnitOfWork
from src.app.services.file_storage import FileStorage
from src.depends import get_unit_of_work, get_current_user, get_file_storage
from src.app.use_cases.exports import (
    CreateExportJobUseCase,
    GetExportJobStatusUseCase,
    ProcessExportJobUseCase,
    CreateExportJobResponseDTO,
    ExportJobStatusDTO,
)
from config import ApplicationConfig

router = APIRouter()


async def process_export_in_background(
    job_id: str,
    file_storage: FileStorage,
):
    """Background task to process export job"""
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
        use_case = ProcessExportJobUseCase(
            uow=uow,
            file_storage=file_storage,
            url_expiry_seconds=ApplicationConfig.EXPORT_URL_EXPIRY_SECONDS
        )
        await use_case.execute(job_id)

    await engine.dispose()


@router.post(
    "/projects/{project_id}/export",
    response_model=CreateExportJobResponseDTO,
    status_code=status.HTTP_202_ACCEPTED
)
async def create_export_job(
    project_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
    file_storage: FileStorage = Depends(get_file_storage),
):
    """
    Create an export job for a project (UC-30)

    Creates an async job to export all approved artifacts as a ZIP file.
    Returns immediately with job ID; poll status endpoint for completion.
    """
    use_case = CreateExportJobUseCase(uow, tenant_id=current_user["tenant_id"])
    result = await use_case.execute(project_id)

    if result.is_err():
        if result.error.code == "PROJECT_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        elif result.error.code in ("NO_ARTIFACTS", "NO_APPROVED_ARTIFACTS"):
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    # Schedule background processing
    background_tasks.add_task(
        process_export_in_background,
        job_id=result.value.export_job_id,
        file_storage=file_storage,
    )

    return result.value


@router.get(
    "/projects/{project_id}/export/{job_id}",
    response_model=ExportJobStatusDTO,
    status_code=status.HTTP_200_OK
)
async def get_export_job_status(
    project_id: str,
    job_id: str,
    current_user: dict = Depends(get_current_user),
    uow: UnitOfWork = Depends(get_unit_of_work),
):
    """
    Get export job status (UC-30)

    Returns the current status of an export job.
    When complete, includes the download URL.
    """
    use_case = GetExportJobStatusUseCase(uow, tenant_id=current_user["tenant_id"])
    result = await use_case.execute(job_id)

    if result.is_err():
        if result.error.code == "EXPORT_JOB_NOT_FOUND":
            raise ClientError(result.error, status_code=status.HTTP_404_NOT_FOUND)
        else:
            raise ClientError(result.error, status_code=status.HTTP_400_BAD_REQUEST)

    # Verify job belongs to requested project
    if result.value.project_id != project_id:
        from libs.result import Error
        raise ClientError(
            Error(code="EXPORT_JOB_NOT_FOUND", message="Export job not found"),
            status_code=status.HTTP_404_NOT_FOUND
        )

    return result.value
