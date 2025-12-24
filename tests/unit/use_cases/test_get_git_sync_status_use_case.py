"""
Unit tests for GetGitSyncStatusUseCase (UC-31)
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from src.app.use_cases.git_sync import GetGitSyncStatusUseCase
from src.domain.git_sync_job import GitSyncJob
from src.domain.enums import GitSyncJobStatus


@pytest.fixture
def mock_uow():
    """Create a mock unit of work"""
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock()
    uow.git_sync_jobs = MagicMock()
    return uow


@pytest.fixture
def pending_job():
    """Create a pending Git sync job"""
    return GitSyncJob(
        id="job-123",
        artifact_id="artifact-1",
        tenant_id="tenant-789",
        repository_url="https://github.com/test/repo",
        branch="main",
        commit_message="Test commit",
        status=GitSyncJobStatus.pending,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def completed_job():
    """Create a completed Git sync job"""
    return GitSyncJob(
        id="job-456",
        artifact_id="artifact-1",
        tenant_id="tenant-789",
        repository_url="https://github.com/test/repo",
        branch="main",
        commit_message="Test commit",
        status=GitSyncJobStatus.completed,
        commit_sha="abc123def456",
        created_at=datetime.utcnow(),
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )


@pytest.fixture
def failed_job():
    """Create a failed Git sync job"""
    return GitSyncJob(
        id="job-789",
        artifact_id="artifact-1",
        tenant_id="tenant-789",
        repository_url="https://github.com/test/repo",
        branch="main",
        commit_message="Test commit",
        status=GitSyncJobStatus.failed,
        error_message="Authentication failed",
        retry_count=1,
        created_at=datetime.utcnow(),
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_get_pending_job_status(mock_uow, pending_job):
    """Get status of pending job"""
    # Arrange
    mock_uow.git_sync_jobs.get_by_id = AsyncMock(return_value=pending_job)

    use_case = GetGitSyncStatusUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("job-123")

    # Assert
    assert result.is_ok()
    assert result.value.id == "job-123"
    assert result.value.status == "pending"
    assert result.value.commit_sha is None
    assert result.value.error_message is None


@pytest.mark.asyncio
async def test_get_completed_job_status(mock_uow, completed_job):
    """Get status of completed job with commit SHA"""
    # Arrange
    mock_uow.git_sync_jobs.get_by_id = AsyncMock(return_value=completed_job)

    use_case = GetGitSyncStatusUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("job-456")

    # Assert
    assert result.is_ok()
    assert result.value.id == "job-456"
    assert result.value.status == "completed"
    assert result.value.commit_sha == "abc123def456"
    assert result.value.completed_at is not None


@pytest.mark.asyncio
async def test_get_failed_job_status(mock_uow, failed_job):
    """Get status of failed job with error message"""
    # Arrange
    mock_uow.git_sync_jobs.get_by_id = AsyncMock(return_value=failed_job)

    use_case = GetGitSyncStatusUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("job-789")

    # Assert
    assert result.is_ok()
    assert result.value.id == "job-789"
    assert result.value.status == "failed"
    assert result.value.error_message == "Authentication failed"
    assert result.value.retry_count == 1


@pytest.mark.asyncio
async def test_get_job_not_found(mock_uow):
    """Job not found returns error"""
    # Arrange
    mock_uow.git_sync_jobs.get_by_id = AsyncMock(return_value=None)

    use_case = GetGitSyncStatusUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("nonexistent-job")

    # Assert
    assert result.is_err()
    assert result.error.code == "GIT_SYNC_JOB_NOT_FOUND"


@pytest.mark.asyncio
async def test_tenant_isolation(mock_uow):
    """Tenant isolation - job from other tenant returns not found"""
    # Arrange
    mock_uow.git_sync_jobs.get_by_id = AsyncMock(return_value=None)

    use_case = GetGitSyncStatusUseCase(mock_uow, tenant_id="different-tenant")

    # Act
    result = await use_case.execute("job-123")

    # Assert
    assert result.is_err()
    assert result.error.code == "GIT_SYNC_JOB_NOT_FOUND"
