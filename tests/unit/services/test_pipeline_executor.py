import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from src.app.services.pipeline_executor import PipelineExecutor
from src.domain import Task, PipelineRun, PipelineStep
from src.domain.enums import (
    TaskStatus,
    PipelineRunStatus,
    PipelineStepStatus,
    ArtifactType,
    StepType,
)


@pytest.fixture
def mock_task_repo():
    return AsyncMock()


@pytest.fixture
def mock_pipeline_run_repo():
    return AsyncMock()


@pytest.fixture
def mock_pipeline_step_repo():
    return AsyncMock()


@pytest.fixture
def mock_audit_service():
    return AsyncMock()


@pytest.fixture
def mock_artifact_service():
    return AsyncMock()


@pytest.fixture
async def success_step_handler():
    """Handler that always succeeds"""

    async def handler(context, tenant_id):
        return {"step_output": "success", "data": "test_data"}

    return handler


@pytest.fixture
async def failing_step_handler():
    """Handler that always fails"""

    async def handler(context, tenant_id):
        raise ValueError("Handler intentionally failed")

    return handler


@pytest.fixture
def queued_task():
    """Create a task in queued status"""
    task = Task(
        id="task-123",
        tenant_id="tenant-123",
        project_id="project-123",
        title="Test Task",
        input_spec={"requirement": "Build something"},
        status=TaskStatus.queued,
    )
    return task


@pytest.mark.asyncio
async def test_execute_pipeline_success(
    queued_task,
    mock_task_repo,
    mock_pipeline_run_repo,
    mock_pipeline_step_repo,
    mock_audit_service,
    success_step_handler,
):
    """Test successful pipeline execution with all steps completing"""
    # Arrange
    step_handlers = {
        "validate_input": success_step_handler,
        "generate_prd": success_step_handler,
        "generate_stories": success_step_handler,
        "review_output": success_step_handler,
    }

    # Mock pipeline run creation
    mock_pipeline_run = PipelineRun(
        id="run-123",
        task_id=queued_task.id,
        tenant_id=queued_task.tenant_id,
        status=PipelineRunStatus.running,
    )
    mock_pipeline_run_repo.create.return_value = mock_pipeline_run

    # Mock pipeline step creation
    created_steps = []
    for i, step_def in enumerate(PipelineExecutor.PIPELINE_STEPS):
        step = PipelineStep(
            id=f"step-{i+1}",
            pipeline_run_id=mock_pipeline_run.id,
            step_number=step_def["step_number"],
            step_name=step_def["step_name"],
            step_type=step_def["step_type"],
            status=PipelineStepStatus.pending,
        )
        created_steps.append(step)

    mock_pipeline_step_repo.create.side_effect = created_steps

    executor = PipelineExecutor(
        task_repo=mock_task_repo,
        pipeline_run_repo=mock_pipeline_run_repo,
        pipeline_step_repo=mock_pipeline_step_repo,
        audit_service=mock_audit_service,
        step_handlers=step_handlers,
    )

    # Act
    await executor.execute(queued_task)

    # Assert
    # Verify task was updated to running then completed
    assert mock_task_repo.update.call_count >= 2
    final_task_update = mock_task_repo.update.call_args_list[-1][0][0]
    assert final_task_update.status == TaskStatus.completed

    # Verify pipeline run was created and completed
    mock_pipeline_run_repo.create.assert_called_once()
    mock_pipeline_run_repo.update.assert_called_once()

    # Verify all 4 steps were created
    assert mock_pipeline_step_repo.create.call_count == 4

    # Verify all 4 steps were updated (pending → running → completed)
    assert mock_pipeline_step_repo.update.call_count == 8  # 2 updates per step

    # Verify audit events
    assert mock_audit_service.log_event.call_count == 2  # pipeline_started, pipeline_completed

    # Check pipeline_started event
    started_call = mock_audit_service.log_event.call_args_list[0]
    assert started_call[1]["event_type"] == "pipeline_started"

    # Check pipeline_completed event
    completed_call = mock_audit_service.log_event.call_args_list[1]
    assert completed_call[1]["event_type"] == "pipeline_completed"


