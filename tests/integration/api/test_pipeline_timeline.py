import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession
from src.domain.project import Project
from src.domain.task import Task
from src.domain.pipeline_run import PipelineRun
from src.domain.pipeline_step import PipelineStep
from src.domain.enums import (
    ProjectStatus,
    TaskStatus,
    PipelineRunStatus,
    PipelineStepStatus,
    StepType,
)
from datetime import datetime


@pytest.mark.asyncio
async def test_get_pipeline_timeline_success(client: AsyncClient, db_session: AsyncSession):
    """Test GET /tasks/{id}/pipeline endpoint returns pipeline timeline"""
    # Arrange - Create project, task, pipeline run, and steps directly in DB
    # Use same tenant_id as client fixture provides via get_current_user override
    tenant_id = "test-tenant-id"

    # Create project
    project = Project(
        id="project-pipeline-1",
        tenant_id=tenant_id,
        name="Test Project",
        description="Test",
        status=ProjectStatus.active,
    )
    db_session.add(project)

    # Create task
    task = Task(
        id="task-pipeline-1",
        tenant_id=tenant_id,
        project_id=project.id,
        title="Test Task",
        input_spec={"requirement": "Build something"},
        status=TaskStatus.running,
    )
    db_session.add(task)
    await db_session.flush()  # Flush to ensure task exists before pipeline_run references it

    # Create pipeline run
    pipeline_run = PipelineRun(
        id="run-pipeline-1",
        task_id=task.id,
        tenant_id=tenant_id,
        status=PipelineRunStatus.running,
        started_at=datetime(2025, 1, 1, 10, 0, 0),
    )
    db_session.add(pipeline_run)

    # Create pipeline steps
    step1 = PipelineStep(
        id="step-pipeline-1",
        pipeline_run_id=pipeline_run.id,
        step_number=1,
        step_name="validate_input",
        step_type=StepType.ANALYSIS,
        status=PipelineStepStatus.completed,
        started_at=datetime(2025, 1, 1, 10, 0, 0),
        completed_at=datetime(2025, 1, 1, 10, 1, 0),
        output={"valid": True},
    )
    db_session.add(step1)

    step2 = PipelineStep(
        id="step-pipeline-2",
        pipeline_run_id=pipeline_run.id,
        step_number=2,
        step_name="generate_prd",
        step_type=StepType.USER_STORIES,
        status=PipelineStepStatus.running,
        started_at=datetime(2025, 1, 1, 10, 1, 0),
    )
    db_session.add(step2)

    # Store IDs before commit to avoid lazy loading issues
    task_id = task.id
    pipeline_run_id = pipeline_run.id

    await db_session.commit()

    # Act
    response = await client.get(f"/tasks/{task_id}/pipeline?tenant_id={tenant_id}")

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == pipeline_run_id  # DTO uses 'id' not 'pipeline_run_id'
    assert data["task_id"] == task_id
    assert data["status"] == "running"
    assert data["started_at"] == "2025-01-01T10:00:00"
    assert data["completed_at"] is None
    assert data["error_message"] is None
    assert len(data["steps"]) == 2

    # Verify step 1
    assert data["steps"][0]["step_number"] == 1
    assert data["steps"][0]["step_name"] == "validate_input"
    assert data["steps"][0]["status"] == "completed"
    assert data["steps"][0]["output"] == {"valid": True}

    # Verify step 2
    assert data["steps"][1]["step_number"] == 2
    assert data["steps"][1]["step_name"] == "generate_prd"
    assert data["steps"][1]["status"] == "running"


@pytest.mark.asyncio
async def test_get_pipeline_timeline_task_not_found(client: AsyncClient):
    """Test GET /tasks/{id}/pipeline with non-existent task returns 404"""
    # Act
    response = await client.get("/tasks/non-existent-task/pipeline?tenant_id=tenant-123")

    # Assert
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "TASK_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_pipeline_timeline_no_pipeline_run(
    client: AsyncClient, db_session: AsyncSession
):
    """Test GET /tasks/{id}/pipeline when task has no pipeline run returns 404"""
    # Arrange - Create project and task without pipeline run
    # Use same tenant_id as client fixture provides via get_current_user override
    tenant_id = "test-tenant-id"

    project = Project(
        id="project-no-run",
        tenant_id=tenant_id,
        name="Test Project",
        status=ProjectStatus.active,
    )
    db_session.add(project)

    task = Task(
        id="task-no-run",
        tenant_id=tenant_id,
        project_id=project.id,
        title="Test Task",
        input_spec={"requirement": "Build something"},
        status=TaskStatus.draft,
    )
    db_session.add(task)

    # Store ID before commit
    task_id = task.id

    await db_session.commit()

    # Act
    response = await client.get(f"/tasks/{task_id}/pipeline?tenant_id={tenant_id}")

    # Assert
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NO_PIPELINE_RUN"


