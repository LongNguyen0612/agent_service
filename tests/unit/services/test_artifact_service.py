import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock
from src.app.services.artifact_service import ArtifactService
from src.domain.artifact import Artifact
from src.domain.enums import ArtifactType


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_artifact_repo():
    return AsyncMock()


@pytest.mark.asyncio
async def test_create_artifact_success(mock_artifact_repo, temp_storage):
    """Test basic artifact creation with versioning and file storage"""
    # Arrange
    mock_artifact_repo.get_max_version.return_value = 0  # First version

    service = ArtifactService(
        artifact_repo=mock_artifact_repo,
        storage_root=temp_storage,
    )

    task_id = "task-123"
    content = "This is PRD content"

    # Mock repository create to return the artifact
    async def create_mock(artifact):
        return artifact

    mock_artifact_repo.create.side_effect = create_mock

    # Act
    artifact = await service.create_artifact(
        task_id=task_id,
        pipeline_run_id="run-123",
        step_run_id="step-run-123",
        artifact_type=ArtifactType.document,
        content=content,
        metadata={"step_name": "generate_prd"},
    )

    # Assert
    assert artifact.task_id == task_id
    assert artifact.artifact_type == ArtifactType.document
    assert artifact.version == 1
    assert artifact.step_run_id == "step-run-123"
    assert artifact.content["metadata"] == {"step_name": "generate_prd"}

    # Verify file was created
    expected_path = Path(temp_storage) / task_id / "document_v1.txt"
    assert expected_path.exists()

    # Verify file content
    with open(expected_path, "r") as f:
        assert f.read() == content

    # Verify repository was called
    mock_artifact_repo.get_max_version.assert_called_once_with(task_id, ArtifactType.document)
    mock_artifact_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_artifact_versioning_auto_increment(mock_artifact_repo, temp_storage):
    """Test that versions auto-increment correctly"""
    # Arrange
    service = ArtifactService(
        artifact_repo=mock_artifact_repo,
        storage_root=temp_storage,
    )

    task_id = "task-123"

    async def create_mock(artifact):
        return artifact

    mock_artifact_repo.create.side_effect = create_mock

    # Create version 1 (max_version = 0)
    mock_artifact_repo.get_max_version.return_value = 0
    artifact_v1 = await service.create_artifact(
        task_id=task_id,
        pipeline_run_id="run-1",
        step_run_id="step-run-1",
        artifact_type=ArtifactType.document,
        content="Version 1 content",
    )

    # Create version 2 (max_version = 1)
    mock_artifact_repo.get_max_version.return_value = 1
    artifact_v2 = await service.create_artifact(
        task_id=task_id,
        pipeline_run_id="run-2",
        step_run_id="step-run-2",
        artifact_type=ArtifactType.document,
        content="Version 2 content",
    )

    # Create version 3 (max_version = 2)
    mock_artifact_repo.get_max_version.return_value = 2
    artifact_v3 = await service.create_artifact(
        task_id=task_id,
        pipeline_run_id="run-3",
        step_run_id="step-run-3",
        artifact_type=ArtifactType.document,
        content="Version 3 content",
    )

    # Assert versions
    assert artifact_v1.version == 1
    assert artifact_v2.version == 2
    assert artifact_v3.version == 3

    # Verify all 3 files exist
    assert (Path(temp_storage) / task_id / "document_v1.txt").exists()
    assert (Path(temp_storage) / task_id / "document_v2.txt").exists()
    assert (Path(temp_storage) / task_id / "document_v3.txt").exists()


@pytest.mark.asyncio
async def test_artifact_multiple_types_same_task(mock_artifact_repo, temp_storage):
    """Test that different artifact types for same task have independent versioning"""
    # Arrange
    service = ArtifactService(
        artifact_repo=mock_artifact_repo,
        storage_root=temp_storage,
    )

    task_id = "task-123"

    async def create_mock(artifact):
        return artifact

    mock_artifact_repo.create.side_effect = create_mock

    # Create document artifact (version 1)
    mock_artifact_repo.get_max_version.return_value = 0
    doc_artifact = await service.create_artifact(
        task_id=task_id,
        pipeline_run_id="run-1",
        step_run_id="step-run-1",
        artifact_type=ArtifactType.document,
        content="PRD content",
    )

    # Create code artifact (should also be version 1, independent versioning)
    mock_artifact_repo.get_max_version.return_value = 0
    code_artifact = await service.create_artifact(
        task_id=task_id,
        pipeline_run_id="run-1",
        step_run_id="step-run-2",
        artifact_type=ArtifactType.code,
        content="Stories content",
    )

    # Create another document artifact (version 2)
    mock_artifact_repo.get_max_version.return_value = 1
    doc_artifact_v2 = await service.create_artifact(
        task_id=task_id,
        pipeline_run_id="run-2",
        step_run_id="step-run-3",
        artifact_type=ArtifactType.document,
        content="PRD v2 content",
    )

    # Assert
    assert doc_artifact.version == 1
    assert doc_artifact.artifact_type == ArtifactType.document

    assert code_artifact.version == 1
    assert code_artifact.artifact_type == ArtifactType.code

    assert doc_artifact_v2.version == 2
    assert doc_artifact_v2.artifact_type == ArtifactType.document

    # Verify files exist
    assert (Path(temp_storage) / task_id / "document_v1.txt").exists()
    assert (Path(temp_storage) / task_id / "code_v1.txt").exists()
    assert (Path(temp_storage) / task_id / "document_v2.txt").exists()


