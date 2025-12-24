"""Unit tests for CancelPipeline use case - Story 2.6"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from libs.result import Error
from src.domain.enums import PipelineStatus, StepStatus
from src.domain.pipeline_run import PipelineRun
from src.domain.pipeline_step import PipelineStepRun, StepType
from src.app.use_cases.pipeline.cancel_pipeline import CancelPipeline
from src.app.use_cases.pipeline.dtos import CancelPipelineCommandDTO


@pytest.fixture
def mock_pipeline_repo():
    return MagicMock()


@pytest.fixture
def mock_step_repo():
    return MagicMock()


@pytest.fixture
def mock_audit_service():
    service = MagicMock()
    service.log_event = AsyncMock()
    return service


@pytest.fixture
def cancel_pipeline_use_case(mock_pipeline_repo, mock_step_repo, mock_audit_service):
    return CancelPipeline(
        pipeline_run_repository=mock_pipeline_repo,
        step_run_repository=mock_step_repo,
        audit_service=mock_audit_service,
    )


@pytest.mark.asyncio
class TestCancelPipeline:
    """Test suite for CancelPipeline use case - AC-2.6.1 through AC-2.6.5"""

    async def test_cancel_running_pipeline_success(
        self, cancel_pipeline_use_case, mock_pipeline_repo, mock_step_repo, mock_audit_service
    ):
        """Test AC-2.6.1: Successfully cancel a running pipeline"""
        # Arrange
        pipeline_id = "pipeline_123"
        tenant_id = "tenant_456"
        user_id = "user_789"

        pipeline = PipelineRun(
            id=pipeline_id,
            task_id="task_123",
            tenant_id=tenant_id,
            status=PipelineStatus.running,
            current_step=2,
        )

        completed_step = PipelineStepRun(
            id="step_1",
            pipeline_run_id=pipeline_id,
            step_number=1,
            step_name="Analysis Step",
            step_type=StepType.ANALYSIS,
            status=StepStatus.completed,
            started_at=datetime.utcnow(),
        )

        running_step = PipelineStepRun(
            id="step_2",
            pipeline_run_id=pipeline_id,
            step_number=2,
            step_name="User Stories Step",
            step_type=StepType.USER_STORIES,
            status=StepStatus.running,
            started_at=datetime.utcnow(),
        )

        mock_pipeline_repo.get_by_id = AsyncMock(return_value=pipeline)
        mock_step_repo.get_by_pipeline_run_id = AsyncMock(
            return_value=[completed_step, running_step]
        )
        mock_step_repo.update = AsyncMock(return_value=running_step)
        mock_pipeline_repo.update = AsyncMock(return_value=pipeline)

        command = CancelPipelineCommandDTO(
            pipeline_run_id=pipeline_id,
            tenant_id=tenant_id,
            user_id=user_id,
            reason="User requested cancellation",
        )

        # Act
        result = await cancel_pipeline_use_case.execute(command)

        # Assert
        assert result.is_ok()
        dto = result.value
        assert dto.pipeline_run_id == pipeline_id
        assert dto.previous_status == "running"
        assert dto.new_status == "cancelled"
        assert dto.steps_completed == 1
        assert dto.steps_cancelled == 1
        assert "preserved" in dto.message.lower()

        # Verify pipeline status was updated
        mock_pipeline_repo.update.assert_called_once()
        updated_pipeline = mock_pipeline_repo.update.call_args[0][0]
        assert updated_pipeline.status == PipelineStatus.cancelled

        # Verify running step was cancelled
        mock_step_repo.update.assert_called_once()

        # Verify audit event was logged
        mock_audit_service.log_event.assert_called_once()
        call_args = mock_audit_service.log_event.call_args
        assert call_args.kwargs["event_type"] == "pipeline_cancelled"
        assert call_args.kwargs["tenant_id"] == tenant_id
        assert call_args.kwargs["user_id"] == user_id

    async def test_cancel_paused_pipeline_success(
        self, cancel_pipeline_use_case, mock_pipeline_repo, mock_step_repo
    ):
        """Test AC-2.6.1: Successfully cancel a paused pipeline"""
        # Arrange
        pipeline_id = "pipeline_123"
        tenant_id = "tenant_456"

        pipeline = PipelineRun(
            id=pipeline_id,
            task_id="task_123",
            tenant_id=tenant_id,
            status=PipelineStatus.paused,
            current_step=1,
        )

        mock_pipeline_repo.get_by_id = AsyncMock(return_value=pipeline)
        mock_step_repo.get_by_pipeline_run_id = AsyncMock(return_value=[])
        mock_pipeline_repo.update = AsyncMock(return_value=pipeline)

        command = CancelPipelineCommandDTO(
            pipeline_run_id=pipeline_id,
            tenant_id=tenant_id,
            user_id="user_123",
        )

        # Act
        result = await cancel_pipeline_use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.previous_status == "paused"
        assert result.value.new_status == "cancelled"

    async def test_cannot_cancel_completed_pipeline(
        self, cancel_pipeline_use_case, mock_pipeline_repo
    ):
        """Test AC-2.6.2: Cannot cancel a completed pipeline"""
        # Arrange
        pipeline_id = "pipeline_123"
        tenant_id = "tenant_456"

        pipeline = PipelineRun(
            id=pipeline_id,
            task_id="task_123",
            tenant_id=tenant_id,
            status=PipelineStatus.completed,
            current_step=4,
        )

        mock_pipeline_repo.get_by_id = AsyncMock(return_value=pipeline)

        command = CancelPipelineCommandDTO(
            pipeline_run_id=pipeline_id,
            tenant_id=tenant_id,
            user_id="user_123",
        )

        # Act
        result = await cancel_pipeline_use_case.execute(command)

        # Assert
        assert result.is_err()
        error = result.error
        assert error.code == "CANNOT_CANCEL_COMPLETED"
        assert "completed" in error.message.lower()

        # Verify no updates were made
        mock_pipeline_repo.update.assert_not_called()

    async def test_cannot_cancel_already_cancelled_pipeline(
        self, cancel_pipeline_use_case, mock_pipeline_repo
    ):
        """Test AC-2.6.2: Cannot cancel an already cancelled pipeline"""
        # Arrange
        pipeline_id = "pipeline_123"
        tenant_id = "tenant_456"

        pipeline = PipelineRun(
            id=pipeline_id,
            task_id="task_123",
            tenant_id=tenant_id,
            status=PipelineStatus.cancelled,
            current_step=2,
        )

        mock_pipeline_repo.get_by_id = AsyncMock(return_value=pipeline)

        command = CancelPipelineCommandDTO(
            pipeline_run_id=pipeline_id,
            tenant_id=tenant_id,
            user_id="user_123",
        )

        # Act
        result = await cancel_pipeline_use_case.execute(command)

        # Assert
        assert result.is_err()
        assert result.error.code == "CANNOT_CANCEL_COMPLETED"

    async def test_cancel_pipeline_not_found(
        self, cancel_pipeline_use_case, mock_pipeline_repo
    ):
        """Test error when pipeline doesn't exist"""
        # Arrange
        mock_pipeline_repo.get_by_id = AsyncMock(return_value=None)

        command = CancelPipelineCommandDTO(
            pipeline_run_id="nonexistent",
            tenant_id="tenant_123",
            user_id="user_123",
        )

        # Act
        result = await cancel_pipeline_use_case.execute(command)

        # Assert
        assert result.is_err()
        error = result.error
        assert error.code == "PIPELINE_NOT_FOUND"

    async def test_cancel_pipeline_unauthorized_tenant(
        self, cancel_pipeline_use_case, mock_pipeline_repo
    ):
        """Test cancellation by wrong tenant is rejected"""
        # Arrange
        pipeline = PipelineRun(
            id="pipeline_123",
            task_id="task_123",
            tenant_id="tenant_correct",
            status=PipelineStatus.running,
        )

        mock_pipeline_repo.get_by_id = AsyncMock(return_value=pipeline)

        command = CancelPipelineCommandDTO(
            pipeline_run_id="pipeline_123",
            tenant_id="tenant_wrong",
            user_id="user_123",
        )

        # Act
        result = await cancel_pipeline_use_case.execute(command)

        # Assert
        assert result.is_err()
        error = result.error
        assert error.code == "UNAUTHORIZED"
        assert "not authorized" in error.message.lower()

        # Verify no updates were made
        mock_pipeline_repo.update.assert_not_called()

    async def test_preserve_completed_steps(
        self, cancel_pipeline_use_case, mock_pipeline_repo, mock_step_repo
    ):
        """Test AC-2.6.3: Completed steps are preserved when pipeline is cancelled"""
        # Arrange
        pipeline_id = "pipeline_123"

        pipeline = PipelineRun(
            id=pipeline_id,
            task_id="task_123",
            tenant_id="tenant_123",
            status=PipelineStatus.running,
            current_step=3,
        )

        step1 = PipelineStepRun(
            id="step_1",
            pipeline_run_id=pipeline_id,
            step_number=1,
            step_name="Step 1",
            step_type=StepType.ANALYSIS,
            status=StepStatus.completed,
            started_at=datetime.utcnow(),
        )

        step2 = PipelineStepRun(
            id="step_2",
            pipeline_run_id=pipeline_id,
            step_number=2,
            step_name="Step 2",
            step_type=StepType.USER_STORIES,
            status=StepStatus.completed,
            started_at=datetime.utcnow(),
        )

        step3 = PipelineStepRun(
            id="step_3",
            pipeline_run_id=pipeline_id,
            step_number=3,
            step_name="Step 3",
            step_type=StepType.CODE_SKELETON,
            status=StepStatus.running,
            started_at=datetime.utcnow(),
        )

        mock_pipeline_repo.get_by_id = AsyncMock(return_value=pipeline)
        mock_step_repo.get_by_pipeline_run_id = AsyncMock(
            return_value=[step1, step2, step3]
        )
        mock_step_repo.update = AsyncMock()
        mock_pipeline_repo.update = AsyncMock(return_value=pipeline)

        command = CancelPipelineCommandDTO(
            pipeline_run_id=pipeline_id,
            tenant_id="tenant_123",
            user_id="user_123",
        )

        # Act
        result = await cancel_pipeline_use_case.execute(command)

        # Assert
        assert result.is_ok()
        dto = result.value
        assert dto.steps_completed == 2  # Two completed steps preserved
        assert dto.steps_cancelled == 1  # One running step cancelled

        # Verify only running step was updated (completed ones untouched)
        assert mock_step_repo.update.call_count == 1

    async def test_cancellation_without_audit_service(
        self, mock_pipeline_repo, mock_step_repo
    ):
        """Test cancellation works even without audit service"""
        # Arrange
        use_case = CancelPipeline(
            pipeline_run_repository=mock_pipeline_repo,
            step_run_repository=mock_step_repo,
            audit_service=None,  # No audit service
        )

        pipeline = PipelineRun(
            id="pipeline_123",
            task_id="task_123",
            tenant_id="tenant_123",
            status=PipelineStatus.running,
        )

        mock_pipeline_repo.get_by_id = AsyncMock(return_value=pipeline)
        mock_step_repo.get_by_pipeline_run_id = AsyncMock(return_value=[])
        mock_pipeline_repo.update = AsyncMock(return_value=pipeline)

        command = CancelPipelineCommandDTO(
            pipeline_run_id="pipeline_123",
            tenant_id="tenant_123",
            user_id="user_123",
        )

        # Act
        result = await use_case.execute(command)

        # Assert - should still succeed
        assert result.is_ok()

    async def test_multiple_running_steps_all_cancelled(
        self, cancel_pipeline_use_case, mock_pipeline_repo, mock_step_repo
    ):
        """Test AC-2.6.4: All running steps are cancelled"""
        # Arrange
        pipeline = PipelineRun(
            id="pipeline_123",
            task_id="task_123",
            tenant_id="tenant_123",
            status=PipelineStatus.running,
        )

        # Edge case: multiple running steps (shouldn't happen in normal flow)
        running_step1 = PipelineStepRun(
            id="step_1",
            pipeline_run_id="pipeline_123",
            step_number=1,
            step_name="Step 1",
            step_type=StepType.ANALYSIS,
            status=StepStatus.running,
            started_at=datetime.utcnow(),
        )

        running_step2 = PipelineStepRun(
            id="step_2",
            pipeline_run_id="pipeline_123",
            step_number=2,
            step_name="Step 2",
            step_type=StepType.USER_STORIES,
            status=StepStatus.running,
            started_at=datetime.utcnow(),
        )

        mock_pipeline_repo.get_by_id = AsyncMock(return_value=pipeline)
        mock_step_repo.get_by_pipeline_run_id = AsyncMock(
            return_value=[running_step1, running_step2]
        )
        mock_step_repo.update = AsyncMock()
        mock_pipeline_repo.update = AsyncMock(return_value=pipeline)

        command = CancelPipelineCommandDTO(
            pipeline_run_id="pipeline_123",
            tenant_id="tenant_123",
            user_id="user_123",
        )

        # Act
        result = await cancel_pipeline_use_case.execute(command)

        # Assert
        assert result.is_ok()
        # Both running steps should be updated
        assert mock_step_repo.update.call_count == 2
