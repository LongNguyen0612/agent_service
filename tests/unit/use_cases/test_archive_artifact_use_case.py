"""
Unit tests for ArchiveArtifactUseCase (UC-32)
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from src.app.use_cases.artifacts import ArchiveArtifactUseCase
from src.domain.artifact import Artifact
from src.domain.enums import ArtifactType, ArtifactStatus
from src.domain.task import Task


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
    return uow


@pytest.fixture
def sample_task():
    """Create a sample task"""
    return Task(
        id="task-123",
        project_id="project-456",
        tenant_id="tenant-789",
        title="Test Task",
        input_spec={"requirement": "test"},
    )


@pytest.fixture
def old_artifact():
    """Create an older version artifact (version 1)"""
    return Artifact(
        id="artifact-old",
        task_id="task-123",
        pipeline_run_id="run-1",
        step_run_id="step-1",
        artifact_type=ArtifactType.CODE_FILES,
        status=ArtifactStatus.draft,
        version=1,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def latest_artifact():
    """Create the latest version artifact (version 2)"""
    return Artifact(
        id="artifact-latest",
        task_id="task-123",
        pipeline_run_id="run-2",
        step_run_id="step-2",
        artifact_type=ArtifactType.CODE_FILES,
        status=ArtifactStatus.draft,
        version=2,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def superseded_artifact():
    """Create an already superseded artifact"""
    return Artifact(
        id="artifact-superseded",
        task_id="task-123",
        pipeline_run_id="run-1",
        step_run_id="step-1",
        artifact_type=ArtifactType.CODE_FILES,
        status=ArtifactStatus.superseded,
        version=1,
        created_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_archive_artifact_success(mock_uow, sample_task, old_artifact, latest_artifact):
    """AC-1.4.1: Successfully archive an older artifact version"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=old_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
    mock_uow.artifacts.get_latest_by_task_and_type = AsyncMock(return_value=latest_artifact)
    mock_uow.artifacts.update = AsyncMock(return_value=old_artifact)

    use_case = ArchiveArtifactUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("artifact-old")

    # Assert
    assert result.is_ok()
    assert result.value.id == "artifact-old"
    assert result.value.status == "superseded"

    # Verify artifact was updated
    mock_uow.artifacts.update.assert_called_once()
    mock_uow.commit.assert_called_once()


@pytest.mark.asyncio
async def test_archive_artifact_cannot_archive_latest(
    mock_uow, sample_task, latest_artifact
):
    """AC-1.4.2: Cannot archive the latest version"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=latest_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
    # Latest artifact is the same as the artifact being archived
    mock_uow.artifacts.get_latest_by_task_and_type = AsyncMock(return_value=latest_artifact)

    use_case = ArchiveArtifactUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("artifact-latest")

    # Assert
    assert result.is_err()
    assert result.error.code == "CANNOT_ARCHIVE_LATEST"
    mock_uow.artifacts.update.assert_not_called()


@pytest.mark.asyncio
async def test_archive_artifact_already_archived(
    mock_uow, sample_task, superseded_artifact, latest_artifact
):
    """Cannot archive already superseded artifact"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=superseded_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)

    use_case = ArchiveArtifactUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("artifact-superseded")

    # Assert
    assert result.is_err()
    assert result.error.code == "ALREADY_ARCHIVED"
    mock_uow.artifacts.update.assert_not_called()


@pytest.mark.asyncio
async def test_archive_artifact_not_found(mock_uow):
    """Artifact not found returns error"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=None)

    use_case = ArchiveArtifactUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("nonexistent-artifact")

    # Assert
    assert result.is_err()
    assert result.error.code == "ARTIFACT_NOT_FOUND"


@pytest.mark.asyncio
async def test_archive_artifact_tenant_isolation(mock_uow, old_artifact):
    """Tenant isolation - artifact from other tenant returns not found"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=old_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=None)  # Task not found for this tenant

    use_case = ArchiveArtifactUseCase(mock_uow, tenant_id="different-tenant")

    # Act
    result = await use_case.execute("artifact-old")

    # Assert
    assert result.is_err()
    assert result.error.code == "ARTIFACT_NOT_FOUND"
    mock_uow.artifacts.update.assert_not_called()
