"""Integration tests for Export API - UC-30

Tests export job creation, status polling, error handling, and tenant isolation.

Note: Background task processing is tested separately in unit tests.
These integration tests focus on the HTTP API contract - creating jobs and checking status.
"""
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession
from datetime import datetime

from src.domain.project import Project
from src.domain.task import Task
from src.domain.pipeline_run import PipelineRun
from src.domain.pipeline_step import PipelineStepRun
from src.domain.artifact import Artifact
from src.domain.export_job import ExportJob
from src.domain.enums import (
    ProjectStatus,
    TaskStatus,
    PipelineStatus,
    StepStatus,
    StepType,
    ArtifactType,
    ArtifactStatus,
    ExportJobStatus,
)
from src.domain.base import generate_uuid


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
async def export_project(db_session: AsyncSession):
    """Create a test project for export tests"""
    project = Project(
        id=generate_uuid(),
        name="Export Test Project",
        description="Test project for export API tests",
        tenant_id="test-tenant-id",
        status=ProjectStatus.active,
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
async def export_task(db_session: AsyncSession, export_project: Project):
    """Create a test task for export tests"""
    task = Task(
        id=generate_uuid(),
        project_id=export_project.id,
        tenant_id="test-tenant-id",
        title="Export Test Task",
        input_spec={"requirement": "Test export functionality"},
        status=TaskStatus.completed,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


@pytest.fixture
async def export_pipeline_run(db_session: AsyncSession, export_task: Task):
    """Create a test pipeline run for export tests"""
    pipeline = PipelineRun(
        id=generate_uuid(),
        task_id=export_task.id,
        tenant_id="test-tenant-id",
        status=PipelineStatus.completed,
        current_step=4,
    )
    db_session.add(pipeline)
    await db_session.commit()
    await db_session.refresh(pipeline)
    return pipeline


@pytest.fixture
async def export_pipeline_step(db_session: AsyncSession, export_pipeline_run: PipelineRun):
    """Create a test pipeline step for export tests"""
    step = PipelineStepRun(
        id=generate_uuid(),
        pipeline_run_id=export_pipeline_run.id,
        step_number=1,
        step_name="Analysis Step",
        step_type=StepType.ANALYSIS,
        status=StepStatus.completed,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db_session.add(step)
    await db_session.commit()
    await db_session.refresh(step)
    return step


@pytest.fixture
async def approved_artifact(
    db_session: AsyncSession,
    export_task: Task,
    export_pipeline_run: PipelineRun,
    export_pipeline_step: PipelineStepRun,
):
    """Create an approved artifact for export tests"""
    artifact = Artifact(
        id=generate_uuid(),
        task_id=export_task.id,
        pipeline_run_id=export_pipeline_run.id,
        step_run_id=export_pipeline_step.id,
        artifact_type=ArtifactType.ANALYSIS_REPORT,
        status=ArtifactStatus.approved,
        version=1,
        content={"analysis": "Test analysis content for export"},
        approved_at=datetime.utcnow(),
    )
    db_session.add(artifact)
    await db_session.commit()
    await db_session.refresh(artifact)
    return artifact


@pytest.fixture
async def draft_artifact(
    db_session: AsyncSession,
    export_task: Task,
    export_pipeline_run: PipelineRun,
    export_pipeline_step: PipelineStepRun,
):
    """Create a draft (not approved) artifact for export tests"""
    artifact = Artifact(
        id=generate_uuid(),
        task_id=export_task.id,
        pipeline_run_id=export_pipeline_run.id,
        step_run_id=export_pipeline_step.id,
        artifact_type=ArtifactType.ANALYSIS_REPORT,
        status=ArtifactStatus.draft,
        version=1,
        content={"analysis": "Draft analysis - not exported"},
    )
    db_session.add(artifact)
    await db_session.commit()
    await db_session.refresh(artifact)
    return artifact


@pytest.fixture
async def existing_export_job(db_session: AsyncSession, export_project: Project):
    """Create an existing export job for status tests"""
    export_job = ExportJob(
        id=generate_uuid(),
        project_id=export_project.id,
        tenant_id="test-tenant-id",
        status=ExportJobStatus.pending,
    )
    db_session.add(export_job)
    await db_session.commit()
    await db_session.refresh(export_job)
    return export_job


@pytest.fixture
async def completed_export_job(db_session: AsyncSession, export_project: Project):
    """Create a completed export job with download URL"""
    export_job = ExportJob(
        id=generate_uuid(),
        project_id=export_project.id,
        tenant_id="test-tenant-id",
        status=ExportJobStatus.completed,
        file_path="exports/test-tenant-id/project-123/job-456.zip",
        download_url="https://storage.example.com/exports/test.zip?token=abc123",
        expires_at=datetime.utcnow(),
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db_session.add(export_job)
    await db_session.commit()
    await db_session.refresh(export_job)
    return export_job


# ============================================================================
# CREATE EXPORT JOB TESTS
# ============================================================================


@pytest.mark.asyncio
@patch("src.api.routes.exports.process_export_in_background", new_callable=AsyncMock)
async def test_create_export_job_success(
    mock_background_task: AsyncMock,
    client: AsyncClient,
    db_session: AsyncSession,
    export_project: Project,
    export_task: Task,
    export_pipeline_run: PipelineRun,
    export_pipeline_step: PipelineStepRun,
    approved_artifact: Artifact,
):
    """Test POST /projects/{id}/export creates export job successfully (returns 202)"""
    # Act
    response = await client.post(f"/projects/{export_project.id}/export")

    # Assert
    assert response.status_code == 202

    data = response.json()
    assert "export_job_id" in data
    assert data["status"] == ExportJobStatus.pending.value

    # Verify background task was scheduled (but mocked)
    # The actual background processing is tested separately


@pytest.mark.asyncio
async def test_create_export_job_project_not_found(client: AsyncClient):
    """Test POST /projects/{id}/export returns 404 for non-existent project"""
    # Act
    response = await client.post("/projects/non-existent-project-id/export")

    # Assert
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "PROJECT_NOT_FOUND"
    assert "not found" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_create_export_job_no_tasks(
    client: AsyncClient,
    db_session: AsyncSession,
    export_project: Project,
):
    """Test POST /projects/{id}/export returns 400 when project has no tasks"""
    # Note: export_project fixture creates a project without tasks

    # Act
    response = await client.post(f"/projects/{export_project.id}/export")

    # Assert
    assert response.status_code == 400

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NO_ARTIFACTS"


@pytest.mark.asyncio
async def test_create_export_job_no_approved_artifacts(
    client: AsyncClient,
    db_session: AsyncSession,
    export_project: Project,
    export_task: Task,
    export_pipeline_run: PipelineRun,
    export_pipeline_step: PipelineStepRun,
    draft_artifact: Artifact,
):
    """Test POST /projects/{id}/export returns 400 when no approved artifacts exist"""
    # Act
    response = await client.post(f"/projects/{export_project.id}/export")

    # Assert
    assert response.status_code == 400

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NO_APPROVED_ARTIFACTS"
    assert "approved" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_create_export_job_tenant_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test that user cannot create export job for another tenant's project"""
    # Arrange - Create project for different tenant
    other_tenant_project = Project(
        id=generate_uuid(),
        name="Other Tenant Project",
        description="Project belonging to different tenant",
        tenant_id="other-tenant-id",  # Different from test-tenant-id in JWT
        status=ProjectStatus.active,
    )
    db_session.add(other_tenant_project)
    await db_session.commit()

    # Act - Try to create export for other tenant's project
    response = await client.post(f"/projects/{other_tenant_project.id}/export")

    # Assert - Should get 404 (project not found for this tenant)
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "PROJECT_NOT_FOUND"


# ============================================================================
# GET EXPORT JOB STATUS TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_get_export_job_status_pending(
    client: AsyncClient,
    db_session: AsyncSession,
    export_project: Project,
    existing_export_job: ExportJob,
):
    """Test GET /projects/{id}/export/{job_id} returns pending status"""
    # Act
    response = await client.get(
        f"/projects/{export_project.id}/export/{existing_export_job.id}"
    )

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert data["export_job_id"] == existing_export_job.id
    assert data["project_id"] == export_project.id
    assert data["status"] == ExportJobStatus.pending.value
    assert data["download_url"] is None
    assert data["expires_at"] is None
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_export_job_status_completed_with_download_url(
    client: AsyncClient,
    db_session: AsyncSession,
    export_project: Project,
    completed_export_job: ExportJob,
):
    """Test GET /projects/{id}/export/{job_id} returns completed status with download URL"""
    # Act
    response = await client.get(
        f"/projects/{export_project.id}/export/{completed_export_job.id}"
    )

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert data["export_job_id"] == completed_export_job.id
    assert data["project_id"] == export_project.id
    assert data["status"] == ExportJobStatus.completed.value
    assert data["download_url"] is not None
    assert "expires_at" in data
    assert "started_at" in data
    assert "completed_at" in data


@pytest.mark.asyncio
async def test_get_export_job_status_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
    export_project: Project,
):
    """Test GET /projects/{id}/export/{job_id} returns 404 for non-existent job"""
    # Act
    response = await client.get(
        f"/projects/{export_project.id}/export/non-existent-job-id"
    )

    # Assert
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "EXPORT_JOB_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_export_job_status_wrong_project(
    client: AsyncClient,
    db_session: AsyncSession,
    export_project: Project,
    existing_export_job: ExportJob,
):
    """Test GET /projects/{id}/export/{job_id} returns 404 when job belongs to different project"""
    # Arrange - Create another project
    other_project = Project(
        id=generate_uuid(),
        name="Other Project",
        tenant_id="test-tenant-id",
        status=ProjectStatus.active,
    )
    db_session.add(other_project)
    await db_session.commit()

    # Act - Try to get export job using wrong project ID
    response = await client.get(
        f"/projects/{other_project.id}/export/{existing_export_job.id}"
    )

    # Assert - Should get 404 (job not found for this project)
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "EXPORT_JOB_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_export_job_status_tenant_isolation(
    client: AsyncClient,
    db_session: AsyncSession,
):
    """Test that user cannot access another tenant's export job"""
    # Arrange - Create project and export job for different tenant
    other_tenant_project = Project(
        id=generate_uuid(),
        name="Other Tenant Project",
        tenant_id="other-tenant-id",  # Different from test-tenant-id
        status=ProjectStatus.active,
    )
    db_session.add(other_tenant_project)
    await db_session.flush()

    other_tenant_job = ExportJob(
        id=generate_uuid(),
        project_id=other_tenant_project.id,
        tenant_id="other-tenant-id",  # Different from test-tenant-id
        status=ExportJobStatus.completed,
        download_url="https://storage.example.com/secret.zip",
    )
    db_session.add(other_tenant_job)
    await db_session.commit()

    # Act - Try to access other tenant's export job
    response = await client.get(
        f"/projects/{other_tenant_project.id}/export/{other_tenant_job.id}"
    )

    # Assert - Should get 404 (job not found - tenant isolation)
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "EXPORT_JOB_NOT_FOUND"


