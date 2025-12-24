import pytest
from datetime import datetime
from unittest.mock import AsyncMock
from src.app.use_cases.artifacts import CompareArtifactsUseCase
from src.domain.artifact import Artifact
from src.domain.task import Task
from src.domain.enums import ArtifactType, TaskStatus


@pytest.mark.asyncio
async def test_compare_artifacts_success_multiple_versions(mock_uow):
    """Test successful comparison of multiple artifact versions"""
    # Arrange
    tenant_id = "tenant-123"
    task_id = "task-456"
    artifact_type = "document"

    # Mock task
    mock_task = Task(
        id=task_id,
        tenant_id=tenant_id,
        project_id="project-123",
        title="Test Task",
        input_spec={"requirement": "Test"},
        status=TaskStatus.completed,
    )
    mock_uow.tasks.get_by_id = AsyncMock(return_value=mock_task)

    # Mock artifacts (3 versions)
    mock_artifacts = [
        Artifact(
            id="artifact-1",
            task_id=task_id,
            pipeline_run_id="run-1",
            step_run_id="step-run-1",
            artifact_type=ArtifactType.document,
            version=1,
            content={
                "text": "Document v1 content",
                "url": "/artifacts/task-456/document_v1.txt",
                "metadata": {"size": 1024}
            },
            created_at=datetime(2025, 1, 1, 10, 0, 0),
        ),
        Artifact(
            id="artifact-2",
            task_id=task_id,
            pipeline_run_id="run-2",
            step_run_id="step-run-2",
            artifact_type=ArtifactType.document,
            version=2,
            content={
                "text": "Document v2 content",
                "url": "/artifacts/task-456/document_v2.txt",
                "metadata": {"size": 2048}
            },
            created_at=datetime(2025, 1, 1, 11, 0, 0),
        ),
        Artifact(
            id="artifact-3",
            task_id=task_id,
            pipeline_run_id="run-3",
            step_run_id="step-run-3",
            artifact_type=ArtifactType.document,
            version=3,
            content={
                "text": "Document v3 content",
                "url": "/artifacts/task-456/document_v3.txt",
                "metadata": {"size": 3072}
            },
            created_at=datetime(2025, 1, 1, 12, 0, 0),
        ),
    ]
    mock_uow.artifacts.get_by_task_and_type = AsyncMock(return_value=mock_artifacts)

    use_case = CompareArtifactsUseCase(uow=mock_uow, tenant_id=tenant_id)

    # Act
    result = await use_case.execute(task_id, artifact_type)

    # Assert
    assert result.is_ok()
    response = result.value
    assert response.task_id == task_id
    assert response.artifact_type == artifact_type
    assert len(response.versions) == 3

    # Verify versions are in ascending order
    assert response.versions[0].version == 1
    assert response.versions[1].version == 2
    assert response.versions[2].version == 3

    # Verify version details
    assert response.versions[0].id == "artifact-1"
    assert response.versions[0].pipeline_run_id == "run-1"
    assert response.versions[0].step_run_id == "step-run-1"

    # Verify repository calls
    mock_uow.tasks.get_by_id.assert_called_once_with(task_id, tenant_id)
    mock_uow.artifacts.get_by_task_and_type.assert_called_once_with(
        task_id, ArtifactType.document
    )


@pytest.mark.asyncio
async def test_compare_artifacts_success_empty_list(mock_uow):
    """Test successful comparison with no artifacts (returns empty list)"""
    # Arrange
    tenant_id = "tenant-123"
    task_id = "task-456"
    artifact_type = "code"

    # Mock task
    mock_task = Task(
        id=task_id,
        tenant_id=tenant_id,
        project_id="project-123",
        title="Test Task",
        input_spec={"requirement": "Test"},
        status=TaskStatus.draft,
    )
    mock_uow.tasks.get_by_id = AsyncMock(return_value=mock_task)

    # No artifacts
    mock_uow.artifacts.get_by_task_and_type = AsyncMock(return_value=[])

    use_case = CompareArtifactsUseCase(uow=mock_uow, tenant_id=tenant_id)

    # Act
    result = await use_case.execute(task_id, artifact_type)

    # Assert
    assert result.is_ok()
    response = result.value
    assert response.task_id == task_id
    assert response.artifact_type == artifact_type
    assert len(response.versions) == 0


@pytest.mark.asyncio
async def test_compare_artifacts_task_not_found(mock_uow):
    """Test error when task does not exist"""
    # Arrange
    tenant_id = "tenant-123"
    task_id = "non-existent-task"
    artifact_type = "document"

    mock_uow.tasks.get_by_id = AsyncMock(return_value=None)

    use_case = CompareArtifactsUseCase(uow=mock_uow, tenant_id=tenant_id)

    # Act
    result = await use_case.execute(task_id, artifact_type)

    # Assert
    assert result.is_err()
    assert result.error.code == "TASK_NOT_FOUND"
    assert result.error.message == "Task not found"


@pytest.mark.asyncio
async def test_compare_artifacts_invalid_artifact_type(mock_uow):
    """Test error with invalid artifact type"""
    # Arrange
    tenant_id = "tenant-123"
    task_id = "task-456"
    artifact_type = "invalid_type"

    # Mock task
    mock_task = Task(
        id=task_id,
        tenant_id=tenant_id,
        project_id="project-123",
        title="Test Task",
        input_spec={"requirement": "Test"},
        status=TaskStatus.running,
    )
    mock_uow.tasks.get_by_id = AsyncMock(return_value=mock_task)

    use_case = CompareArtifactsUseCase(uow=mock_uow, tenant_id=tenant_id)

    # Act
    result = await use_case.execute(task_id, artifact_type)

    # Assert
    assert result.is_err()
    assert result.error.code == "INVALID_ARTIFACT_TYPE"
    assert "Invalid artifact type" in result.error.message
    assert "invalid_type" in result.error.message


@pytest.mark.asyncio
async def test_compare_artifacts_all_valid_types(mock_uow):
    """Test that all valid artifact types are accepted"""
    # Arrange
    tenant_id = "tenant-123"
    task_id = "task-456"

    # Mock task
    mock_task = Task(
        id=task_id,
        tenant_id=tenant_id,
        project_id="project-123",
        title="Test Task",
        input_spec={"requirement": "Test"},
        status=TaskStatus.running,
    )
    mock_uow.tasks.get_by_id = AsyncMock(return_value=mock_task)
    mock_uow.artifacts.get_by_task_and_type = AsyncMock(return_value=[])

    use_case = CompareArtifactsUseCase(uow=mock_uow, tenant_id=tenant_id)

    # Act & Assert - Test all valid types
    valid_types = ["document", "code"]
    for artifact_type in valid_types:
        result = await use_case.execute(task_id, artifact_type)
        assert result.is_ok(), f"Failed for type: {artifact_type}"
