"""
Unit tests for ListArtifactsUseCase (UC-26)
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from src.app.use_cases.artifacts import ListArtifactsUseCase
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
def sample_artifacts():
    """Create sample artifacts"""
    now = datetime.utcnow()
    return [
        Artifact(
            id="artifact-1",
            task_id="task-123",
            pipeline_run_id="run-1",
            step_run_id="step-1",
            artifact_type=ArtifactType.ANALYSIS_REPORT,
            status=ArtifactStatus.draft,
            version=1,
            created_at=now,
        ),
        Artifact(
            id="artifact-2",
            task_id="task-123",
            pipeline_run_id="run-1",
            step_run_id="step-2",
            artifact_type=ArtifactType.USER_STORIES,
            status=ArtifactStatus.approved,
            version=1,
            created_at=now,
            approved_at=now,
        ),
        Artifact(
            id="artifact-3",
            task_id="task-123",
            pipeline_run_id="run-1",
            step_run_id="step-3",
            artifact_type=ArtifactType.CODE_FILES,
            status=ArtifactStatus.rejected,
            version=1,
            created_at=now,
            rejected_at=now,
        ),
    ]


@pytest.mark.asyncio
async def test_list_artifacts_success(mock_uow, sample_task, sample_artifacts):
    """Test successful artifact listing"""
    # Arrange
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
    mock_uow.artifacts.get_by_task = AsyncMock(return_value=sample_artifacts)

    use_case = ListArtifactsUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("task-123")

    # Assert
    assert result.is_ok()
    assert len(result.value.artifacts) == 3

    # Verify first artifact
    artifact1 = result.value.artifacts[0]
    assert artifact1.id == "artifact-1"
    assert artifact1.artifact_type == "ANALYSIS_REPORT"
    assert artifact1.status == "draft"
    assert artifact1.version == 1
    assert artifact1.is_approved is False

    # Verify second artifact (approved)
    artifact2 = result.value.artifacts[1]
    assert artifact2.id == "artifact-2"
    assert artifact2.artifact_type == "USER_STORIES"
    assert artifact2.status == "approved"
    assert artifact2.is_approved is True
    assert artifact2.approved_at is not None

    # Verify third artifact (rejected)
    artifact3 = result.value.artifacts[2]
    assert artifact3.id == "artifact-3"
    assert artifact3.status == "rejected"
    assert artifact3.is_approved is False
    assert artifact3.rejected_at is not None

    # Verify repository calls
    mock_uow.tasks.get_by_id.assert_called_once_with("task-123", "tenant-789")
    mock_uow.artifacts.get_by_task.assert_called_once_with("task-123")


@pytest.mark.asyncio
async def test_list_artifacts_empty_list(mock_uow, sample_task):
    """Test listing artifacts when task has no artifacts"""
    # Arrange
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
    mock_uow.artifacts.get_by_task = AsyncMock(return_value=[])

    use_case = ListArtifactsUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("task-123")

    # Assert
    assert result.is_ok()
    assert len(result.value.artifacts) == 0


@pytest.mark.asyncio
async def test_list_artifacts_task_not_found(mock_uow):
    """Test listing artifacts for non-existent task"""
    # Arrange
    mock_uow.tasks.get_by_id = AsyncMock(return_value=None)

    use_case = ListArtifactsUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("nonexistent-task")

    # Assert
    assert result.is_err()
    assert result.error.code == "TASK_NOT_FOUND"
    assert result.error.message == "Task not found"

    # Verify artifacts were not queried
    mock_uow.artifacts.get_by_task.assert_not_called()


@pytest.mark.asyncio
async def test_list_artifacts_tenant_isolation(mock_uow):
    """Test that task lookup uses tenant_id for isolation"""
    # Arrange
    mock_uow.tasks.get_by_id = AsyncMock(return_value=None)

    use_case = ListArtifactsUseCase(mock_uow, tenant_id="different-tenant")

    # Act
    result = await use_case.execute("task-123")

    # Assert - Task not found because wrong tenant
    assert result.is_err()
    assert result.error.code == "TASK_NOT_FOUND"

    # Verify tenant_id was passed correctly
    mock_uow.tasks.get_by_id.assert_called_once_with("task-123", "different-tenant")
