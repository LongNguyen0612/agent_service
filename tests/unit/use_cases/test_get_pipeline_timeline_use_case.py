import pytest
from datetime import datetime
from unittest.mock import AsyncMock
from src.app.use_cases.pipelines import GetPipelineTimelineUseCase
from src.domain.pipeline_run import PipelineRun
from src.domain.pipeline_step import PipelineStepRun
from src.domain.task import Task
from src.domain.enums import PipelineStatus, StepStatus, TaskStatus, StepType


@pytest.mark.asyncio
async def test_get_pipeline_timeline_success_default_run(mock_uow):
    """Test successful retrieval of most recent pipeline run"""
    # Arrange
    tenant_id = "tenant-123"
    task_id = "task-456"
    pipeline_run_id = "run-789"

    # Mock task
    mock_task = Task(
        id=task_id,
        tenant_id=tenant_id,
        project_id="project-123",
        title="Test Task",
        input_spec={"test": "data"},
        status=TaskStatus.running,
    )
    mock_uow.tasks.get_by_id = AsyncMock(return_value=mock_task)

    # Mock pipeline run
    mock_pipeline_run = PipelineRun(
        id=pipeline_run_id,
        task_id=task_id,
        tenant_id=tenant_id,
        status=PipelineStatus.running,
        started_at=datetime(2025, 1, 1, 10, 0, 0),
        completed_at=None,
    )
    mock_uow.pipeline_runs.get_by_task_id = AsyncMock(return_value=mock_pipeline_run)

    # Mock pipeline steps
    mock_steps = [
        PipelineStepRun(
            id="step-1",
            pipeline_run_id=pipeline_run_id,
            step_number=1,
            step_name="Analysis Step",
            step_type=StepType.ANALYSIS,
            status=StepStatus.completed,
            started_at=datetime(2025, 1, 1, 10, 0, 0),
            completed_at=datetime(2025, 1, 1, 10, 1, 0),
        ),
        PipelineStepRun(
            id="step-2",
            pipeline_run_id=pipeline_run_id,
            step_number=2,
            step_name="User Stories Step",
            step_type=StepType.USER_STORIES,
            status=StepStatus.running,
            started_at=datetime(2025, 1, 1, 10, 1, 0),
            completed_at=None,
        ),
    ]
    mock_uow.pipeline_steps.get_by_pipeline_run_id = AsyncMock(return_value=mock_steps)

    use_case = GetPipelineTimelineUseCase(uow=mock_uow, tenant_id=tenant_id)

    # Act
    result = await use_case.execute(task_id)

    # Assert
    assert result.is_ok()
    response = result.value
    assert response.id == pipeline_run_id
    assert response.task_id == task_id
    assert response.status == "running"
    assert response.started_at == datetime(2025, 1, 1, 10, 0, 0)
    assert response.completed_at is None
    assert response.error_message is None
    assert len(response.steps) == 2
    assert response.steps[0].step_number == 1
    assert response.steps[0].step_name == "Analysis Step"
    assert response.steps[0].status == "completed"
    assert response.steps[1].step_number == 2
    assert response.steps[1].step_name == "User Stories Step"
    assert response.steps[1].status == "running"

    # Verify repository calls
    mock_uow.tasks.get_by_id.assert_called_once_with(task_id, tenant_id)
    mock_uow.pipeline_runs.get_by_task_id.assert_called_once_with(task_id)
    mock_uow.pipeline_steps.get_by_pipeline_run_id.assert_called_once_with(pipeline_run_id)