@pytest.mark.asyncio
async def test_get_pipeline_timeline_specific_run_id(
    client: AsyncClient, db_session: AsyncSession
):
    """Test GET /tasks/{id}/pipeline with specific run_id parameter"""
    # Arrange - Create project, task, and TWO pipeline runs
    # Use same tenant_id as client fixture provides via get_current_user override
    tenant_id = "test-tenant-id"

    project = Project(
        id="project-specific-run",
        tenant_id=tenant_id,
        name="Test Project",
        status=ProjectStatus.active,
    )
    db_session.add(project)

    task = Task(
        id="task-specific-run",
        tenant_id=tenant_id,
        project_id=project.id,
        title="Test Task",
        input_spec={"requirement": "Build something"},
        status=TaskStatus.completed,
    )
    db_session.add(task)
    await db_session.flush()  # Flush to ensure task exists before pipeline_run references it

    # First run (older)
    pipeline_run_1 = PipelineRun(
        id="run-specific-1",
        task_id=task.id,
        tenant_id=tenant_id,
        status=PipelineRunStatus.completed,
        started_at=datetime(2025, 1, 1, 9, 0, 0),
        completed_at=datetime(2025, 1, 1, 9, 5, 0),
    )
    db_session.add(pipeline_run_1)

    # Second run (newer)
    pipeline_run_2 = PipelineRun(
        id="run-specific-2",
        task_id=task.id,
        tenant_id=tenant_id,
        status=PipelineRunStatus.completed,
        started_at=datetime(2025, 1, 1, 10, 0, 0),
        completed_at=datetime(2025, 1, 1, 10, 5, 0),
    )
    db_session.add(pipeline_run_2)

    # Store IDs before commit
    task_id = task.id
    run_1_id = pipeline_run_1.id

    await db_session.commit()

    # Act - Request the first (older) run specifically
    response = await client.get(
        f"/tasks/{task_id}/pipeline?tenant_id={tenant_id}&run_id={run_1_id}"
    )

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == run_1_id  # DTO uses 'id' not 'pipeline_run_id'
    assert data["started_at"] == "2025-01-01T09:00:00"
    assert data["completed_at"] == "2025-01-01T09:05:00"


@pytest.mark.asyncio
async def test_get_pipeline_timeline_with_failed_step(
    client: AsyncClient, db_session: AsyncSession
):
    """Test GET /tasks/{id}/pipeline shows failed step with error message"""
    # Arrange - Use same tenant_id as client fixture provides via get_current_user override
    tenant_id = "test-tenant-id"

    project = Project(
        id="project-failed",
        tenant_id=tenant_id,
        name="Test Project",
        status=ProjectStatus.active,
    )
    db_session.add(project)

    task = Task(
        id="task-failed",
        tenant_id=tenant_id,
        project_id=project.id,
        title="Test Task",
        input_spec={"requirement": "Build something"},
        status=TaskStatus.failed,
    )
    db_session.add(task)
    await db_session.flush()  # Flush to ensure task exists before pipeline_run references it

    pipeline_run = PipelineRun(
        id="run-failed",
        task_id=task.id,
        tenant_id=tenant_id,
        status=PipelineRunStatus.failed,
        started_at=datetime(2025, 1, 1, 10, 0, 0),
        completed_at=datetime(2025, 1, 1, 10, 2, 0),
        error_message="Pipeline failed at step 2",
    )
    db_session.add(pipeline_run)

    step1 = PipelineStep(
        id="step-failed-1",
        pipeline_run_id=pipeline_run.id,
        step_number=1,
        step_name="validate_input",
        step_type=StepType.ANALYSIS,
        status=PipelineStepStatus.completed,
        started_at=datetime(2025, 1, 1, 10, 0, 0),
        completed_at=datetime(2025, 1, 1, 10, 1, 0),
    )
    db_session.add(step1)

    step2 = PipelineStep(
        id="step-failed-2",
        pipeline_run_id=pipeline_run.id,
        step_number=2,
        step_name="generate_prd",
        step_type=StepType.USER_STORIES,
        status=PipelineStepStatus.failed,
        started_at=datetime(2025, 1, 1, 10, 1, 0),
        completed_at=datetime(2025, 1, 1, 10, 2, 0),
        error_message="Invalid input specification",
    )
    db_session.add(step2)

    # Store ID before commit
    task_id = task.id

    await db_session.commit()

    # Act
    response = await client.get(f"/tasks/{task_id}/pipeline?tenant_id={tenant_id}")

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "failed"
    assert data["error_message"] == "Pipeline failed at step 2"
    assert len(data["steps"]) == 2
    assert data["steps"][1]["status"] == "failed"
    assert data["steps"][1]["error_message"] == "Invalid input specification"


@pytest.mark.asyncio
async def test_get_pipeline_timeline_tenant_isolation(
    client: AsyncClient, db_session: AsyncSession
):
    """Test that users cannot access pipeline timelines from other tenants"""
    # Arrange - Create task for tenant A
    tenant_a = "tenant-a"
    tenant_b = "tenant-b"

    project = Project(
        id="project-tenant-a",
        tenant_id=tenant_a,
        name="Tenant A Project",
        status=ProjectStatus.active,
    )
    db_session.add(project)

    task = Task(
        id="task-tenant-a",
        tenant_id=tenant_a,
        project_id=project.id,
        title="Tenant A Task",
        input_spec={"requirement": "Build something"},
        status=TaskStatus.running,
    )
    db_session.add(task)
    await db_session.flush()  # Flush to ensure task exists before pipeline_run references it

    pipeline_run = PipelineRun(
        id="run-tenant-a",
        task_id=task.id,
        tenant_id=tenant_a,
        status=PipelineRunStatus.running,
        started_at=datetime(2025, 1, 1, 10, 0, 0),
    )
    db_session.add(pipeline_run)

    # Store ID before commit
    task_id = task.id

    await db_session.commit()

    # Act - Try to access with tenant B credentials
    response = await client.get(f"/tasks/{task_id}/pipeline?tenant_id={tenant_b}")

    # Assert - Should get 404 (not 403) because repository returns None
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "TASK_NOT_FOUND"
