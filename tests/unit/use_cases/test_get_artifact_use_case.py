"""
Unit tests for GetArtifactUseCase (UC-27)
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from src.app.use_cases.artifacts import GetArtifactUseCase
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
def sample_artifact():
    """Create a sample artifact"""
    return Artifact(
        id="artifact-1",
        task_id="task-123",
        pipeline_run_id="run-1",
        step_run_id="step-1",
        artifact_type=ArtifactType.CODE_FILES,
        status=ArtifactStatus.draft,
        version=1,
        content={"files": [{"name": "main.py", "content": "print('hello')"}]},
        created_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_get_artifact_success(mock_uow, sample_task, sample_artifact):
    """AC-1.1.1: Get artifact by ID successfully"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=sample_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)

    use_case = GetArtifactUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("artifact-1")

    # Assert
    assert result.is_ok()
    assert result.value.id == "artifact-1"
    assert result.value.task_id == "task-123"
    assert result.value.artifact_type == "CODE_FILES"
    assert result.value.version == 1
    assert result.value.status == "draft"
    assert result.value.content is not None
    assert "files" in result.value.content

    # Verify repository calls
    mock_uow.artifacts.get_by_id.assert_called_once_with("artifact-1")
    mock_uow.tasks.get_by_id.assert_called_once_with("task-123", "tenant-789")


@pytest.mark.asyncio
async def test_get_artifact_not_found(mock_uow):
    """AC-1.1.2: Artifact not found returns 404"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=None)

    use_case = GetArtifactUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("nonexistent-artifact")

    # Assert
    assert result.is_err()
    assert result.error.code == "ARTIFACT_NOT_FOUND"
    assert result.error.message == "Artifact not found"


@pytest.mark.asyncio
async def test_get_artifact_tenant_isolation(mock_uow, sample_artifact):
    """AC-1.1.3: Tenant isolation - artifact from other tenant returns 404"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=sample_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=None)  # Task not found for this tenant

    use_case = GetArtifactUseCase(mock_uow, tenant_id="different-tenant")

    # Act
    result = await use_case.execute("artifact-1")

    # Assert - Returns NOT_FOUND for security (doesn't reveal existence)
    assert result.is_err()
    assert result.error.code == "ARTIFACT_NOT_FOUND"

    # Verify tenant isolation via task lookup
    mock_uow.tasks.get_by_id.assert_called_once_with("task-123", "different-tenant")
