"""Integration tests for CancelPipeline use case - Story 2.6"""
import pytest
from datetime import datetime
from sqlmodel.ext.asyncio.session import AsyncSession
from src.domain.enums import PipelineStatus, StepStatus, StepType
from src.domain.pipeline_run import PipelineRun
from src.domain.pipeline_step import PipelineStepRun
from src.domain.artifact import Artifact, ArtifactStatus
from src.domain.task import Task, TaskStatus
from src.domain.project import Project, ProjectStatus
from src.domain.base import generate_uuid
from src.adapter.repositories.pipeline_run_repository import PipelineRunRepository
from src.adapter.repositories.pipeline_step_repository import PipelineStepRunRepository
from src.adapter.repositories.artifact_repository import ArtifactRepository
from src.adapter.repositories.task_repository import SqlAlchemyTaskRepository
from src.app.use_cases.pipeline.cancel_pipeline import CancelPipeline
from src.app.use_cases.pipeline.dtos import CancelPipelineCommandDTO


@pytest.fixture
async def task_repository(db_session: AsyncSession):
    return SqlAlchemyTaskRepository(db_session)


@pytest.fixture
async def pipeline_run_repository(db_session: AsyncSession):
    return PipelineRunRepository(db_session)


@pytest.fixture
async def step_run_repository(db_session: AsyncSession):
    return PipelineStepRunRepository(db_session)


@pytest.fixture
async def artifact_repository(db_session: AsyncSession):
    return ArtifactRepository(db_session)


@pytest.fixture
async def cancel_pipeline_use_case(
    pipeline_run_repository, step_run_repository
):
    return CancelPipeline(
        pipeline_run_repository=pipeline_run_repository,
        step_run_repository=step_run_repository,
        audit_service=None,  # No audit service for integration tests
    )