@pytest.mark.asyncio
async def test_execute_pipeline_step_failure(
    queued_task,
    mock_task_repo,
    mock_pipeline_run_repo,
    mock_pipeline_step_repo,
    mock_audit_service,
    success_step_handler,
    failing_step_handler,
):
    """Test pipeline execution when a step fails"""
    # Arrange - step 2 fails
    step_handlers = {
        "validate_input": success_step_handler,
        "generate_prd": failing_step_handler,  # This will fail
        "generate_stories": success_step_handler,
        "review_output": success_step_handler,
    }

    mock_pipeline_run = PipelineRun(
        id="run-123",
        task_id=queued_task.id,
        tenant_id=queued_task.tenant_id,
        status=PipelineRunStatus.running,
    )
    mock_pipeline_run_repo.create.return_value = mock_pipeline_run

    # Mock step creation
    created_steps = []
    for i, step_def in enumerate(PipelineExecutor.PIPELINE_STEPS):
        step = PipelineStep(
            id=f"step-{i+1}",
            pipeline_run_id=mock_pipeline_run.id,
            step_number=step_def["step_number"],
            step_name=step_def["step_name"],
            step_type=step_def["step_type"],
            status=PipelineStepStatus.pending,
        )
        created_steps.append(step)

    mock_pipeline_step_repo.create.side_effect = created_steps

    executor = PipelineExecutor(
        task_repo=mock_task_repo,
        pipeline_run_repo=mock_pipeline_run_repo,
        pipeline_step_repo=mock_pipeline_step_repo,
        audit_service=mock_audit_service,
        step_handlers=step_handlers,
    )

    # Act & Assert
    with pytest.raises(Exception) as exc_info:
        await executor.execute(queued_task)

    assert "generate_prd failed" in str(exc_info.value)

    # Verify task was marked as failed
    final_task_update = mock_task_repo.update.call_args_list[-1][0][0]
    assert final_task_update.status == TaskStatus.failed

    # Verify pipeline run was marked as failed
    assert mock_pipeline_run_repo.update.call_count >= 1

    # Verify pipeline_failed audit event
    failed_calls = [
        call for call in mock_audit_service.log_event.call_args_list
        if call[1]["event_type"] == "pipeline_failed"
    ]
    assert len(failed_calls) == 1


@pytest.mark.asyncio
async def test_execute_pipeline_invalid_task_status(
    mock_task_repo,
    mock_pipeline_run_repo,
    mock_pipeline_step_repo,
    mock_audit_service,
):
    """Test that pipeline execution fails if task is not in queued status"""
    # Arrange
    task = Task(
        id="task-123",
        tenant_id="tenant-123",
        project_id="project-123",
        title="Test Task",
        input_spec={"requirement": "Test"},
        status=TaskStatus.draft,  # Wrong status!
    )

    executor = PipelineExecutor(
        task_repo=mock_task_repo,
        pipeline_run_repo=mock_pipeline_run_repo,
        pipeline_step_repo=mock_pipeline_step_repo,
        audit_service=mock_audit_service,
        step_handlers={},
    )

    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        await executor.execute(task)

    assert "must be in 'queued' status" in str(exc_info.value)

    # Verify no pipeline run was created
    mock_pipeline_run_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_execute_step_no_handler(
    queued_task,
    mock_task_repo,
    mock_pipeline_run_repo,
    mock_pipeline_step_repo,
    mock_audit_service,
):
    """Test that execution fails if a step handler is missing"""
    # Arrange - no handlers provided
    step_handlers = {}  # Missing all handlers!

    mock_pipeline_run = PipelineRun(
        id="run-123",
        task_id=queued_task.id,
        tenant_id=queued_task.tenant_id,
        status=PipelineRunStatus.running,
    )
    mock_pipeline_run_repo.create.return_value = mock_pipeline_run

    # Mock step creation
    step = PipelineStep(
        id="step-1",
        pipeline_run_id=mock_pipeline_run.id,
        step_number=1,
        step_name="validate_input",
        step_type=StepType.ANALYSIS,
        status=PipelineStepStatus.pending,
    )
    mock_pipeline_step_repo.create.return_value = step

    executor = PipelineExecutor(
        task_repo=mock_task_repo,
        pipeline_run_repo=mock_pipeline_run_repo,
        pipeline_step_repo=mock_pipeline_step_repo,
        audit_service=mock_audit_service,
        step_handlers=step_handlers,
    )

    # Act & Assert
    with pytest.raises(Exception) as exc_info:
        await executor.execute(queued_task)

    assert "No handler found for step" in str(exc_info.value)

    # Verify task was marked as failed
    final_task_update = mock_task_repo.update.call_args_list[-1][0][0]
    assert final_task_update.status == TaskStatus.failed