@pytest.mark.asyncio
async def test_get_pipeline_timeline_success_specific_run(mock_uow):
    """Test successful retrieval of specific pipeline run"""
    # Arrange
    tenant_id = "tenant-123"
    task_id = "task-456"
    pipeline_run_id = "run-specific"


    # Mock task
    mock_task = Task(
        id=task_id,
        tenant_id=tenant_id,
        project_id="project-123",
        title="Test Task",
        input_spec={"test": "data"},
        status=TaskStatus.completed,
    )
    mock_uow.tasks.get_by_id = AsyncMock(return_value=mock_task)

    # Mock pipeline run
    mock_pipeline_run = PipelineRun(
        id=pipeline_run_id,
        task_id=task_id,
        tenant_id=tenant_id,
        status=PipelineStatus.completed,
        started_at=datetime(2025, 1, 1, 10, 0, 0),
        completed_at=datetime(2025, 1, 1, 10, 5, 0),
        error_message=None,
    )
    mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=mock_pipeline_run)

    # Mock pipeline steps (empty for simplicity)
    mock_uow.pipeline_steps.get_by_pipeline_run_id = AsyncMock(return_value=[])

    use_case = GetPipelineTimelineUseCase(uow=mock_uow, tenant_id=tenant_id)

    # Act
    result = await use_case.execute(task_id, run_id=pipeline_run_id)

    # Assert
    assert result.is_ok()
    response = result.value
    assert response.id == pipeline_run_id
    assert response.status == "completed"
    assert response.completed_at == datetime(2025, 1, 1, 10, 5, 0)
    assert len(response.steps) == 0

    # Verify repository calls
    mock_uow.pipeline_runs.get_by_id.assert_called_once_with(pipeline_run_id)


@pytest.mark.asyncio
async def test_get_pipeline_timeline_task_not_found(mock_uow):
    """Test error when task does not exist"""
    # Arrange
    tenant_id = "tenant-123"
    task_id = "non-existent-task"


    mock_uow.tasks.get_by_id = AsyncMock(return_value=None)

    use_case = GetPipelineTimelineUseCase(uow=mock_uow, tenant_id=tenant_id)

    # Act
    result = await use_case.execute(task_id)

    # Assert
    assert result.is_err()
    assert result.error.code == "TASK_NOT_FOUND"
    assert result.error.message == "Task not found"


@pytest.mark.asyncio
async def test_get_pipeline_timeline_no_pipeline_run(mock_uow):
    """Test error when no pipeline run exists for task"""
    # Arrange
    tenant_id = "tenant-123"
    task_id = "task-456"


    # Mock task
    mock_task = Task(
        id=task_id,
        tenant_id=tenant_id,
        project_id="project-123",
        title="Test Task",
        input_spec={"test": "data"},
        status=TaskStatus.draft,
    )
    mock_uow.tasks.get_by_id = AsyncMock(return_value=mock_task)

    # No pipeline run found
    mock_uow.pipeline_runs.get_by_task_id = AsyncMock(return_value=None)

    use_case = GetPipelineTimelineUseCase(uow=mock_uow, tenant_id=tenant_id)

    # Act
    result = await use_case.execute(task_id)

    # Assert
    assert result.is_err()
    assert result.error.code == "NO_PIPELINE_RUN"
    assert result.error.message == "No pipeline run found for this task"


@pytest.mark.asyncio
async def test_get_pipeline_timeline_pipeline_run_not_found(mock_uow):
    """Test error when specific pipeline run ID does not exist"""
    # Arrange
    tenant_id = "tenant-123"
    task_id = "task-456"
    pipeline_run_id = "non-existent-run"


    # Mock task
    mock_task = Task(
        id=task_id,
        tenant_id=tenant_id,
        project_id="project-123",
        title="Test Task",
        input_spec={"test": "data"},
        status=TaskStatus.running,
    )
    mock_uow.tasks.get_by_id = AsyncMock(return_value=mock_task)

    # Pipeline run not found
    mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=None)

    use_case = GetPipelineTimelineUseCase(uow=mock_uow, tenant_id=tenant_id)

    # Act
    result = await use_case.execute(task_id, run_id=pipeline_run_id)

    # Assert
    assert result.is_err()
    assert result.error.code == "PIPELINE_RUN_NOT_FOUND"
    assert result.error.message == "Pipeline run not found"


