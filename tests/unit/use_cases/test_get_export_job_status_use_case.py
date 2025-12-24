"""
Unit tests for GetExportJobStatusUseCase (UC-30)
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from src.app.use_cases.exports import GetExportJobStatusUseCase
from src.domain.export_job import ExportJob
from src.domain.enums import ExportJobStatus


@pytest.fixture
def mock_uow():
    """Create a mock unit of work"""
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.export_jobs = MagicMock()
    return uow


@pytest.fixture
def pending_export_job():
    """Create a pending export job"""
    return ExportJob(
        id="job-123",
        project_id="project-456",
        tenant_id="tenant-789",
        status=ExportJobStatus.pending,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def completed_export_job():
    """Create a completed export job"""
    expires_at = datetime.utcnow() + timedelta(hours=1)
    return ExportJob(
        id="job-123",
        project_id="project-456",
        tenant_id="tenant-789",
        status=ExportJobStatus.completed,
        file_path="exports/tenant-789/project-456/job-123.zip",
        download_url="http://localhost:8000/files/exports/tenant-789/project-456/job-123.zip",
        expires_at=expires_at,
        created_at=datetime.utcnow() - timedelta(minutes=5),
        started_at=datetime.utcnow() - timedelta(minutes=4),
        completed_at=datetime.utcnow(),
    )


@pytest.fixture
def failed_export_job():
    """Create a failed export job"""
    return ExportJob(
        id="job-123",
        project_id="project-456",
        tenant_id="tenant-789",
        status=ExportJobStatus.failed,
        error_message="Failed to generate ZIP",
        created_at=datetime.utcnow() - timedelta(minutes=5),
        started_at=datetime.utcnow() - timedelta(minutes=4),
        completed_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_get_export_job_status_pending(mock_uow, pending_export_job):
    """Get status of pending export job"""
    # Arrange
    mock_uow.export_jobs.get_by_id = AsyncMock(return_value=pending_export_job)

    use_case = GetExportJobStatusUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("job-123")

    # Assert
    assert result.is_ok()
    assert result.value.export_job_id == "job-123"
    assert result.value.project_id == "project-456"
    assert result.value.status == "pending"
    assert result.value.download_url is None
    assert result.value.error_message is None


@pytest.mark.asyncio
async def test_get_export_job_status_completed(mock_uow, completed_export_job):
    """AC-3.1.2: Get status of completed export job with download URL"""
    # Arrange
    mock_uow.export_jobs.get_by_id = AsyncMock(return_value=completed_export_job)

    use_case = GetExportJobStatusUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("job-123")

    # Assert
    assert result.is_ok()
    assert result.value.export_job_id == "job-123"
    assert result.value.status == "completed"
    assert result.value.download_url is not None
    assert "job-123.zip" in result.value.download_url
    assert result.value.expires_at is not None
    assert result.value.completed_at is not None


@pytest.mark.asyncio
async def test_get_export_job_status_failed(mock_uow, failed_export_job):
    """Get status of failed export job with error message"""
    # Arrange
    mock_uow.export_jobs.get_by_id = AsyncMock(return_value=failed_export_job)

    use_case = GetExportJobStatusUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("job-123")

    # Assert
    assert result.is_ok()
    assert result.value.export_job_id == "job-123"
    assert result.value.status == "failed"
    assert result.value.error_message == "Failed to generate ZIP"
    assert result.value.download_url is None


@pytest.mark.asyncio
async def test_get_export_job_status_not_found(mock_uow):
    """Export job not found returns error"""
    # Arrange
    mock_uow.export_jobs.get_by_id = AsyncMock(return_value=None)

    use_case = GetExportJobStatusUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("nonexistent-job")

    # Assert
    assert result.is_err()
    assert result.error.code == "EXPORT_JOB_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_export_job_status_tenant_isolation(mock_uow, pending_export_job):
    """Tenant isolation - job from other tenant returns not found"""
    # Arrange
    mock_uow.export_jobs.get_by_id = AsyncMock(return_value=None)

    use_case = GetExportJobStatusUseCase(mock_uow, tenant_id="different-tenant")

    # Act
    result = await use_case.execute("job-123")

    # Assert
    assert result.is_err()
    assert result.error.code == "EXPORT_JOB_NOT_FOUND"