@pytest.mark.asyncio
async def test_pipeline_task_state_transitions(
    queued_task,
    mock_task_repo,
    mock_pipeline_run_repo,
    mock_pipeline_step_repo,
    mock_audit_service,
    success_step_handler,
):
    """Test that task transitions correctly: queued → running → completed"""
    # Arrange
    step_handlers = {
        "validate_input": success_step_handler,
        "generate_prd": success_step_handler,
        "generate_stories": success_step_handler,
        "review_output": success_step_handler,
    }

    mock_pipeline_run = PipelineRun(
        id="run-123",
        task_id=queued_task.id,
        tenant_id=queued_task.tenant_id,
    )
    mock_pipeline_run_repo.create.return_value = mock_pipeline_run

    # Mock step creation
    created_steps = []
    for i, step_def in enumerate(PipelineExecutor.PIPELINE_STEPS):
        step = PipelineStep(
            id=f"step-{i+1}",
            pipeline_run_id=mock_pipeline_run.id,
            step_number=step_def["step_number"],
            step_name=step_def["step_name"],
            step_type=step_def["step_type"],
            status=PipelineStepStatus.pending,
        )
        created_steps.append(step)

    mock_pipeline_step_repo.create.side_effect = created_steps

    # Capture task status at time of each update
    captured_statuses = []

    async def capture_task_status(task):
        captured_statuses.append(task.status)

    mock_task_repo.update.side_effect = capture_task_status

    executor = PipelineExecutor(
        task_repo=mock_task_repo,
        pipeline_run_repo=mock_pipeline_run_repo,
        pipeline_step_repo=mock_pipeline_step_repo,
        audit_service=mock_audit_service,
        step_handlers=step_handlers,
    )

    # Act
    await executor.execute(queued_task)

    # Assert task state transitions
    # First update: queued → running
    assert captured_statuses[0] == TaskStatus.running

    # Last update: running → completed
    assert captured_statuses[-1] == TaskStatus.completed


@pytest.mark.asyncio
async def test_pipeline_step_state_transitions(
    queued_task,
    mock_task_repo,
    mock_pipeline_run_repo,
    mock_pipeline_step_repo,
    mock_audit_service,
    success_step_handler,
):
    """Test that steps transition correctly: pending → running → completed"""
    # Arrange
    step_handlers = {
        "validate_input": success_step_handler,
        "generate_prd": success_step_handler,
        "generate_stories": success_step_handler,
        "review_output": success_step_handler,
    }

    mock_pipeline_run = PipelineRun(
        id="run-123",
        task_id=queued_task.id,
        tenant_id=queued_task.tenant_id,
    )
    mock_pipeline_run_repo.create.return_value = mock_pipeline_run

    # Mock step creation
    created_steps = []
    for i, step_def in enumerate(PipelineExecutor.PIPELINE_STEPS):
        step = PipelineStep(
            id=f"step-{i+1}",
            pipeline_run_id=mock_pipeline_run.id,
            step_number=step_def["step_number"],
            step_name=step_def["step_name"],
            step_type=step_def["step_type"],
            status=PipelineStepStatus.pending,
        )
        created_steps.append(step)

    mock_pipeline_step_repo.create.side_effect = created_steps

    # Capture step status at time of each update
    captured_step_statuses = []

    async def capture_step_status(step):
        captured_step_statuses.append(step.status)

    mock_pipeline_step_repo.update.side_effect = capture_step_status

    executor = PipelineExecutor(
        task_repo=mock_task_repo,
        pipeline_run_repo=mock_pipeline_run_repo,
        pipeline_step_repo=mock_pipeline_step_repo,
        audit_service=mock_audit_service,
        step_handlers=step_handlers,
    )

    # Act
    await executor.execute(queued_task)

    # Assert step state transitions
    # Each step should have 2 updates: pending → running, running → completed
    # 4 steps * 2 updates = 8 total
    assert len(captured_step_statuses) == 8

    # Check first step's transitions
    assert captured_step_statuses[0] == PipelineStepStatus.running  # Step 1: pending → running
    assert captured_step_statuses[1] == PipelineStepStatus.completed  # Step 1: running → completed


