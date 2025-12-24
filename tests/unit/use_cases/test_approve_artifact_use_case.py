"""
Unit tests for ApproveArtifactUseCase (UC-28)
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from src.app.use_cases.artifacts import ApproveArtifactUseCase
from src.domain.artifact import Artifact
from src.domain.pipeline_run import PipelineRun
from src.domain.enums import ArtifactType, ArtifactStatus, PipelineStatus, PauseReason
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
    uow.pipeline_runs.get_by_id = AsyncMock(return_value=None)
    uow.pipeline_runs.update = AsyncMock()
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
def approved_artifact():
    """Create an already approved artifact"""
    return Artifact(
        id="artifact-2",
        task_id="task-123",
        pipeline_run_id="run-1",
        step_run_id="step-1",
        artifact_type=ArtifactType.CODE_FILES,
        status=ArtifactStatus.approved,
        version=1,
        created_at=datetime.utcnow(),
        approved_at=datetime.utcnow(),
    )


@pytest.fixture
def rejected_artifact():
    """Create a rejected artifact"""
    return Artifact(
        id="artifact-3",
        task_id="task-123",
        pipeline_run_id="run-1",
        step_run_id="step-1",
        artifact_type=ArtifactType.CODE_FILES,
        status=ArtifactStatus.rejected,
        version=1,
        created_at=datetime.utcnow(),
        rejected_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_approve_artifact_success(mock_uow, mock_audit_service, sample_task, draft_artifact):
    """AC-1.2.1: Successfully approve a draft artifact"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=draft_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
    mock_uow.artifacts.update = AsyncMock(return_value=draft_artifact)

    use_case = ApproveArtifactUseCase(
        mock_uow,
        tenant_id="tenant-789",
        user_id="user-123",
        audit_service=mock_audit_service,
    )

    # Act
    result = await use_case.execute("artifact-1")

    # Assert
    assert result.is_ok()
    assert result.value.id == "artifact-1"
    assert result.value.status == "approved"
    assert result.value.approved_at is not None

    # Verify artifact was updated
    mock_uow.artifacts.update.assert_called_once()
    mock_uow.commit.assert_called_once()

    # Verify audit event was logged
    mock_audit_service.log_event.assert_called_once()
    call_args = mock_audit_service.log_event.call_args
    assert call_args.kwargs["event_type"] == "artifact_approved"
    assert call_args.kwargs["resource_type"] == "artifact"
    assert call_args.kwargs["resource_id"] == "artifact-1"


@pytest.mark.asyncio
async def test_approve_artifact_already_approved(
    mock_uow, mock_audit_service, sample_task, approved_artifact
):
    """AC-1.2.2: Cannot approve already approved artifact"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=approved_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)

    use_case = ApproveArtifactUseCase(
        mock_uow,
        tenant_id="tenant-789",
        user_id="user-123",
        audit_service=mock_audit_service,
    )

    # Act
    result = await use_case.execute("artifact-2")

    # Assert
    assert result.is_err()
    assert result.error.code == "ALREADY_APPROVED"
    mock_uow.artifacts.update.assert_not_called()
    mock_audit_service.log_event.assert_not_called()


@pytest.mark.asyncio
async def test_approve_artifact_rejected(
    mock_uow, mock_audit_service, sample_task, rejected_artifact
):
    """AC-1.2.3: Cannot approve rejected artifact"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=rejected_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)

    use_case = ApproveArtifactUseCase(
        mock_uow,
        tenant_id="tenant-789",
        user_id="user-123",
        audit_service=mock_audit_service,
    )

    # Act
    result = await use_case.execute("artifact-3")

    # Assert
    assert result.is_err()
    assert result.error.code == "CANNOT_APPROVE_REJECTED"
    mock_uow.artifacts.update.assert_not_called()


