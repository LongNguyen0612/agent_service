"""Unit tests for ReplayPipeline use case (UC-25) - Story 2.4"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from libs.result import Error
from src.domain.enums import PipelineStatus, StepStatus, StepType
from src.domain.pipeline_run import PipelineRun
from src.domain.pipeline_step import PipelineStepRun
from src.domain.task import Task, TaskStatus
from src.app.use_cases.pipeline.replay_pipeline import ReplayPipelineUseCase
from src.app.use_cases.pipeline.dtos import ReplayPipelineCommandDTO, ReplayPipelineResponseDTO


@pytest.fixture
def mock_uow():
    """Create a mock unit of work with pipeline_runs, tasks, and pipeline_steps repositories"""
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()

    # Create mock repositories
    uow.pipeline_runs = MagicMock()
    uow.tasks = MagicMock()
    uow.pipeline_steps = MagicMock()

    return uow


@pytest.fixture
def mock_audit_service():
    """Create a mock audit service"""
    service = MagicMock()
    service.log_event = AsyncMock()
    return service


@pytest.fixture
def replay_pipeline_use_case(mock_uow, mock_audit_service):
    """Create ReplayPipelineUseCase instance with mocked dependencies"""
    return ReplayPipelineUseCase(uow=mock_uow, audit_service=mock_audit_service)


@pytest.fixture
def sample_pipeline_run():
    """Create a sample pipeline run for testing"""
    return PipelineRun(
        id="pipeline_123",
        task_id="task_456",
        tenant_id="tenant_789",
        status=PipelineStatus.completed,
        current_step=4,
    )


@pytest.fixture
def sample_task():
    """Create a sample task for testing"""
    return Task(
        id="task_456",
        project_id="project_abc",
        tenant_id="tenant_789",
        title="Test Task",
        input_spec={"description": "Build an API"},
        status=TaskStatus.completed,
    )


@pytest.fixture
def sample_steps():
    """Create sample pipeline steps for testing"""
    return [
        PipelineStepRun(
            id="step_1",
            pipeline_run_id="pipeline_123",
            step_number=1,
            step_name="Analysis",
            step_type=StepType.ANALYSIS,
            status=StepStatus.completed,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        ),
        PipelineStepRun(
            id="step_2",
            pipeline_run_id="pipeline_123",
            step_number=2,
            step_name="User Stories",
            step_type=StepType.USER_STORIES,
            status=StepStatus.completed,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        ),
        PipelineStepRun(
            id="step_3",
            pipeline_run_id="pipeline_123",
            step_number=3,
            step_name="Code Skeleton",
            step_type=StepType.CODE_SKELETON,
            status=StepStatus.failed,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            error_message="LLM timeout",
        ),
    ]


@pytest.mark.asyncio
class TestReplayPipelineUseCase:
    """Test suite for ReplayPipeline use case - AC-2.4.1 and AC-2.4.2"""

    async def test_replay_from_beginning_success(
        self, replay_pipeline_use_case, mock_uow, mock_audit_service, sample_pipeline_run, sample_task
    ):
        """
        Test AC-2.4.2: Replay entire pipeline from beginning.

        GIVEN completed pipeline run
        WHEN POST /pipeline/{id}/replay without step_id
        THEN new pipeline run starts from beginning
        AND original task inputs are used
        """
        # Arrange
        tenant_id = "tenant_789"
        pipeline_id = "pipeline_123"

        mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=sample_pipeline_run)
        mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)

        new_run = PipelineRun(
            id="new_pipeline_456",
            task_id=sample_pipeline_run.task_id,
            tenant_id=tenant_id,
            status=PipelineStatus.running,
            current_step=1,
        )
        mock_uow.pipeline_runs.create = AsyncMock(return_value=new_run)

        command = ReplayPipelineCommandDTO(
            pipeline_run_id=pipeline_id,
            tenant_id=tenant_id,
            from_step_id=None,  # Replay from beginning
            preserve_approved_artifacts=True,
        )

        # Act
        result = await replay_pipeline_use_case.execute(command)

        # Assert
        assert result.is_ok()
        dto = result.value
        assert isinstance(dto, ReplayPipelineResponseDTO)
        assert dto.new_pipeline_run_id == "new_pipeline_456"
        assert dto.status == "running"
        assert dto.started_from_step == "STEP_1"

        # Verify repositories were called correctly
        mock_uow.pipeline_runs.get_by_id.assert_called_once_with(pipeline_id)
        mock_uow.tasks.get_by_id.assert_called_once_with(
            sample_pipeline_run.task_id, tenant_id
        )
        mock_uow.pipeline_runs.create.assert_called_once()
        mock_uow.commit.assert_called_once()

        # Verify audit event was logged
        mock_audit_service.log_event.assert_called_once()
        call_kwargs = mock_audit_service.log_event.call_args.kwargs
        assert call_kwargs["event_type"] == "pipeline_replayed"
        assert call_kwargs["tenant_id"] == tenant_id
        assert call_kwargs["resource_type"] == "pipeline_run"
        assert call_kwargs["resource_id"] == "new_pipeline_456"
        assert call_kwargs["metadata"]["original_pipeline_run_id"] == pipeline_id
        assert call_kwargs["metadata"]["from_step_id"] is None
        assert call_kwargs["metadata"]["started_from_step"] == "STEP_1"

    async def test_replay_from_specific_step_success(
        self,
        replay_pipeline_use_case,
        mock_uow,
        mock_audit_service,
        sample_pipeline_run,
        sample_task,
        sample_steps,
    ):
        """
        Test AC-2.4.1: Replay from a specific failed step.

        GIVEN pipeline run with failed step
        WHEN POST /pipeline/{id}/replay with step_id
        THEN new execution starts from that step
        AND previous inputs are preserved
        """
        # Arrange
        tenant_id = "tenant_789"
        pipeline_id = "pipeline_123"
        from_step_id = "step_3"  # Replay from the failed Code Skeleton step

        mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=sample_pipeline_run)
        mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
        mock_uow.pipeline_steps.get_by_pipeline_run_id = AsyncMock(return_value=sample_steps)

        new_run = PipelineRun(
            id="new_pipeline_789",
            task_id=sample_pipeline_run.task_id,
            tenant_id=tenant_id,
            status=PipelineStatus.running,
            current_step=3,
        )
        mock_uow.pipeline_runs.create = AsyncMock(return_value=new_run)

        command = ReplayPipelineCommandDTO(
            pipeline_run_id=pipeline_id,
            tenant_id=tenant_id,
            from_step_id=from_step_id,
            preserve_approved_artifacts=True,
        )

        # Act
        result = await replay_pipeline_use_case.execute(command)

        # Assert
        assert result.is_ok()
        dto = result.value
        assert dto.new_pipeline_run_id == "new_pipeline_789"
        assert dto.status == "running"
        assert dto.started_from_step == "CODE SKELETON"  # step_name.upper()

        # Verify steps were fetched
        mock_uow.pipeline_steps.get_by_pipeline_run_id.assert_called_once_with(pipeline_id)

        # Verify the new pipeline run was created with correct starting step
        mock_uow.pipeline_runs.create.assert_called_once()
        created_run = mock_uow.pipeline_runs.create.call_args[0][0]
        assert created_run.current_step == 3  # Step 3 is Code Skeleton

        # Verify audit event includes from_step_id
        call_kwargs = mock_audit_service.log_event.call_args.kwargs
        assert call_kwargs["metadata"]["from_step_id"] == from_step_id
        assert call_kwargs["metadata"]["started_from_step"] == "CODE SKELETON"

    async def test_pipeline_run_not_found_error(
        self, replay_pipeline_use_case, mock_uow
    ):
        """
        Test error case: Pipeline run does not exist.

        GIVEN nonexistent pipeline run ID
        WHEN POST /pipeline/{id}/replay
        THEN return PIPELINE_RUN_NOT_FOUND error
        """
        # Arrange
        mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=None)

        command = ReplayPipelineCommandDTO(
            pipeline_run_id="nonexistent_pipeline",
            tenant_id="tenant_123",
            from_step_id=None,
        )

        # Act
        result = await replay_pipeline_use_case.execute(command)

        # Assert
        assert result.is_err()
        error = result.error
        assert error.code == "PIPELINE_RUN_NOT_FOUND"
        assert "not found" in error.message.lower()

        # Verify no pipeline was created
        mock_uow.pipeline_runs.create.assert_not_called()
        mock_uow.commit.assert_not_called()

    async def test_tenant_isolation_wrong_tenant_returns_not_found(
        self, replay_pipeline_use_case, mock_uow, sample_pipeline_run
    ):
        """
        Test security: Wrong tenant cannot access pipeline.

        GIVEN pipeline belonging to tenant_A
        WHEN tenant_B tries to replay the pipeline
        THEN return PIPELINE_RUN_NOT_FOUND error (not UNAUTHORIZED for security)
        """
        # Arrange
        wrong_tenant_id = "tenant_wrong"

        mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=sample_pipeline_run)
        # Task lookup with wrong tenant returns None
        mock_uow.tasks.get_by_id = AsyncMock(return_value=None)

        command = ReplayPipelineCommandDTO(
            pipeline_run_id="pipeline_123",
            tenant_id=wrong_tenant_id,
            from_step_id=None,
        )

        # Act
        result = await replay_pipeline_use_case.execute(command)

        # Assert
        assert result.is_err()
        error = result.error
        assert error.code == "PIPELINE_RUN_NOT_FOUND"  # Same error for security

        # Verify task lookup was called with wrong tenant
        mock_uow.tasks.get_by_id.assert_called_once_with(
            sample_pipeline_run.task_id, wrong_tenant_id
        )

        # Verify no pipeline was created
        mock_uow.pipeline_runs.create.assert_not_called()

    async def test_audit_event_logged_on_successful_replay(
        self, replay_pipeline_use_case, mock_uow, mock_audit_service, sample_pipeline_run, sample_task
    ):
        """
        Test that audit event is logged when replay is successful.

        GIVEN valid replay request
        WHEN replay succeeds
        THEN audit event is logged with correct metadata
        """
        # Arrange
        tenant_id = "tenant_789"
        pipeline_id = "pipeline_123"

        mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=sample_pipeline_run)
        mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)

        new_run = PipelineRun(
            id="new_pipeline_audit_test",
            task_id=sample_pipeline_run.task_id,
            tenant_id=tenant_id,
            status=PipelineStatus.running,
            current_step=1,
        )
        mock_uow.pipeline_runs.create = AsyncMock(return_value=new_run)

        command = ReplayPipelineCommandDTO(
            pipeline_run_id=pipeline_id,
            tenant_id=tenant_id,
            from_step_id=None,
            preserve_approved_artifacts=False,
        )

        # Act
        result = await replay_pipeline_use_case.execute(command)

        # Assert
        assert result.is_ok()
        mock_audit_service.log_event.assert_called_once()

        call_kwargs = mock_audit_service.log_event.call_args.kwargs
        assert call_kwargs["event_type"] == "pipeline_replayed"
        assert call_kwargs["tenant_id"] == tenant_id
        assert call_kwargs["user_id"] is None
        assert call_kwargs["resource_type"] == "pipeline_run"
        assert call_kwargs["resource_id"] == "new_pipeline_audit_test"
        assert call_kwargs["metadata"]["original_pipeline_run_id"] == pipeline_id
        assert call_kwargs["metadata"]["preserve_approved_artifacts"] is False
        assert call_kwargs["metadata"]["started_from_step"] == "STEP_1"

    async def test_replay_with_nonexistent_step_id_starts_from_beginning(
        self,
        replay_pipeline_use_case,
        mock_uow,
        mock_audit_service,
        sample_pipeline_run,
        sample_task,
        sample_steps,
    ):
        """
        Test edge case: from_step_id that doesn't exist in the pipeline.

        GIVEN from_step_id that does not match any step in the pipeline
        WHEN replay is requested
        THEN pipeline starts from step 1 (fallback behavior)
        """
        # Arrange
        tenant_id = "tenant_789"
        pipeline_id = "pipeline_123"
        nonexistent_step_id = "step_nonexistent"

        mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=sample_pipeline_run)
        mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
        mock_uow.pipeline_steps.get_by_pipeline_run_id = AsyncMock(return_value=sample_steps)

        new_run = PipelineRun(
            id="new_pipeline_fallback",
            task_id=sample_pipeline_run.task_id,
            tenant_id=tenant_id,
            status=PipelineStatus.running,
            current_step=1,
        )
        mock_uow.pipeline_runs.create = AsyncMock(return_value=new_run)

        command = ReplayPipelineCommandDTO(
            pipeline_run_id=pipeline_id,
            tenant_id=tenant_id,
            from_step_id=nonexistent_step_id,
            preserve_approved_artifacts=True,
        )

        # Act
        result = await replay_pipeline_use_case.execute(command)

        # Assert
        assert result.is_ok()
        dto = result.value
        # Falls back to STEP_1 when step not found
        assert dto.started_from_step == "STEP_1"

        # Verify the created pipeline starts from step 1
        created_run = mock_uow.pipeline_runs.create.call_args[0][0]
        assert created_run.current_step == 1

    async def test_replay_failed_pipeline_run(
        self, replay_pipeline_use_case, mock_uow, mock_audit_service, sample_task
    ):
        """
        Test replaying a failed pipeline run.

        GIVEN a failed pipeline run
        WHEN replay is requested
        THEN new pipeline run is created successfully
        """
        # Arrange
        tenant_id = "tenant_789"
        failed_pipeline = PipelineRun(
            id="failed_pipeline",
            task_id="task_456",
            tenant_id=tenant_id,
            status=PipelineStatus.failed,
            current_step=2,
            error_message="Step failed due to API timeout",
        )

        mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=failed_pipeline)
        mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)

        new_run = PipelineRun(
            id="new_pipeline_from_failed",
            task_id=failed_pipeline.task_id,
            tenant_id=tenant_id,
            status=PipelineStatus.running,
            current_step=1,
        )
        mock_uow.pipeline_runs.create = AsyncMock(return_value=new_run)

        command = ReplayPipelineCommandDTO(
            pipeline_run_id="failed_pipeline",
            tenant_id=tenant_id,
            from_step_id=None,
        )

        # Act
        result = await replay_pipeline_use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.new_pipeline_run_id == "new_pipeline_from_failed"
        assert result.value.status == "running"

    async def test_replay_with_preserve_approved_artifacts_false(
        self, replay_pipeline_use_case, mock_uow, mock_audit_service, sample_pipeline_run, sample_task
    ):
        """
        Test replay with preserve_approved_artifacts=False.

        GIVEN replay request with preserve_approved_artifacts=False
        WHEN replay is executed
        THEN the metadata reflects the setting correctly
        """
        # Arrange
        tenant_id = "tenant_789"

        mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=sample_pipeline_run)
        mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)

        new_run = PipelineRun(
            id="new_pipeline_no_preserve",
            task_id=sample_pipeline_run.task_id,
            tenant_id=tenant_id,
            status=PipelineStatus.running,
            current_step=1,
        )
        mock_uow.pipeline_runs.create = AsyncMock(return_value=new_run)

        command = ReplayPipelineCommandDTO(
            pipeline_run_id="pipeline_123",
            tenant_id=tenant_id,
            from_step_id=None,
            preserve_approved_artifacts=False,
        )

        # Act
        result = await replay_pipeline_use_case.execute(command)

        # Assert
        assert result.is_ok()

        call_kwargs = mock_audit_service.log_event.call_args.kwargs
        assert call_kwargs["metadata"]["preserve_approved_artifacts"] is False

    async def test_replay_creates_new_pipeline_with_running_status(
        self, replay_pipeline_use_case, mock_uow, mock_audit_service, sample_pipeline_run, sample_task
    ):
        """
        Test that new pipeline is always created with 'running' status.

        GIVEN any valid replay request
        WHEN replay is executed
        THEN new pipeline run has status 'running'
        """
        # Arrange
        tenant_id = "tenant_789"

        mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=sample_pipeline_run)
        mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)

        # Capture what gets created
        captured_pipeline = None

        async def capture_create(pipeline):
            nonlocal captured_pipeline
            captured_pipeline = pipeline
            return pipeline

        mock_uow.pipeline_runs.create = capture_create

        command = ReplayPipelineCommandDTO(
            pipeline_run_id="pipeline_123",
            tenant_id=tenant_id,
        )

        # Act
        result = await replay_pipeline_use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert captured_pipeline is not None
        assert captured_pipeline.status == PipelineStatus.running
        assert captured_pipeline.task_id == sample_pipeline_run.task_id
        assert captured_pipeline.tenant_id == tenant_id


@pytest.mark.asyncio
class TestReplayPipelineEdgeCases:
    """Additional edge case tests for ReplayPipeline use case"""

    async def test_replay_from_first_step(
        self,
        replay_pipeline_use_case,
        mock_uow,
        mock_audit_service,
        sample_pipeline_run,
        sample_task,
        sample_steps,
    ):
        """
        Test replaying from the first step explicitly.

        GIVEN from_step_id pointing to step 1
        WHEN replay is executed
        THEN new pipeline starts from step 1 with ANALYSIS as started_from_step
        """
        # Arrange
        tenant_id = "tenant_789"
        from_step_id = "step_1"

        mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=sample_pipeline_run)
        mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
        mock_uow.pipeline_steps.get_by_pipeline_run_id = AsyncMock(return_value=sample_steps)

        new_run = PipelineRun(
            id="new_pipeline_from_step1",
            task_id=sample_pipeline_run.task_id,
            tenant_id=tenant_id,
            status=PipelineStatus.running,
            current_step=1,
        )
        mock_uow.pipeline_runs.create = AsyncMock(return_value=new_run)

        command = ReplayPipelineCommandDTO(
            pipeline_run_id="pipeline_123",
            tenant_id=tenant_id,
            from_step_id=from_step_id,
        )

        # Act
        result = await replay_pipeline_use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.started_from_step == "ANALYSIS"

        created_run = mock_uow.pipeline_runs.create.call_args[0][0]
        assert created_run.current_step == 1

    async def test_replay_from_second_step(
        self,
        replay_pipeline_use_case,
        mock_uow,
        mock_audit_service,
        sample_pipeline_run,
        sample_task,
        sample_steps,
    ):
        """
        Test replaying from the second step.

        GIVEN from_step_id pointing to step 2
        WHEN replay is executed
        THEN new pipeline starts from step 2 with USER STORIES as started_from_step
        """
        # Arrange
        tenant_id = "tenant_789"
        from_step_id = "step_2"

        mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=sample_pipeline_run)
        mock_uow.tasks.get_by_id = AsyncMock(return_value=sample_task)
        mock_uow.pipeline_steps.get_by_pipeline_run_id = AsyncMock(return_value=sample_steps)

        new_run = PipelineRun(
            id="new_pipeline_from_step2",
            task_id=sample_pipeline_run.task_id,
            tenant_id=tenant_id,
            status=PipelineStatus.running,
            current_step=2,
        )
        mock_uow.pipeline_runs.create = AsyncMock(return_value=new_run)

        command = ReplayPipelineCommandDTO(
            pipeline_run_id="pipeline_123",
            tenant_id=tenant_id,
            from_step_id=from_step_id,
        )

        # Act
        result = await replay_pipeline_use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.started_from_step == "USER STORIES"

        created_run = mock_uow.pipeline_runs.create.call_args[0][0]
        assert created_run.current_step == 2