@pytest.mark.asyncio
async def test_get_pipeline_timeline_invalid_pipeline_run(mock_uow):
    """Test error when pipeline run does not belong to the task"""
    # Arrange
    tenant_id = "tenant-123"
    task_id = "task-456"
    pipeline_run_id = "run-789"


    # Mock task
    mock_task = Task(
        id=task_id,
        tenant_id=tenant_id,
        project_id="project-123",
        title="Test Task",
        input_spec={"test": "data"},
        status=TaskStatus.running,
    )
    mock_uow.tasks.get_by_id = AsyncMock(return_value=mock_task)

    # Mock pipeline run with different task_id
    mock_pipeline_run = PipelineRun(
        id=pipeline_run_id,
        task_id="different-task-id",
        tenant_id=tenant_id,
        status=PipelineStatus.running,
        started_at=datetime(2025, 1, 1, 10, 0, 0),
    )
    mock_uow.pipeline_runs.get_by_id = AsyncMock(return_value=mock_pipeline_run)

    use_case = GetPipelineTimelineUseCase(uow=mock_uow, tenant_id=tenant_id)

    # Act
    result = await use_case.execute(task_id, run_id=pipeline_run_id)

    # Assert
    assert result.is_err()
    assert result.error.code == "INVALID_PIPELINE_RUN"
    assert result.error.message == "Pipeline run does not belong to this task"


@pytest.mark.asyncio
async def test_get_pipeline_timeline_with_failed_step(mock_uow):
    """Test pipeline timeline with a failed step"""
    # Arrange
    tenant_id = "tenant-123"
    task_id = "task-456"
    pipeline_run_id = "run-789"


    # Mock task
    mock_task = Task(
        id=task_id,
        tenant_id=tenant_id,
        project_id="project-123",
        title="Test Task",
        input_spec={"test": "data"},
        status=TaskStatus.failed,
    )
    mock_uow.tasks.get_by_id = AsyncMock(return_value=mock_task)

    # Mock failed pipeline run
    mock_pipeline_run = PipelineRun(
        id=pipeline_run_id,
        task_id=task_id,
        tenant_id=tenant_id,
        status=PipelineStatus.failed,
        started_at=datetime(2025, 1, 1, 10, 0, 0),
        completed_at=datetime(2025, 1, 1, 10, 2, 0),
    )
    mock_uow.pipeline_runs.get_by_task_id = AsyncMock(return_value=mock_pipeline_run)

    # Mock pipeline steps with failure
    mock_steps = [
        PipelineStepRun(
            id="step-1",
            pipeline_run_id=pipeline_run_id,
            step_number=1,
            step_name="Analysis Step",
            step_type=StepType.ANALYSIS,
            status=StepStatus.completed,
            started_at=datetime(2025, 1, 1, 10, 0, 0),
            completed_at=datetime(2025, 1, 1, 10, 1, 0),
        ),
        PipelineStepRun(
            id="step-2",
            pipeline_run_id=pipeline_run_id,
            step_number=2,
            step_name="User Stories Step",
            step_type=StepType.USER_STORIES,
            status=StepStatus.failed,
            started_at=datetime(2025, 1, 1, 10, 1, 0),
            completed_at=datetime(2025, 1, 1, 10, 2, 0),
        ),
    ]
    mock_uow.pipeline_steps.get_by_pipeline_run_id = AsyncMock(return_value=mock_steps)

    use_case = GetPipelineTimelineUseCase(uow=mock_uow, tenant_id=tenant_id)

    # Act
    result = await use_case.execute(task_id)

    # Assert
    assert result.is_ok()
    response = result.value
    assert response.status == "failed"
    assert response.error_message is None  # PipelineRun doesn't have error_message field
    assert len(response.steps) == 2
    assert response.steps[1].status == "failed"
    assert response.steps[1].error_message is None  # PipelineStepRun doesn't have error_message field