# ============================================================================
# PROCESSING STATUS TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_get_export_job_status_processing(
    client: AsyncClient,
    db_session: AsyncSession,
    export_project: Project,
):
    """Test GET /projects/{id}/export/{job_id} returns processing status"""
    # Arrange - Create processing export job
    processing_job = ExportJob(
        id=generate_uuid(),
        project_id=export_project.id,
        tenant_id="test-tenant-id",
        status=ExportJobStatus.processing,
        started_at=datetime.utcnow(),
    )
    db_session.add(processing_job)
    await db_session.commit()

    # Act
    response = await client.get(
        f"/projects/{export_project.id}/export/{processing_job.id}"
    )

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == ExportJobStatus.processing.value
    assert data["download_url"] is None
    assert "started_at" in data


@pytest.mark.asyncio
async def test_get_export_job_status_failed(
    client: AsyncClient,
    db_session: AsyncSession,
    export_project: Project,
):
    """Test GET /projects/{id}/export/{job_id} returns failed status with error message"""
    # Arrange - Create failed export job
    failed_job = ExportJob(
        id=generate_uuid(),
        project_id=export_project.id,
        tenant_id="test-tenant-id",
        status=ExportJobStatus.failed,
        error_message="Storage upload failed: Connection timeout",
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )
    db_session.add(failed_job)
    await db_session.commit()

    # Act
    response = await client.get(
        f"/projects/{export_project.id}/export/{failed_job.id}"
    )

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == ExportJobStatus.failed.value
    assert data["error_message"] is not None
    assert "Storage upload failed" in data["error_message"]
    assert data["download_url"] is None


