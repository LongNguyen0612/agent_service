"""
Unit tests for RejectArtifactUseCase (UC-29)
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from src.app.use_cases.artifacts import RejectArtifactUseCase, RejectArtifactRequestDTO
from src.domain.artifact import Artifact
from src.domain.pipeline_run import PipelineRun
from src.domain.enums import ArtifactType, ArtifactStatus, PipelineStatus
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
    uow.pipeline_runs = MagicMock()
    return uow


@pytest.fixture
def mock_audit_service():
    """Create a mock audit service"""
    audit = MagicMock()
    audit.log_event = AsyncMock()
    return audit


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
def draft_artifact():
    """Create a draft artifact"""
    return Artifact(
        id="artifact-1",
        task_id="task-123",
        pipeline_run_id="run-1",
        step_run_id="step-1",
        artifact_type=ArtifactType.CODE_FILES,
        status=ArtifactStatus.draft,
        version=1,
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def rejected_artifact():
    """Create a rejected artifact"""
    return Artifact(
        id="artifact-2",
        task_id="task-123",
        pipeline_run_id="run-1",
        step_run_id="step-1",
        artifact_type=ArtifactType.CODE_FILES,
        status=ArtifactStatus.rejected,
        version=1,
        created_at=datetime.utcnow(),
        rejected_at=datetime.utcnow(),
    )


@pytest.fixture
def approved_artifact():
    """Create an approved artifact"""
    return Artifact(
        id="artifact-3",
        task_id="task-123",
        pipeline_run_id="run-1",
        step_run_id="step-1",
        artifact_type=ArtifactType.CODE_FILES,
        status=ArtifactStatus.approved,
        version=1,
        created_at=datetime.utcnow(),
        approved_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_reject_artifact_success(mock_uow, mock_audit_service, sample_task, draft_artifact):
    """AC-1.3.1: Successfully reject a draft artifact"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=draft_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
    mock_uow.artifacts.update = AsyncMock(return_value=draft_artifact)

    use_case = RejectArtifactUseCase(
        mock_uow,
        tenant_id="tenant-789",
        user_id="user-123",
        audit_service=mock_audit_service,
    )

    request = RejectArtifactRequestDTO(regenerate=False)

    # Act
    result = await use_case.execute("artifact-1", request)

    # Assert
    assert result.is_ok()
    assert result.value.id == "artifact-1"
    assert result.value.status == "rejected"
    assert result.value.rejected_at is not None
    assert result.value.new_pipeline_run_id is None

    # Verify artifact was updated
    mock_uow.artifacts.update.assert_called_once()
    mock_uow.commit.assert_called_once()

    # Verify audit event was logged
    mock_audit_service.log_event.assert_called_once()
    call_args = mock_audit_service.log_event.call_args
    assert call_args.kwargs["event_type"] == "artifact_rejected"


@pytest.mark.asyncio
async def test_reject_artifact_with_feedback(
    mock_uow, mock_audit_service, sample_task, draft_artifact
):
    """AC-1.3.2: Rejection with feedback stores feedback in metadata"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=draft_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
    mock_uow.artifacts.update = AsyncMock(return_value=draft_artifact)

    use_case = RejectArtifactUseCase(
        mock_uow,
        tenant_id="tenant-789",
        user_id="user-123",
        audit_service=mock_audit_service,
    )

    request = RejectArtifactRequestDTO(
        feedback="Please add more error handling",
        regenerate=False,
    )

    # Act
    result = await use_case.execute("artifact-1", request)

    # Assert
    assert result.is_ok()
    # Feedback should be stored in artifact extra_data
    assert draft_artifact.extra_data is not None
    assert draft_artifact.extra_data.get("rejection_feedback") == "Please add more error handling"

    # Verify feedback in audit metadata
    call_args = mock_audit_service.log_event.call_args
    assert call_args.kwargs["metadata"]["feedback"] == "Please add more error handling"


@pytest.mark.asyncio
async def test_reject_artifact_with_regeneration(
    mock_uow, mock_audit_service, sample_task, draft_artifact
):
    """AC-1.3.1 + regeneration: Rejection triggers new pipeline run"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=draft_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
    mock_uow.artifacts.update = AsyncMock(return_value=draft_artifact)

    new_pipeline_run = PipelineRun(
        id="new-run-id",
        task_id="task-123",
        tenant_id="tenant-789",
        status=PipelineStatus.running,
    )
    mock_uow.pipeline_runs.create = AsyncMock(return_value=new_pipeline_run)

    use_case = RejectArtifactUseCase(
        mock_uow,
        tenant_id="tenant-789",
        user_id="user-123",
        audit_service=mock_audit_service,
    )

    request = RejectArtifactRequestDTO(
        feedback="Needs improvement",
        regenerate=True,
    )

    # Act
    result = await use_case.execute("artifact-1", request)

    # Assert
    assert result.is_ok()
    assert result.value.new_pipeline_run_id == "new-run-id"

    # Verify pipeline run was created
    mock_uow.pipeline_runs.create.assert_called_once()


@pytest.mark.asyncio
async def test_reject_artifact_already_rejected(
    mock_uow, mock_audit_service, sample_task, rejected_artifact
):
    """AC-1.3.3: Cannot reject already rejected artifact"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=rejected_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)

    use_case = RejectArtifactUseCase(
        mock_uow,
        tenant_id="tenant-789",
        user_id="user-123",
        audit_service=mock_audit_service,
    )

    request = RejectArtifactRequestDTO(regenerate=False)

    # Act
    result = await use_case.execute("artifact-2", request)

    # Assert
    assert result.is_err()
    assert result.error.code == "ALREADY_REJECTED"
    mock_uow.artifacts.update.assert_not_called()


@pytest.mark.asyncio
async def test_reject_artifact_approved(
    mock_uow, mock_audit_service, sample_task, approved_artifact
):
    """Cannot reject approved artifact"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=approved_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)

    use_case = RejectArtifactUseCase(
        mock_uow,
        tenant_id="tenant-789",
        user_id="user-123",
        audit_service=mock_audit_service,
    )

    request = RejectArtifactRequestDTO(regenerate=False)

    # Act
    result = await use_case.execute("artifact-3", request)

    # Assert
    assert result.is_err()
    assert result.error.code == "CANNOT_REJECT_APPROVED"


@pytest.mark.asyncio
async def test_reject_artifact_not_found(mock_uow, mock_audit_service):
    """Artifact not found returns error"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=None)

    use_case = RejectArtifactUseCase(
        mock_uow,
        tenant_id="tenant-789",
        user_id="user-123",
        audit_service=mock_audit_service,
    )

    request = RejectArtifactRequestDTO(regenerate=False)

    # Act
    result = await use_case.execute("nonexistent-artifact", request)

    # Assert
    assert result.is_err()
    assert result.error.code == "ARTIFACT_NOT_FOUND"