@pytest.mark.asyncio
async def test_artifact_file_storage_structure(mock_artifact_repo, temp_storage):
    """Test that artifact files are stored in correct directory structure"""
    # Arrange
    service = ArtifactService(
        artifact_repo=mock_artifact_repo,
        storage_root=temp_storage,
    )

    mock_artifact_repo.get_max_version.return_value = 0

    async def create_mock(artifact):
        return artifact

    mock_artifact_repo.create.side_effect = create_mock

    # Act
    task_id = "task-abc-123"
    await service.create_artifact(
        task_id=task_id,
        pipeline_run_id="run-1",
        step_run_id="step-run-1",
        artifact_type=ArtifactType.document,
        content="Test content",
    )

    # Assert
    task_dir = Path(temp_storage) / task_id
    assert task_dir.exists()
    assert task_dir.is_dir()

    artifact_file = task_dir / "document_v1.txt"
    assert artifact_file.exists()
    assert artifact_file.is_file()


@pytest.mark.asyncio
async def test_read_content_success(mock_artifact_repo, temp_storage):
    """Test reading artifact content from filesystem"""
    # Arrange
    service = ArtifactService(
        artifact_repo=mock_artifact_repo,
        storage_root=temp_storage,
    )

    # Create a test file
    task_id = "task-123"
    task_dir = Path(temp_storage) / task_id
    task_dir.mkdir(parents=True)

    content = "This is test artifact content"
    file_path = task_dir / "document_v1.txt"
    with open(file_path, "w") as f:
        f.write(content)

    # Act - use absolute path
    read_content = service.read_content(str(file_path))

    # Assert
    assert read_content == content


def test_read_content_file_not_found(mock_artifact_repo, temp_storage):
    """Test reading non-existent artifact raises FileNotFoundError"""
    # Arrange
    service = ArtifactService(
        artifact_repo=mock_artifact_repo,
        storage_root=temp_storage,
    )

    # Act & Assert
    with pytest.raises(FileNotFoundError) as exc_info:
        service.read_content("artifacts/task-999/non-existent.txt")

    assert "not found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_artifact_content_url_format(mock_artifact_repo, temp_storage):
    """Test that content_url has correct format"""
    # Arrange
    service = ArtifactService(
        artifact_repo=mock_artifact_repo,
        storage_root=temp_storage,
    )

    mock_artifact_repo.get_max_version.return_value = 0

    async def create_mock(artifact):
        return artifact

    mock_artifact_repo.create.side_effect = create_mock

    # Act
    artifact = await service.create_artifact(
        task_id="task-123",
        pipeline_run_id="run-1",
        step_run_id="step-run-1",
        artifact_type=ArtifactType.document,
        content="Test content",
    )

    # Assert content_url format - content_url is in the content dict
    assert "task-123" in artifact.content["url"]
    assert "document_v1.txt" in artifact.content["url"]


@pytest.mark.asyncio
async def test_artifact_metadata_storage(mock_artifact_repo, temp_storage):
    """Test that artifact metadata is properly stored"""
    # Arrange
    service = ArtifactService(
        artifact_repo=mock_artifact_repo,
        storage_root=temp_storage,
    )

    mock_artifact_repo.get_max_version.return_value = 0

    async def create_mock(artifact):
        return artifact

    mock_artifact_repo.create.side_effect = create_mock

    metadata = {
        "step_name": "generate_prd",
        "generated_at": "2025-12-24T10:00:00",
        "model": "gpt-4",
        "temperature": 0.7,
    }

    # Act
    artifact = await service.create_artifact(
        task_id="task-123",
        pipeline_run_id="run-1",
        step_run_id="step-run-1",
        artifact_type=ArtifactType.document,
        content="Test content",
        metadata=metadata,
    )

    # Assert
    assert artifact.content["metadata"] == metadata


@pytest.mark.asyncio
async def test_artifact_service_creates_storage_root(mock_artifact_repo, temp_storage):
    """Test that ArtifactService creates storage root directory if it doesn't exist"""
    # Arrange
    storage_path = Path(temp_storage) / "new_artifacts_dir"
    assert not storage_path.exists()

    # Act
    service = ArtifactService(
        artifact_repo=mock_artifact_repo,
        storage_root=str(storage_path),
    )

    # Assert
    assert storage_path.exists()
    assert storage_path.is_dir()


@pytest.mark.asyncio
async def test_concurrent_artifact_creation_versioning(mock_artifact_repo, temp_storage):
    """Test that concurrent artifact creation with same task/type gets correct versions"""
    # Arrange
    service = ArtifactService(
        artifact_repo=mock_artifact_repo,
        storage_root=temp_storage,
    )

    async def create_mock(artifact):
        return artifact

    mock_artifact_repo.create.side_effect = create_mock

    # Simulate concurrent calls with different max versions
    mock_artifact_repo.get_max_version.side_effect = [0, 1, 2]  # Sequential versions

    # Act
    artifacts = []
    for i in range(3):
        artifact = await service.create_artifact(
            task_id="task-123",
            pipeline_run_id=f"run-{i+1}",
            step_run_id=f"step-run-{i+1}",
            artifact_type=ArtifactType.document,
            content=f"Content {i+1}",
        )
        artifacts.append(artifact)

    # Assert
    assert artifacts[0].version == 1
    assert artifacts[1].version == 2
    assert artifacts[2].version == 3

    # Verify get_max_version was called for each creation
    assert mock_artifact_repo.get_max_version.call_count == 3