# ============================================================================
# EDGE CASES
# ============================================================================


@pytest.mark.asyncio
@patch("src.api.routes.exports.process_export_in_background", new_callable=AsyncMock)
async def test_create_export_job_multiple_approved_artifacts(
    mock_background_task: AsyncMock,
    client: AsyncClient,
    db_session: AsyncSession,
    export_project: Project,
    export_task: Task,
    export_pipeline_run: PipelineRun,
    export_pipeline_step: PipelineStepRun,
):
    """Test export job creation with multiple approved artifacts"""
    # Arrange - Create multiple approved artifacts
    for i in range(3):
        artifact = Artifact(
            id=generate_uuid(),
            task_id=export_task.id,
            pipeline_run_id=export_pipeline_run.id,
            step_run_id=export_pipeline_step.id,
            artifact_type=ArtifactType.ANALYSIS_REPORT,
            status=ArtifactStatus.approved,
            version=i + 1,
            content={"analysis": f"Analysis content {i + 1}"},
            approved_at=datetime.utcnow(),
        )
        db_session.add(artifact)
    await db_session.commit()

    # Act
    response = await client.post(f"/projects/{export_project.id}/export")

    # Assert
    assert response.status_code == 202

    data = response.json()
    assert "export_job_id" in data
    assert data["status"] == ExportJobStatus.pending.value