@pytest.mark.asyncio
async def test_approve_artifact_not_found(mock_uow, mock_audit_service):
    """Artifact not found returns error"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=None)

    use_case = ApproveArtifactUseCase(
        mock_uow,
        tenant_id="tenant-789",
        user_id="user-123",
        audit_service=mock_audit_service,
    )

    # Act
    result = await use_case.execute("nonexistent-artifact")

    # Assert
    assert result.is_err()
    assert result.error.code == "ARTIFACT_NOT_FOUND"


@pytest.mark.asyncio
async def test_approve_artifact_tenant_isolation(
    mock_uow, mock_audit_service, draft_artifact
):
    """Tenant isolation - artifact from other tenant returns not found"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=draft_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=None)  # Task not found for this tenant

    use_case = ApproveArtifactUseCase(
        mock_uow,
        tenant_id="different-tenant",
        user_id="user-123",
        audit_service=mock_audit_service,
    )

    # Act
    result = await use_case.execute("artifact-1")

    # Assert
    assert result.is_err()
    assert result.error.code == "ARTIFACT_NOT_FOUND"
    mock_uow.artifacts.update.assert_not_called()


# --- Pipeline Resume Tests (AC-2.3.1, AC-2.3.2) ---


@pytest.fixture
def paused_pipeline_awaiting_approval():
    """Create a paused pipeline with AWAITING_USER_APPROVAL reason"""
    pipeline = PipelineRun(
        id="run-1",
        task_id="task-123",
        tenant_id="tenant-789",
        status=PipelineStatus.paused,
        pause_reasons=[PauseReason.AWAITING_USER_APPROVAL.value],
        current_step=2,
    )
    return pipeline


@pytest.fixture
def paused_pipeline_multiple_reasons():
    """Create a paused pipeline with multiple pause reasons"""
    pipeline = PipelineRun(
        id="run-1",
        task_id="task-123",
        tenant_id="tenant-789",
        status=PipelineStatus.paused,
        pause_reasons=[
            PauseReason.AWAITING_USER_APPROVAL.value,
            PauseReason.INSUFFICIENT_CREDIT.value,
        ],
        current_step=2,
    )
    return pipeline


@pytest.fixture
def running_pipeline():
    """Create a running pipeline (not paused)"""
    pipeline = PipelineRun(
        id="run-1",
        task_id="task-123",
        tenant_id="tenant-789",
        status=PipelineStatus.running,
        pause_reasons=[],
        current_step=2,
    )
    return pipeline


@pytest.mark.asyncio
async def test_approve_artifact_resumes_paused_pipeline(
    mock_uow, mock_audit_service, sample_task, draft_artifact, paused_pipeline_awaiting_approval
):
    """AC-2.3.2: Pipeline resumes when artifact is approved and AWAITING_USER_APPROVAL is the only reason"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=draft_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
    mock_uow.artifacts.update = AsyncMock(return_value=draft_artifact)
    mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=paused_pipeline_awaiting_approval)

    use_case = ApproveArtifactUseCase(
        mock_uow,
        tenant_id="tenant-789",
        user_id="user-123",
        audit_service=mock_audit_service,
    )

    # Act
    result = await use_case.execute("artifact-1")

    # Assert
    assert result.is_ok()
    assert result.value.pipeline_run_id == "run-1"
    assert result.value.pipeline_resumed is True

    # Verify pipeline was updated
    mock_uow.pipeline_runs.update.assert_called_once()
    updated_pipeline = mock_uow.pipeline_runs.update.call_args[0][0]
    assert updated_pipeline.status == PipelineStatus.running
    assert updated_pipeline.paused_at is None
    assert len(updated_pipeline.pause_reasons) == 0

    # Verify pipeline resume audit event was logged
    assert mock_audit_service.log_event.call_count == 2
    resume_call = mock_audit_service.log_event.call_args_list[1]
    assert resume_call.kwargs["event_type"] == "pipeline_resumed"
    assert resume_call.kwargs["resource_type"] == "pipeline_run"
    assert resume_call.kwargs["resource_id"] == "run-1"


@pytest.mark.asyncio
async def test_approve_artifact_keeps_pipeline_paused_with_other_reasons(
    mock_uow, mock_audit_service, sample_task, draft_artifact, paused_pipeline_multiple_reasons
):
    """AC-2.3.2: Pipeline stays paused if other pause reasons exist"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=draft_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
    mock_uow.artifacts.update = AsyncMock(return_value=draft_artifact)
    mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=paused_pipeline_multiple_reasons)

    use_case = ApproveArtifactUseCase(
        mock_uow,
        tenant_id="tenant-789",
        user_id="user-123",
        audit_service=mock_audit_service,
    )

    # Act
    result = await use_case.execute("artifact-1")

    # Assert
    assert result.is_ok()
    assert result.value.pipeline_run_id == "run-1"
    assert result.value.pipeline_resumed is False  # Not resumed due to other reasons

    # Verify pipeline was updated but remains paused
    mock_uow.pipeline_runs.update.assert_called_once()
    updated_pipeline = mock_uow.pipeline_runs.update.call_args[0][0]
    assert updated_pipeline.status == PipelineStatus.paused
    assert PauseReason.AWAITING_USER_APPROVAL.value not in updated_pipeline.pause_reasons
    assert PauseReason.INSUFFICIENT_CREDIT.value in updated_pipeline.pause_reasons

    # Only artifact_approved audit event (no pipeline_resumed)
    assert mock_audit_service.log_event.call_count == 1
    assert mock_audit_service.log_event.call_args.kwargs["event_type"] == "artifact_approved"