@pytest.mark.asyncio
class TestCancelPipelineIntegration:
    """Integration tests for CancelPipeline - AC-2.6.1 through AC-2.6.5"""

    async def test_cancel_running_pipeline_end_to_end(
        self,
        db_session: AsyncSession,
        task_repository,
        pipeline_run_repository,
        step_run_repository,
        artifact_repository,
        cancel_pipeline_use_case,
    ):
        """Test AC-2.6.1, AC-2.6.3: Cancel pipeline and preserve completed work"""
        # Arrange: Create project first
        project = Project(
            id=generate_uuid(),
            name="Test Project",
            tenant_id="tenant_123",
            user_id="user_123",
            status=ProjectStatus.active,
        )
        db_session.add(project)
        await db_session.commit()

        # Create task
        task = Task(
            id=generate_uuid(),
            project_id=project.id,
            tenant_id="tenant_123",
            title="Test Task",
            input_spec="Build an API",
            status=TaskStatus.running,
        )
        db_session.add(task)
        await db_session.commit()

        # Create pipeline run
        pipeline = PipelineRun(
            id=generate_uuid(),
            task_id=task.id,
            tenant_id=task.tenant_id,
            status=PipelineStatus.running,
            current_step=2,
        )
        pipeline = await pipeline_run_repository.create(pipeline)

        # Create completed step with artifact
        step1 = PipelineStepRun(
            id=generate_uuid(),
            pipeline_run_id=pipeline.id,
            step_number=1,
            step_name="Analysis Step",
            step_type=StepType.ANALYSIS,
            status=StepStatus.completed,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        step1 = await step_run_repository.create(step1)

        artifact1 = Artifact(
            id=generate_uuid(),
            task_id=task.id,
            pipeline_run_id=pipeline.id,
            step_run_id=step1.id,
            artifact_type="ANALYSIS_REPORT",
            status=ArtifactStatus.approved,
            content="Analysis report content",
            version=1,
        )
        db_session.add(artifact1)

        # Create running step
        step2 = PipelineStepRun(
            id=generate_uuid(),
            pipeline_run_id=pipeline.id,
            step_number=2,
            step_name="User Stories Step",
            step_type=StepType.USER_STORIES,
            status=StepStatus.running,
            started_at=datetime.utcnow(),
        )
        step2 = await step_run_repository.create(step2)

        await db_session.commit()

        # Act: Cancel pipeline
        command = CancelPipelineCommandDTO(
            pipeline_run_id=pipeline.id,
            tenant_id=task.tenant_id,
            user_id="user_123",
            reason="Testing cancellation",
        )

        result = await cancel_pipeline_use_case.execute(command)

        # Assert: Cancellation succeeded
        assert result.is_ok()
        dto = result.value
        assert dto.pipeline_run_id == pipeline.id
        assert dto.previous_status == "running"
        assert dto.new_status == "cancelled"
        assert dto.steps_completed == 1
        assert dto.steps_cancelled == 1

        # Verify pipeline status in database
        await db_session.refresh(pipeline)
        assert pipeline.status == PipelineStatus.cancelled

        # Verify completed step is preserved
        await db_session.refresh(step1)
        assert step1.status == StepStatus.completed

        # Verify artifact is still accessible
        from sqlmodel import select

        result = await db_session.execute(
            select(Artifact).where(Artifact.id == artifact1.id)
        )
        artifact = result.scalar_one()
        assert artifact is not None
        assert artifact.status == ArtifactStatus.approved

        # Verify running step was cancelled
        await db_session.refresh(step2)
        assert step2.status == StepStatus.cancelled
        assert step2.completed_at is not None

    async def test_cannot_cancel_completed_pipeline_persistence(
        self, db_session: AsyncSession, pipeline_run_repository, cancel_pipeline_use_case
    ):
        """Test AC-2.6.2: Cannot cancel completed pipeline (database check)"""
        # Arrange: Create project and task first
        project = Project(
            id=generate_uuid(),
            name="Test Project",
            tenant_id="tenant_123",
            user_id="user_123",
            status=ProjectStatus.active,
        )
        db_session.add(project)

        task = Task(
            id=generate_uuid(),
            project_id=project.id,
            tenant_id="tenant_123",
            title="Test Task",
            input_spec="Build an API",
            status=TaskStatus.completed,
        )
        db_session.add(task)
        await db_session.flush()

        # Create completed pipeline
        pipeline = PipelineRun(
            id=generate_uuid(),
            task_id=task.id,
            tenant_id="tenant_123",
            status=PipelineStatus.completed,
            current_step=4,
            completed_at=datetime.utcnow(),
        )
        pipeline = await pipeline_run_repository.create(pipeline)
        await db_session.commit()

        # Act: Attempt to cancel
        command = CancelPipelineCommandDTO(
            pipeline_run_id=pipeline.id,
            tenant_id="tenant_123",
            user_id="user_123",
        )

        result = await cancel_pipeline_use_case.execute(command)

        # Assert: Error returned
        assert result.is_err()
        assert result.error.code == "CANNOT_CANCEL_COMPLETED"

        # Verify status unchanged in database
        await db_session.refresh(pipeline)
        assert pipeline.status == PipelineStatus.completed

    async def test_cancel_with_multiple_completed_steps(
        self,
        db_session: AsyncSession,
        task_repository,
        pipeline_run_repository,
        step_run_repository,
        cancel_pipeline_use_case,
    ):
        """Test AC-2.6.3: All completed steps preserved when cancelling"""
        # Arrange: Create project first
        project = Project(
            id=generate_uuid(),
            name="Multi-step Project",
            tenant_id="tenant_123",
            user_id="user_123",
            status=ProjectStatus.active,
        )
        db_session.add(project)
        await db_session.commit()

        # Create task
        task = Task(
            id=generate_uuid(),
            project_id=project.id,
            tenant_id="tenant_123",
            title="Multi-step Task",
            input_spec="Complex project",
            status=TaskStatus.running,
        )
        db_session.add(task)
        await db_session.commit()

        # Create pipeline
        pipeline = PipelineRun(
            id=generate_uuid(),
            task_id=task.id,
            tenant_id=task.tenant_id,
            status=PipelineStatus.running,
            current_step=4,
        )
        pipeline = await pipeline_run_repository.create(pipeline)

        # Create 3 completed steps
        for i in range(1, 4):
            step = PipelineStepRun(
                id=generate_uuid(),
                pipeline_run_id=pipeline.id,
                step_number=i,
                step_name=f"Step {i}",
                step_type=list(StepType)[i - 1],
                status=StepStatus.completed,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )
            await step_run_repository.create(step)

        # Create 1 running step
        running_step = PipelineStepRun(
            id=generate_uuid(),
            pipeline_run_id=pipeline.id,
            step_number=4,
            step_name="Test Cases Step",
            step_type=StepType.TEST_CASES,
            status=StepStatus.running,
            started_at=datetime.utcnow(),
        )
        await step_run_repository.create(running_step)
        await db_session.commit()

        # Act: Cancel
        command = CancelPipelineCommandDTO(
            pipeline_run_id=pipeline.id,
            tenant_id=task.tenant_id,
            user_id="user_123",
        )

        result = await cancel_pipeline_use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.steps_completed == 3
        assert result.value.steps_cancelled == 1

        # Verify all steps in database
        steps = await step_run_repository.get_by_pipeline_run_id(pipeline.id)
        completed_steps = [s for s in steps if s.status == StepStatus.completed]
        cancelled_steps = [s for s in steps if s.status == StepStatus.cancelled]

        assert len(completed_steps) == 3
        assert len(cancelled_steps) == 1

    async def test_cancel_paused_pipeline(
        self, db_session: AsyncSession, pipeline_run_repository, cancel_pipeline_use_case
    ):
        """Test AC-2.6.1: Can cancel paused pipeline"""
        # Arrange: Create project and task first
        project = Project(
            id=generate_uuid(),
            name="Test Project",
            tenant_id="tenant_123",
            user_id="user_123",
            status=ProjectStatus.active,
        )
        db_session.add(project)

        task = Task(
            id=generate_uuid(),
            project_id=project.id,
            tenant_id="tenant_123",
            title="Test Task",
            input_spec="Build an API",
            status=TaskStatus.running,
        )
        db_session.add(task)
        await db_session.flush()

        pipeline = PipelineRun(
            id=generate_uuid(),
            task_id=task.id,
            tenant_id="tenant_123",
            status=PipelineStatus.paused,
            current_step=2,
            pause_reasons=["INSUFFICIENT_CREDIT"],
        )
        pipeline = await pipeline_run_repository.create(pipeline)
        await db_session.commit()

        # Act
        command = CancelPipelineCommandDTO(
            pipeline_run_id=pipeline.id,
            tenant_id="tenant_123",
            user_id="user_123",
        )

        result = await cancel_pipeline_use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.previous_status == "paused"

        await db_session.refresh(pipeline)
        assert pipeline.status == PipelineStatus.cancelled

    async def test_unauthorized_tenant_cannot_cancel(
        self, db_session: AsyncSession, pipeline_run_repository, cancel_pipeline_use_case
    ):
        """Test security: Wrong tenant cannot cancel pipeline"""
        # Arrange: Create project and task first
        project = Project(
            id=generate_uuid(),
            name="Test Project",
            tenant_id="tenant_correct",
            user_id="user_123",
            status=ProjectStatus.active,
        )
        db_session.add(project)

        task = Task(
            id=generate_uuid(),
            project_id=project.id,
            tenant_id="tenant_correct",
            title="Test Task",
            input_spec="Build an API",
            status=TaskStatus.running,
        )
        db_session.add(task)
        await db_session.flush()

        pipeline = PipelineRun(
            id=generate_uuid(),
            task_id=task.id,
            tenant_id="tenant_correct",
            status=PipelineStatus.running,
        )
        pipeline = await pipeline_run_repository.create(pipeline)
        await db_session.commit()

        # Act: Try to cancel with wrong tenant
        command = CancelPipelineCommandDTO(
            pipeline_run_id=pipeline.id,
            tenant_id="tenant_wrong",
            user_id="user_123",
        )

        result = await cancel_pipeline_use_case.execute(command)

        # Assert: Error
        assert result.is_err()
        assert result.error.code == "UNAUTHORIZED"

        # Verify status unchanged
        await db_session.refresh(pipeline)
        assert pipeline.status == PipelineStatus.running

    async def test_cancel_pipeline_with_no_steps(
        self, db_session: AsyncSession, pipeline_run_repository, cancel_pipeline_use_case
    ):
        """Test edge case: Cancel pipeline that has no steps yet"""
        # Arrange: Create project and task first
        project = Project(
            id=generate_uuid(),
            name="Test Project",
            tenant_id="tenant_123",
            user_id="user_123",
            status=ProjectStatus.active,
        )
        db_session.add(project)

        task = Task(
            id=generate_uuid(),
            project_id=project.id,
            tenant_id="tenant_123",
            title="Test Task",
            input_spec="Build an API",
            status=TaskStatus.running,
        )
        db_session.add(task)
        await db_session.flush()

        pipeline = PipelineRun(
            id=generate_uuid(),
            task_id=task.id,
            tenant_id="tenant_123",
            status=PipelineStatus.running,
            current_step=1,
        )
        pipeline = await pipeline_run_repository.create(pipeline)
        await db_session.commit()

        # Act
        command = CancelPipelineCommandDTO(
            pipeline_run_id=pipeline.id,
            tenant_id="tenant_123",
            user_id="user_123",
        )

        result = await cancel_pipeline_use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.steps_completed == 0
        assert result.value.steps_cancelled == 0

        await db_session.refresh(pipeline)
        assert pipeline.status == PipelineStatus.cancelled

    async def test_idempotent_cancellation(
        self, db_session: AsyncSession, pipeline_run_repository, cancel_pipeline_use_case
    ):
        """Test AC-2.6.4: Cancellation is idempotent"""
        # Arrange: Create project and task first
        project = Project(
            id=generate_uuid(),
            name="Test Project",
            tenant_id="tenant_123",
            user_id="user_123",
            status=ProjectStatus.active,
        )
        db_session.add(project)

        task = Task(
            id=generate_uuid(),
            project_id=project.id,
            tenant_id="tenant_123",
            title="Test Task",
            input_spec="Build an API",
            status=TaskStatus.running,
        )
        db_session.add(task)
        await db_session.flush()

        pipeline = PipelineRun(
            id=generate_uuid(),
            task_id=task.id,
            tenant_id="tenant_123",
            status=PipelineStatus.running,
        )
        pipeline = await pipeline_run_repository.create(pipeline)
        await db_session.commit()

        command = CancelPipelineCommandDTO(
            pipeline_run_id=pipeline.id,
            tenant_id="tenant_123",
            user_id="user_123",
        )

        # Act: First cancellation
        result1 = await cancel_pipeline_use_case.execute(command)
        assert result1.is_ok()

        # Act: Second cancellation (should fail with CANNOT_CANCEL_COMPLETED)
        result2 = await cancel_pipeline_use_case.execute(command)

        # Assert: Second attempt returns error (pipeline already cancelled)
        assert result2.is_err()
        assert result2.error.code == "CANNOT_CANCEL_COMPLETED"

        # Verify final state
        await db_session.refresh(pipeline)
        assert pipeline.status == PipelineStatus.cancelled