@pytest.mark.asyncio
async def test_pipeline_context_accumulation(
    queued_task,
    mock_task_repo,
    mock_pipeline_run_repo,
    mock_pipeline_step_repo,
    mock_audit_service,
):
    """Test that context accumulates across steps"""
    # Arrange
    step_1_output = {"validation_passed": True}
    step_2_output = {"prd_generated": True}

    async def step_1_handler(context, tenant_id):
        assert "input_spec" in context
        return step_1_output

    async def step_2_handler(context, tenant_id):
        # Should have input_spec + step_1 output
        assert "input_spec" in context
        assert "validation_passed" in context
        return step_2_output

    async def step_3_handler(context, tenant_id):
        # Should have all previous outputs
        assert "input_spec" in context
        assert "validation_passed" in context
        assert "prd_generated" in context
        return {"stories_generated": True}

    async def step_4_handler(context, tenant_id):
        # Should have all previous outputs
        assert "input_spec" in context
        assert "validation_passed" in context
        assert "prd_generated" in context
        assert "stories_generated" in context
        return {"review_passed": True}

    step_handlers = {
        "validate_input": step_1_handler,
        "generate_prd": step_2_handler,
        "generate_stories": step_3_handler,
        "review_output": step_4_handler,
    }

    mock_pipeline_run = PipelineRun(
        id="run-123",
        task_id=queued_task.id,
        tenant_id=queued_task.tenant_id,
    )
    mock_pipeline_run_repo.create.return_value = mock_pipeline_run

    # Mock step creation
    created_steps = []
    for i, step_def in enumerate(PipelineExecutor.PIPELINE_STEPS):
        step = PipelineStep(
            id=f"step-{i+1}",
            pipeline_run_id=mock_pipeline_run.id,
            step_number=step_def["step_number"],
            step_name=step_def["step_name"],
            step_type=step_def["step_type"],
            status=PipelineStepStatus.pending,
        )
        created_steps.append(step)

    mock_pipeline_step_repo.create.side_effect = created_steps

    executor = PipelineExecutor(
        task_repo=mock_task_repo,
        pipeline_run_repo=mock_pipeline_run_repo,
        pipeline_step_repo=mock_pipeline_step_repo,
        audit_service=mock_audit_service,
        step_handlers=step_handlers,
    )

    # Act
    await executor.execute(queued_task)

    # Assert - if handlers didn't get correct context, they would raise assertion errors
    # So successful execution means context was properly accumulated
    assert True


@pytest.mark.asyncio
async def test_pipeline_with_artifact_service(
    queued_task,
    mock_task_repo,
    mock_pipeline_run_repo,
    mock_pipeline_step_repo,
    mock_audit_service,
    mock_artifact_service,
):
    """Test that pipeline creates artifacts when artifact service is provided"""
    # Arrange
    async def prd_handler(context, tenant_id):
        return {"prd_content": "PRD content here", "prd_generated": True}

    async def stories_handler(context, tenant_id):
        return {"stories_content": "Stories content here", "stories_generated": True}

    async def other_handler(context, tenant_id):
        return {"result": "success"}

    step_handlers = {
        "validate_input": other_handler,
        "generate_prd": prd_handler,  # Should create artifact
        "generate_stories": stories_handler,  # Should create artifact
        "review_output": other_handler,
    }

    mock_pipeline_run = PipelineRun(
        id="run-123",
        task_id=queued_task.id,
        tenant_id=queued_task.tenant_id,
    )
    mock_pipeline_run_repo.create.return_value = mock_pipeline_run
    mock_pipeline_run_repo.get_by_id.return_value = mock_pipeline_run

    # Mock step creation
    created_steps = []
    for i, step_def in enumerate(PipelineExecutor.PIPELINE_STEPS):
        step = PipelineStep(
            id=f"step-{i+1}",
            pipeline_run_id=mock_pipeline_run.id,
            step_number=step_def["step_number"],
            step_name=step_def["step_name"],
            step_type=step_def["step_type"],
            status=PipelineStepStatus.pending,
        )
        created_steps.append(step)

    mock_pipeline_step_repo.create.side_effect = created_steps

    executor = PipelineExecutor(
        task_repo=mock_task_repo,
        pipeline_run_repo=mock_pipeline_run_repo,
        pipeline_step_repo=mock_pipeline_step_repo,
        audit_service=mock_audit_service,
        step_handlers=step_handlers,
        artifact_service=mock_artifact_service,
    )

    # Act
    await executor.execute(queued_task)

    # Assert - artifacts should be created for step 2 and step 3
    assert mock_artifact_service.create_artifact.call_count == 2

    # Check first artifact (step 2: PRD)
    first_call = mock_artifact_service.create_artifact.call_args_list[0]
    assert first_call[1]["artifact_type"] == ArtifactType.document
    assert "PRD content" in first_call[1]["content"]

    # Check second artifact (step 3: Stories)
    second_call = mock_artifact_service.create_artifact.call_args_list[1]
    assert second_call[1]["artifact_type"] == ArtifactType.code
    assert "Stories content" in second_call[1]["content"]