@pytest.mark.asyncio
async def test_approve_artifact_no_pipeline_to_resume(
    mock_uow, mock_audit_service, sample_task, draft_artifact, running_pipeline
):
    """AC-2.3.2: Running pipeline is not affected by approval"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=draft_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
    mock_uow.artifacts.update = AsyncMock(return_value=draft_artifact)
    mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=running_pipeline)

    use_case = ApproveArtifactUseCase(
        mock_uow,
        tenant_id="tenant-789",
        user_id="user-123",
        audit_service=mock_audit_service,
    )

    # Act
    result = await use_case.execute("artifact-1")

    # Assert
    assert result.is_ok()
    assert result.value.pipeline_run_id is None
    assert result.value.pipeline_resumed is False

    # Pipeline should not be updated
    mock_uow.pipeline_runs.update.assert_not_called()


@pytest.mark.asyncio
async def test_approve_artifact_triggers_websocket_notification(
    mock_uow, mock_audit_service, sample_task, draft_artifact, paused_pipeline_awaiting_approval
):
    """AC-2.3.2: WebSocket notification is sent on approval"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=draft_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
    mock_uow.artifacts.update = AsyncMock(return_value=draft_artifact)
    mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=paused_pipeline_awaiting_approval)

    mock_websocket_callback = AsyncMock()

    use_case = ApproveArtifactUseCase(
        mock_uow,
        tenant_id="tenant-789",
        user_id="user-123",
        audit_service=mock_audit_service,
        websocket_callback=mock_websocket_callback,
    )

    # Act
    result = await use_case.execute("artifact-1")

    # Assert
    assert result.is_ok()

    # Verify WebSocket callback was invoked
    mock_websocket_callback.assert_called_once()
    call_args = mock_websocket_callback.call_args
    assert call_args[0][0] == "tenant-789"  # tenant_id
    message = call_args[0][1]
    assert message["event"] == "artifact:approved"
    assert message["data"]["artifact_id"] == "artifact-1"
    assert message["data"]["pipeline_run_id"] == "run-1"
    assert message["data"]["pipeline_resumed"] is True
    assert message["data"]["task_id"] == "task-123"


@pytest.mark.asyncio
async def test_approve_artifact_without_websocket_callback(
    mock_uow, mock_audit_service, sample_task, draft_artifact
):
    """Approval works correctly without WebSocket callback"""
    # Arrange
    mock_uow.artifacts.get_by_id = AsyncMock(return_value=draft_artifact)
    mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
    mock_uow.artifacts.update = AsyncMock(return_value=draft_artifact)
    mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=None)

    use_case = ApproveArtifactUseCase(
        mock_uow,
        tenant_id="tenant-789",
        user_id="user-123",
        audit_service=mock_audit_service,
        # No websocket_callback provided
    )

    # Act
    result = await use_case.execute("artifact-1")

    # Assert - should complete without errors
    assert result.is_ok()
    assert result.value.id == "artifact-1"
    assert result.value.status == "approved"
