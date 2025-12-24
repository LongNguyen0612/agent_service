"""Integration tests for ReplayPipeline (UC-25) - Story 2.4"""
import pytest
from datetime import datetime
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession
from src.domain.enums import PipelineStatus, StepStatus, StepType, TaskStatus, ProjectStatus
from src.domain.pipeline_run import PipelineRun
from src.domain.pipeline_step import PipelineStepRun
from src.domain.task import Task
from src.domain.project import Project
from src.domain.base import generate_uuid


@pytest.mark.asyncio
class TestReplayPipelineEndpoint:
    """Integration tests for POST /pipeline/{pipeline_run_id}/replay endpoint"""

    async def test_replay_entire_pipeline_from_beginning(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """
        Test AC-2.4.2: Replay entire pipeline from beginning.

        GIVEN completed pipeline run
        WHEN POST /pipeline/{id}/replay without from_step_id
        THEN new pipeline run starts from beginning
        AND returns 200 with new pipeline info
        """
        # Arrange: Create project
        project = Project(
            id=generate_uuid(),
            name="Replay Test Project",
            tenant_id="test-tenant-id",
            status=ProjectStatus.active,
        )
        db_session.add(project)
        await db_session.commit()

        # Create task
        task = Task(
            id=generate_uuid(),
            project_id=project.id,
            tenant_id="test-tenant-id",
            title="Test Task for Replay",
            input_spec={"description": "Build a REST API"},
            status=TaskStatus.completed,
        )
        db_session.add(task)
        await db_session.commit()

        # Create completed pipeline run
        pipeline = PipelineRun(
            id=generate_uuid(),
            task_id=task.id,
            tenant_id="test-tenant-id",
            status=PipelineStatus.completed,
            current_step=4,
            completed_at=datetime.utcnow(),
        )
        db_session.add(pipeline)
        await db_session.commit()

        # Act: Replay from beginning
        response = await client.post(f"/pipeline/{pipeline.id}/replay")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "new_pipeline_run_id" in data
        assert data["status"] == "running"
        assert data["started_from_step"] == "STEP_1"

        # Verify new pipeline was created in database
        from sqlmodel import select

        result = await db_session.execute(
            select(PipelineRun).where(PipelineRun.id == data["new_pipeline_run_id"])
        )
        new_pipeline = result.scalar_one()
        assert new_pipeline is not None
        assert new_pipeline.status == PipelineStatus.running
        assert new_pipeline.task_id == task.id
        assert new_pipeline.current_step == 1

    async def test_replay_from_specific_step(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """
        Test AC-2.4.1: Replay from a specific step.

        GIVEN pipeline run with failed step
        WHEN POST /pipeline/{id}/replay with from_step_id
        THEN new execution starts from that step
        """
        # Arrange: Create project
        project = Project(
            id=generate_uuid(),
            name="Step Replay Project",
            tenant_id="test-tenant-id",
            status=ProjectStatus.active,
        )
        db_session.add(project)
        await db_session.commit()

        # Create task
        task = Task(
            id=generate_uuid(),
            project_id=project.id,
            tenant_id="test-tenant-id",
            title="Step Replay Task",
            input_spec={"description": "Build a service"},
            status=TaskStatus.running,
        )
        db_session.add(task)
        await db_session.commit()

        # Create failed pipeline run
        pipeline = PipelineRun(
            id=generate_uuid(),
            task_id=task.id,
            tenant_id="test-tenant-id",
            status=PipelineStatus.failed,
            current_step=3,
        )
        db_session.add(pipeline)
        await db_session.commit()

        # Create pipeline steps
        step1 = PipelineStepRun(
            id=generate_uuid(),
            pipeline_run_id=pipeline.id,
            step_number=1,
            step_name="Analysis",
            step_type=StepType.ANALYSIS,
            status=StepStatus.completed,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        step2 = PipelineStepRun(
            id=generate_uuid(),
            pipeline_run_id=pipeline.id,
            step_number=2,
            step_name="User Stories",
            step_type=StepType.USER_STORIES,
            status=StepStatus.completed,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        step3 = PipelineStepRun(
            id=generate_uuid(),
            pipeline_run_id=pipeline.id,
            step_number=3,
            step_name="Code Skeleton",
            step_type=StepType.CODE_SKELETON,
            status=StepStatus.failed,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            error_message="API timeout during code generation",
        )
        db_session.add_all([step1, step2, step3])
        await db_session.commit()

        # Act: Replay from step 3 (the failed step)
        response = await client.post(
            f"/pipeline/{pipeline.id}/replay",
            params={"from_step_id": step3.id}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["started_from_step"] == "CODE SKELETON"

        # Verify new pipeline starts from step 3
        from sqlmodel import select

        result = await db_session.execute(
            select(PipelineRun).where(PipelineRun.id == data["new_pipeline_run_id"])
        )
        new_pipeline = result.scalar_one()
        assert new_pipeline.current_step == 3

    async def test_replay_nonexistent_pipeline_returns_404(
        self,
        client: AsyncClient,
    ):
        """
        Test error: Pipeline run not found returns 404.

        GIVEN nonexistent pipeline run ID
        WHEN POST /pipeline/{id}/replay
        THEN returns 404 Not Found
        """
        # Act
        nonexistent_id = generate_uuid()
        response = await client.post(f"/pipeline/{nonexistent_id}/replay")

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_replay_with_preserve_approved_artifacts_param(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """
        Test API accepts preserve_approved_artifacts query parameter.

        GIVEN valid pipeline run
        WHEN POST /pipeline/{id}/replay?preserve_approved_artifacts=true
        THEN request succeeds
        """
        # Arrange: Create project
        project = Project(
            id=generate_uuid(),
            name="Preserve Artifacts Project",
            tenant_id="test-tenant-id",
            status=ProjectStatus.active,
        )
        db_session.add(project)
        await db_session.commit()

        # Create task
        task = Task(
            id=generate_uuid(),
            project_id=project.id,
            tenant_id="test-tenant-id",
            title="Preserve Artifacts Task",
            input_spec={"description": "Build something"},
            status=TaskStatus.completed,
        )
        db_session.add(task)
        await db_session.commit()

        # Create pipeline run
        pipeline = PipelineRun(
            id=generate_uuid(),
            task_id=task.id,
            tenant_id="test-tenant-id",
            status=PipelineStatus.completed,
            current_step=4,
        )
        db_session.add(pipeline)
        await db_session.commit()

        # Act
        response = await client.post(
            f"/pipeline/{pipeline.id}/replay",
            params={"preserve_approved_artifacts": True}
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"

    async def test_replay_with_preserve_artifacts_false(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """
        Test API accepts preserve_approved_artifacts=false.

        GIVEN valid pipeline run
        WHEN POST /pipeline/{id}/replay?preserve_approved_artifacts=false
        THEN request succeeds
        """
        # Arrange: Create project
        project = Project(
            id=generate_uuid(),
            name="No Preserve Project",
            tenant_id="test-tenant-id",
            status=ProjectStatus.active,
        )
        db_session.add(project)
        await db_session.commit()

        # Create task
        task = Task(
            id=generate_uuid(),
            project_id=project.id,
            tenant_id="test-tenant-id",
            title="No Preserve Task",
            input_spec={"description": "Build something else"},
            status=TaskStatus.completed,
        )
        db_session.add(task)
        await db_session.commit()

        # Create pipeline run
        pipeline = PipelineRun(
            id=generate_uuid(),
            task_id=task.id,
            tenant_id="test-tenant-id",
            status=PipelineStatus.completed,
            current_step=4,
        )
        db_session.add(pipeline)
        await db_session.commit()

        # Act
        response = await client.post(
            f"/pipeline/{pipeline.id}/replay",
            params={"preserve_approved_artifacts": False}
        )

        # Assert
        assert response.status_code == 200

    async def test_replay_failed_pipeline(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """
        Test replaying a failed pipeline run.

        GIVEN failed pipeline run
        WHEN POST /pipeline/{id}/replay
        THEN new pipeline run is created
        """
        # Arrange: Create project
        project = Project(
            id=generate_uuid(),
            name="Failed Pipeline Project",
            tenant_id="test-tenant-id",
            status=ProjectStatus.active,
        )
        db_session.add(project)
        await db_session.commit()

        # Create task
        task = Task(
            id=generate_uuid(),
            project_id=project.id,
            tenant_id="test-tenant-id",
            title="Failed Pipeline Task",
            input_spec={"description": "Build API"},
            status=TaskStatus.failed,
        )
        db_session.add(task)
        await db_session.commit()

        # Create failed pipeline run
        pipeline = PipelineRun(
            id=generate_uuid(),
            task_id=task.id,
            tenant_id="test-tenant-id",
            status=PipelineStatus.failed,
            current_step=2,
            error_message="Step failed due to external service error",
        )
        db_session.add(pipeline)
        await db_session.commit()

        # Act
        response = await client.post(f"/pipeline/{pipeline.id}/replay")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["started_from_step"] == "STEP_1"

    async def test_replay_creates_independent_pipeline_run(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """
        Test that replay creates a new independent pipeline run.

        GIVEN completed pipeline run
        WHEN replayed twice
        THEN two separate new pipeline runs are created
        """
        # Arrange: Create project
        project = Project(
            id=generate_uuid(),
            name="Multiple Replay Project",
            tenant_id="test-tenant-id",
            status=ProjectStatus.active,
        )
        db_session.add(project)
        await db_session.commit()

        # Create task
        task = Task(
            id=generate_uuid(),
            project_id=project.id,
            tenant_id="test-tenant-id",
            title="Multiple Replay Task",
            input_spec={"description": "Build multiple"},
            status=TaskStatus.completed,
        )
        db_session.add(task)
        await db_session.commit()

        # Create pipeline run
        original_pipeline = PipelineRun(
            id=generate_uuid(),
            task_id=task.id,
            tenant_id="test-tenant-id",
            status=PipelineStatus.completed,
            current_step=4,
        )
        db_session.add(original_pipeline)
        await db_session.commit()

        # Act: Replay twice
        response1 = await client.post(f"/pipeline/{original_pipeline.id}/replay")
        response2 = await client.post(f"/pipeline/{original_pipeline.id}/replay")

        # Assert: Both succeed with different IDs
        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        assert data1["new_pipeline_run_id"] != data2["new_pipeline_run_id"]
        assert data1["new_pipeline_run_id"] != original_pipeline.id
        assert data2["new_pipeline_run_id"] != original_pipeline.id

        # Verify all three pipelines exist in database
        from sqlmodel import select

        result = await db_session.execute(
            select(PipelineRun).where(PipelineRun.task_id == task.id)
        )
        all_pipelines = result.scalars().all()
        assert len(all_pipelines) == 3

    async def test_replay_from_step_with_nonexistent_step_id(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """
        Test replay with from_step_id that doesn't exist falls back to step 1.

        GIVEN valid pipeline run
        WHEN POST /pipeline/{id}/replay with nonexistent from_step_id
        THEN pipeline starts from step 1 (fallback)
        """
        # Arrange: Create project
        project = Project(
            id=generate_uuid(),
            name="Fallback Step Project",
            tenant_id="test-tenant-id",
            status=ProjectStatus.active,
        )
        db_session.add(project)
        await db_session.commit()

        # Create task
        task = Task(
            id=generate_uuid(),
            project_id=project.id,
            tenant_id="test-tenant-id",
            title="Fallback Step Task",
            input_spec={"description": "Build fallback"},
            status=TaskStatus.completed,
        )
        db_session.add(task)
        await db_session.commit()

        # Create pipeline run with steps
        pipeline = PipelineRun(
            id=generate_uuid(),
            task_id=task.id,
            tenant_id="test-tenant-id",
            status=PipelineStatus.completed,
            current_step=2,
        )
        db_session.add(pipeline)
        await db_session.commit()

        # Create a step
        step = PipelineStepRun(
            id=generate_uuid(),
            pipeline_run_id=pipeline.id,
            step_number=1,
            step_name="Analysis",
            step_type=StepType.ANALYSIS,
            status=StepStatus.completed,
        )
        db_session.add(step)
        await db_session.commit()

        # Act: Use a nonexistent step ID
        nonexistent_step_id = generate_uuid()
        response = await client.post(
            f"/pipeline/{pipeline.id}/replay",
            params={"from_step_id": nonexistent_step_id}
        )

        # Assert: Falls back to STEP_1
        assert response.status_code == 200
        data = response.json()
        assert data["started_from_step"] == "STEP_1"


@pytest.mark.asyncio
class TestReplayPipelineTenantIsolation:
    """Tests for tenant isolation in replay pipeline endpoint"""

    async def test_wrong_tenant_cannot_replay_pipeline(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ):
        """
        Test security: Different tenant cannot replay another tenant's pipeline.

        GIVEN pipeline belonging to tenant_A
        WHEN tenant_B (via current_user fixture) tries to replay
        THEN returns 404 (not 403, for security through obscurity)

        Note: The client fixture returns user with tenant_id="test-tenant-id"
        """
        # Arrange: Create project for different tenant
        other_tenant_id = "other-tenant-xyz"
        project = Project(
            id=generate_uuid(),
            name="Other Tenant Project",
            tenant_id=other_tenant_id,
            status=ProjectStatus.active,
        )
        db_session.add(project)
        await db_session.commit()

        # Create task for different tenant
        task = Task(
            id=generate_uuid(),
            project_id=project.id,
            tenant_id=other_tenant_id,
            title="Other Tenant Task",
            input_spec={"description": "Build for other tenant"},
            status=TaskStatus.completed,
        )
        db_session.add(task)
        await db_session.commit()

        # Create pipeline for different tenant
        pipeline = PipelineRun(
            id=generate_uuid(),
            task_id=task.id,
            tenant_id=other_tenant_id,
            status=PipelineStatus.completed,
            current_step=4,
        )
        db_session.add(pipeline)
        await db_session.commit()

        # Act: Try to replay (client fixture has tenant_id="test-tenant-id")
        response = await client.post(f"/pipeline/{pipeline.id}/replay")

        # Assert: Returns 404 (security through obscurity)
        assert response.status_code == 404