@pytest.mark.asyncio
@patch("src.api.routes.exports.process_export_in_background", new_callable=AsyncMock)
async def test_create_export_job_mixed_artifact_statuses(
    mock_background_task: AsyncMock,
    client: AsyncClient,
    db_session: AsyncSession,
    export_project: Project,
    export_task: Task,
    export_pipeline_run: PipelineRun,
    export_pipeline_step: PipelineStepRun,
):
    """Test export job creation succeeds when at least one artifact is approved"""
    # Arrange - Create mix of approved, draft, and rejected artifacts
    statuses = [ArtifactStatus.approved, ArtifactStatus.draft, ArtifactStatus.rejected]
    for i, status in enumerate(statuses):
        artifact = Artifact(
            id=generate_uuid(),
            task_id=export_task.id,
            pipeline_run_id=export_pipeline_run.id,
            step_run_id=export_pipeline_step.id,
            artifact_type=ArtifactType.ANALYSIS_REPORT,
            status=status,
            version=i + 1,
            content={"analysis": f"Analysis with status {status.value}"},
        )
        if status == ArtifactStatus.approved:
            artifact.approved_at = datetime.utcnow()
        db_session.add(artifact)
    await db_session.commit()

    # Act
    response = await client.post(f"/projects/{export_project.id}/export")

    # Assert - Should succeed because there's at least one approved artifact
    assert response.status_code == 202

    data = response.json()
    assert "export_job_id" in data
    assert data["status"] == ExportJobStatus.pending.value
