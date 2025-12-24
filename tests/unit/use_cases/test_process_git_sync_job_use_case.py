"""
Unit tests for ProcessGitSyncJobUseCase (UC-31)
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from src.app.use_cases.git_sync import ProcessGitSyncJobUseCase
from src.app.services.git_service import GitPushResult
from src.domain.artifact import Artifact
from src.domain.git_sync_job import GitSyncJob
from src.domain.enums import ArtifactType, ArtifactStatus, GitSyncJobStatus


@pytest.fixture
def mock_uow():
    """Create a mock unit of work"""
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.artifacts = MagicMock()
    uow.git_sync_jobs = MagicMock()
    return uow


@pytest.fixture
def mock_git_service():
    """Create a mock Git service"""
    service = MagicMock()
    return service


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
def artifact_with_content():
    """Create an artifact with content"""
    return Artifact(
        id="artifact-1",
        task_id="task-123",
        pipeline_run_id="run-1",
        step_run_id="step-1",
        artifact_type=ArtifactType.CODE_FILES,
        status=ArtifactStatus.approved,
        version=1,
        content={"files": [{"filename": "test.py", "content": "print('hello')"}]},
        created_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_process_job_success(mock_uow, mock_git_service, pending_job, artifact_with_content):
    """Successfully process Git sync job"""
    # Arrange
    mock_uow.git_sync_jobs.get_by_id = AsyncMock(return_value=pending_job)
    mock_uow.git_sync_jobs.update = AsyncMock(return_value=pending_job)
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=artifact_with_content)

    mock_git_service.push_content = AsyncMock(
        return_value=GitPushResult(success=True, commit_sha="abc123def456")
    )

    use_case = ProcessGitSyncJobUseCase(mock_uow, git_service=mock_git_service)

    # Act
    result = await use_case.execute("job-123")

    # Assert
    assert result.is_ok()
    assert result.value is True

    # Verify Git push was called
    mock_git_service.push_content.assert_called_once()

    # Verify job was updated (at least twice: start_processing and complete)
    assert mock_uow.git_sync_jobs.update.call_count >= 2
    assert mock_uow.commit.call_count >= 2


@pytest.mark.asyncio
async def test_process_job_not_found(mock_uow, mock_git_service):
    """Job not found returns error"""
    # Arrange
    mock_uow.git_sync_jobs.get_by_id = AsyncMock(return_value=None)

    use_case = ProcessGitSyncJobUseCase(mock_uow, git_service=mock_git_service)

    # Act
    result = await use_case.execute("nonexistent-job")

    # Assert
    assert result.is_err()
    assert result.error.code == "GIT_SYNC_JOB_NOT_FOUND"


@pytest.mark.asyncio
async def test_process_job_already_processing(mock_uow, mock_git_service, pending_job):
    """Skip job that is not pending"""
    # Arrange
    pending_job.status = GitSyncJobStatus.processing
    mock_uow.git_sync_jobs.get_by_id = AsyncMock(return_value=pending_job)

    use_case = ProcessGitSyncJobUseCase(mock_uow, git_service=mock_git_service)

    # Act
    result = await use_case.execute("job-123")

    # Assert
    assert result.is_ok()
    assert result.value is False
    mock_git_service.push_content.assert_not_called()


@pytest.mark.asyncio
async def test_process_job_artifact_not_found(mock_uow, mock_git_service, pending_job):
    """Artifact not found marks job as failed"""
    # Arrange
    mock_uow.git_sync_jobs.get_by_id = AsyncMock(return_value=pending_job)
    mock_uow.git_sync_jobs.update = AsyncMock(return_value=pending_job)
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=None)

    use_case = ProcessGitSyncJobUseCase(mock_uow, git_service=mock_git_service)

    # Act
    result = await use_case.execute("job-123")

    # Assert
    assert result.is_err()
    assert result.error.code == "ARTIFACT_NOT_FOUND"

    # Verify job was marked as failed
    mock_uow.git_sync_jobs.update.assert_called()


@pytest.mark.asyncio
async def test_process_job_git_push_failure(
    mock_uow, mock_git_service, pending_job, artifact_with_content
):
    """Git push failure marks job as failed with retry"""
    # Arrange
    mock_uow.git_sync_jobs.get_by_id = AsyncMock(return_value=pending_job)
    mock_uow.git_sync_jobs.update = AsyncMock(return_value=pending_job)
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=artifact_with_content)

    mock_git_service.push_content = AsyncMock(
        return_value=GitPushResult(success=False, error_message="Authentication failed")
    )

    use_case = ProcessGitSyncJobUseCase(mock_uow, git_service=mock_git_service)

    # Act
    result = await use_case.execute("job-123")

    # Assert
    assert result.is_ok()
    assert result.value is False

    # Verify job was updated with retry
    mock_uow.git_sync_jobs.update.assert_called()


@pytest.mark.asyncio
async def test_process_job_no_content(mock_uow, mock_git_service, pending_job):
    """Artifact with no content marks job as failed"""
    # Arrange
    artifact_no_content = Artifact(
        id="artifact-1",
        task_id="task-123",
        pipeline_run_id="run-1",
        step_run_id="step-1",
        artifact_type=ArtifactType.CODE_FILES,
        status=ArtifactStatus.approved,
        version=1,
        content=None,  # No content
        created_at=datetime.utcnow(),
    )

    mock_uow.git_sync_jobs.get_by_id = AsyncMock(return_value=pending_job)
    mock_uow.git_sync_jobs.update = AsyncMock(return_value=pending_job)
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=artifact_no_content)

    use_case = ProcessGitSyncJobUseCase(mock_uow, git_service=mock_git_service)

    # Act
    result = await use_case.execute("job-123")

    # Assert
    assert result.is_err()
    assert result.error.code == "NO_CONTENT"


@pytest.mark.asyncio
async def test_process_job_max_retries_exceeded(
    mock_uow, mock_git_service, artifact_with_content
):
    """Job with max retries exceeded stays failed"""
    # Arrange
    max_retried_job = GitSyncJob(
        id="job-123",
        artifact_id="artifact-1",
        tenant_id="tenant-789",
        repository_url="https://github.com/test/repo",
        branch="main",
        commit_message="Test commit",
        status=GitSyncJobStatus.pending,
        retry_count=3,  # Already at max
        max_retries=3,
        created_at=datetime.utcnow(),
    )

    mock_uow.git_sync_jobs.get_by_id = AsyncMock(return_value=max_retried_job)
    mock_uow.git_sync_jobs.update = AsyncMock(return_value=max_retried_job)
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=artifact_with_content)

    mock_git_service.push_content = AsyncMock(
        return_value=GitPushResult(success=False, error_message="Still failing")
    )

    use_case = ProcessGitSyncJobUseCase(mock_uow, git_service=mock_git_service)

    # Act
    result = await use_case.execute("job-123")

    # Assert
    assert result.is_ok()
    assert result.value is False

    # Job should not be retried
    assert not max_retried_job.can_retry()
