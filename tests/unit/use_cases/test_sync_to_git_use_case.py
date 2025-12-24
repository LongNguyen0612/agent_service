"""
Unit tests for SyncToGitUseCase (UC-31)
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from src.app.use_cases.git_sync import SyncToGitUseCase, SyncToGitRequestDTO
from src.domain.task import Task
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
    uow.tasks = MagicMock()
    uow.artifacts = MagicMock()
    uow.git_sync_jobs = MagicMock()
    return uow


@pytest.fixture
def sample_task():
    """Create a sample task"""
    return Task(
        id="task-123",
        project_id="project-123",
        tenant_id="tenant-789",
        title="Test Task",
        input_spec={"requirement": "test"},
    )


@pytest.fixture
def approved_artifact():
    """Create an approved artifact"""
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
        approved_at=datetime.utcnow(),
    )


@pytest.fixture
def draft_artifact():
    """Create a draft artifact"""
    return Artifact(
        id="artifact-2",
        task_id="task-123",
        pipeline_run_id="run-1",
        step_run_id="step-1",
        artifact_type=ArtifactType.CODE_FILES,
        status=ArtifactStatus.draft,
        version=1,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def sync_request():
    """Create a sync request"""
    return SyncToGitRequestDTO(
        repository_url="https://github.com/test/repo",
        branch="feature/generated-code",
        commit_message="Add generated code from Super Agent",
    )


@pytest.mark.asyncio
async def test_sync_to_git_success(mock_uow, sample_task, approved_artifact, sync_request):
    """AC-3.2.1: Successfully create Git sync job for approved artifact"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=approved_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)

    git_sync_job = GitSyncJob(
        id="job-123",
        artifact_id="artifact-1",
        tenant_id="tenant-789",
        repository_url=sync_request.repository_url,
        branch=sync_request.branch,
        commit_message=sync_request.commit_message,
        status=GitSyncJobStatus.pending,
        created_at=datetime.utcnow(),
    )
    mock_uow.git_sync_jobs.create = AsyncMock(return_value=git_sync_job)

    use_case = SyncToGitUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("artifact-1", sync_request)

    # Assert
    assert result.is_ok()
    assert result.value.sync_job_id == "job-123"
    assert result.value.status == "pending"

    mock_uow.git_sync_jobs.create.assert_called_once()
    mock_uow.commit.assert_called_once()


@pytest.mark.asyncio
async def test_sync_to_git_artifact_not_found(mock_uow, sync_request):
    """Artifact not found returns error"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=None)

    use_case = SyncToGitUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("nonexistent-artifact", sync_request)

    # Assert
    assert result.is_err()
    assert result.error.code == "ARTIFACT_NOT_FOUND"
    mock_uow.git_sync_jobs.create.assert_not_called()


@pytest.mark.asyncio
async def test_sync_to_git_artifact_not_approved(
    mock_uow, sample_task, draft_artifact, sync_request
):
    """Draft artifact cannot be synced"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=draft_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)

    use_case = SyncToGitUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("artifact-2", sync_request)

    # Assert
    assert result.is_err()
    assert result.error.code == "ARTIFACT_NOT_APPROVED"
    mock_uow.git_sync_jobs.create.assert_not_called()


@pytest.mark.asyncio
async def test_sync_to_git_invalid_repository_url(mock_uow, sample_task, approved_artifact):
    """Invalid repository URL returns error"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=approved_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)

    invalid_request = SyncToGitRequestDTO(
        repository_url="not-a-valid-url",
        branch="main",
        commit_message="Test commit",
    )

    use_case = SyncToGitUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("artifact-1", invalid_request)

    # Assert
    assert result.is_err()
    assert result.error.code == "INVALID_REPOSITORY_URL"
    mock_uow.git_sync_jobs.create.assert_not_called()


@pytest.mark.asyncio
async def test_sync_to_git_tenant_isolation(mock_uow, approved_artifact, sync_request):
    """Tenant isolation - artifact from other tenant returns not found"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=approved_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=None)  # Task not found for different tenant

    use_case = SyncToGitUseCase(mock_uow, tenant_id="different-tenant")

    # Act
    result = await use_case.execute("artifact-1", sync_request)

    # Assert
    assert result.is_err()
    assert result.error.code == "ARTIFACT_NOT_FOUND"
    mock_uow.git_sync_jobs.create.assert_not_called()


@pytest.mark.asyncio
async def test_sync_to_git_with_ssh_url(mock_uow, sample_task, approved_artifact):
    """SSH URL is valid"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=approved_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)

    ssh_request = SyncToGitRequestDTO(
        repository_url="git@github.com:test/repo.git",
        branch="main",
        commit_message="Test commit",
    )

    git_sync_job = GitSyncJob(
        id="job-123",
        artifact_id="artifact-1",
        tenant_id="tenant-789",
        repository_url=ssh_request.repository_url,
        branch=ssh_request.branch,
        commit_message=ssh_request.commit_message,
        status=GitSyncJobStatus.pending,
        created_at=datetime.utcnow(),
    )
    mock_uow.git_sync_jobs.create = AsyncMock(return_value=git_sync_job)

    use_case = SyncToGitUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("artifact-1", ssh_request)

    # Assert
    assert result.is_ok()
    mock_uow.git_sync_jobs.create.assert_called_once()


@pytest.mark.asyncio
async def test_sync_to_git_with_gitlab_url(mock_uow, sample_task, approved_artifact):
    """GitLab URL is valid"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=approved_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)

    gitlab_request = SyncToGitRequestDTO(
        repository_url="https://gitlab.com/test/repo",
        branch="main",
        commit_message="Test commit",
    )

    git_sync_job = GitSyncJob(
        id="job-123",
        artifact_id="artifact-1",
        tenant_id="tenant-789",
        repository_url=gitlab_request.repository_url,
        branch=gitlab_request.branch,
        commit_message=gitlab_request.commit_message,
        status=GitSyncJobStatus.pending,
        created_at=datetime.utcnow(),
    )
    mock_uow.git_sync_jobs.create = AsyncMock(return_value=git_sync_job)

    use_case = SyncToGitUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("artifact-1", gitlab_request)

    # Assert
    assert result.is_ok()
    mock_uow.git_sync_jobs.create.assert_called_once()
