"""
Integration tests for Git Sync API (UC-31)

Tests the /artifacts/{id}/sync-git and /git-sync/{job_id} endpoints.
"""
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from src.domain.project import Project
from src.domain.task import Task
from src.domain.pipeline_run import PipelineRun
from src.domain.pipeline_step import PipelineStepRun
from src.domain.artifact import Artifact
from src.domain.git_sync_job import GitSyncJob
from src.domain.enums import (
    ArtifactType,
    ArtifactStatus,
    StepType,
    StepStatus,
    PipelineStatus,
    GitSyncJobStatus,
)
from datetime import datetime


# Test constants
TEST_TENANT_ID = "test-tenant-id"
OTHER_TENANT_ID = "other-tenant-id"


@pytest.fixture(autouse=True)
def mock_background_task():
    """
    Mock the background task to prevent it from trying to connect to production DB.
    The background task creates its own DB connection from ApplicationConfig.DB_URI,
    which fails in tests. We mock it to do nothing since we're testing the API response,
    not the background processing.
    """
    with patch(
        "src.api.routes.git_sync.process_git_sync_in_background",
        new_callable=AsyncMock
    ) as mock:
        yield mock


@pytest.fixture
def valid_sync_request():
    """Valid Git sync request payload"""
    return {
        "repository_url": "https://github.com/test/repo.git",
        "branch": "feature/generated-code",
        "commit_message": "Add generated code from Super Agent",
    }


@pytest.fixture
def gitlab_sync_request():
    """Valid Git sync request for GitLab"""
    return {
        "repository_url": "https://gitlab.com/test/repo",
        "branch": "main",
        "commit_message": "Sync generated artifact",
    }


@pytest.fixture
def ssh_sync_request():
    """Valid Git sync request with SSH URL"""
    return {
        "repository_url": "git@github.com:test/repo.git",
        "branch": "develop",
        "commit_message": "Add generated code via SSH",
    }


async def create_test_project(session: AsyncSession, tenant_id: str = TEST_TENANT_ID) -> Project:
    """Helper to create a test project"""
    project = Project(
        tenant_id=tenant_id,
        name="Test Project",
        description="Test project for integration tests",
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def create_test_task(
    session: AsyncSession, project_id: str, tenant_id: str = TEST_TENANT_ID
) -> Task:
    """Helper to create a test task"""
    task = Task(
        project_id=project_id,
        tenant_id=tenant_id,
        title="Test Task",
        input_spec={"requirement": "test requirement"},
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def create_test_pipeline_run(
    session: AsyncSession, task_id: str, tenant_id: str = TEST_TENANT_ID
) -> PipelineRun:
    """Helper to create a test pipeline run"""
    pipeline_run = PipelineRun(
        task_id=task_id,
        tenant_id=tenant_id,
        status=PipelineStatus.completed,
    )
    session.add(pipeline_run)
    await session.commit()
    await session.refresh(pipeline_run)
    return pipeline_run


async def create_test_step_run(
    session: AsyncSession, pipeline_run_id: str
) -> PipelineStepRun:
    """Helper to create a test pipeline step run"""
    step_run = PipelineStepRun(
        pipeline_run_id=pipeline_run_id,
        step_number=1,
        step_name="Code Generation",
        step_type=StepType.CODE_SKELETON,
        status=StepStatus.completed,
    )
    session.add(step_run)
    await session.commit()
    await session.refresh(step_run)
    return step_run


async def create_test_artifact(
    session: AsyncSession,
    task_id: str,
    pipeline_run_id: str,
    step_run_id: str,
    status: ArtifactStatus = ArtifactStatus.approved,
) -> Artifact:
    """Helper to create a test artifact"""
    artifact = Artifact(
        task_id=task_id,
        pipeline_run_id=pipeline_run_id,
        step_run_id=step_run_id,
        artifact_type=ArtifactType.CODE_FILES,
        status=status,
        version=1,
        content={"files": [{"filename": "main.py", "content": "print('hello')"}]},
        created_at=datetime.utcnow(),
    )
    if status == ArtifactStatus.approved:
        artifact.approved_at = datetime.utcnow()
    session.add(artifact)
    await session.commit()
    await session.refresh(artifact)
    return artifact


async def create_test_git_sync_job(
    session: AsyncSession,
    artifact_id: str,
    tenant_id: str = TEST_TENANT_ID,
    status: GitSyncJobStatus = GitSyncJobStatus.pending,
) -> GitSyncJob:
    """Helper to create a test Git sync job"""
    job = GitSyncJob(
        artifact_id=artifact_id,
        tenant_id=tenant_id,
        repository_url="https://github.com/test/repo.git",
        branch="main",
        commit_message="Test commit",
        status=status,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def setup_approved_artifact(db_session: AsyncSession, tenant_id: str = TEST_TENANT_ID):
    """Helper to set up a complete chain: Project -> Task -> Pipeline -> Step -> Artifact"""
    project = await create_test_project(db_session, tenant_id)
    task = await create_test_task(db_session, project.id, tenant_id)
    pipeline_run = await create_test_pipeline_run(db_session, task.id, tenant_id)
    step_run = await create_test_step_run(db_session, pipeline_run.id)
    artifact = await create_test_artifact(
        db_session, task.id, pipeline_run.id, step_run.id, ArtifactStatus.approved
    )
    return artifact


async def setup_draft_artifact(db_session: AsyncSession, tenant_id: str = TEST_TENANT_ID):
    """Helper to set up a draft artifact (not approved)"""
    project = await create_test_project(db_session, tenant_id)
    task = await create_test_task(db_session, project.id, tenant_id)
    pipeline_run = await create_test_pipeline_run(db_session, task.id, tenant_id)
    step_run = await create_test_step_run(db_session, pipeline_run.id)
    artifact = await create_test_artifact(
        db_session, task.id, pipeline_run.id, step_run.id, ArtifactStatus.draft
    )
    return artifact


# =============================================================================
# Test Case 1: POST /artifacts/{id}/sync-git - Creates sync job successfully
# =============================================================================


@pytest.mark.asyncio
async def test_sync_to_git_success_returns_202(
    client: AsyncClient, db_session: AsyncSession, valid_sync_request
):
    """
    Test POST /artifacts/{id}/sync-git creates a sync job successfully.
    Returns 202 Accepted with sync_job_id and status.
    """
    # Arrange
    artifact = await setup_approved_artifact(db_session)

    # Act
    response = await client.post(
        f"/artifacts/{artifact.id}/sync-git", json=valid_sync_request
    )

    # Assert
    assert response.status_code == 202

    data = response.json()
    assert "sync_job_id" in data
    assert data["status"] == "pending"
    assert len(data["sync_job_id"]) > 0


@pytest.mark.asyncio
async def test_sync_to_git_with_gitlab_url(
    client: AsyncClient, db_session: AsyncSession, gitlab_sync_request
):
    """Test POST /artifacts/{id}/sync-git with GitLab URL"""
    # Arrange
    artifact = await setup_approved_artifact(db_session)

    # Act
    response = await client.post(
        f"/artifacts/{artifact.id}/sync-git", json=gitlab_sync_request
    )

    # Assert
    assert response.status_code == 202
    data = response.json()
    assert "sync_job_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_sync_to_git_with_ssh_url(
    client: AsyncClient, db_session: AsyncSession, ssh_sync_request
):
    """Test POST /artifacts/{id}/sync-git with SSH URL"""
    # Arrange
    artifact = await setup_approved_artifact(db_session)

    # Act
    response = await client.post(
        f"/artifacts/{artifact.id}/sync-git", json=ssh_sync_request
    )

    # Assert
    assert response.status_code == 202
    data = response.json()
    assert "sync_job_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_sync_to_git_creates_job_in_database(
    client: AsyncClient, db_session: AsyncSession, valid_sync_request
):
    """Test that POST /artifacts/{id}/sync-git creates a job record in the database"""
    # Arrange
    artifact = await setup_approved_artifact(db_session)

    # Act
    response = await client.post(
        f"/artifacts/{artifact.id}/sync-git", json=valid_sync_request
    )

    # Assert
    assert response.status_code == 202
    job_id = response.json()["sync_job_id"]

    # Verify job exists in database
    from sqlmodel import select

    result = await db_session.execute(select(GitSyncJob).where(GitSyncJob.id == job_id))
    job = result.scalar_one_or_none()

    assert job is not None
    assert job.artifact_id == artifact.id
    assert job.tenant_id == TEST_TENANT_ID
    assert job.repository_url == valid_sync_request["repository_url"]
    assert job.branch == valid_sync_request["branch"]
    assert job.commit_message == valid_sync_request["commit_message"]


# =============================================================================
# Test Case 2: GET /git-sync/{job_id} - Returns job status
# =============================================================================


@pytest.mark.asyncio
async def test_get_git_sync_status_pending(
    client: AsyncClient, db_session: AsyncSession
):
    """Test GET /git-sync/{job_id} returns pending status"""
    # Arrange
    artifact = await setup_approved_artifact(db_session)
    job = await create_test_git_sync_job(
        db_session, artifact.id, TEST_TENANT_ID, GitSyncJobStatus.pending
    )

    # Act
    response = await client.get(f"/git-sync/{job.id}")

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == job.id
    assert data["artifact_id"] == artifact.id
    assert data["status"] == "pending"
    assert data["repository_url"] == job.repository_url
    assert data["branch"] == job.branch
    assert data["commit_sha"] is None
    assert data["error_message"] is None
    assert data["retry_count"] == 0
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_git_sync_status_processing(
    client: AsyncClient, db_session: AsyncSession
):
    """Test GET /git-sync/{job_id} returns processing status"""
    # Arrange
    artifact = await setup_approved_artifact(db_session)
    job = await create_test_git_sync_job(
        db_session, artifact.id, TEST_TENANT_ID, GitSyncJobStatus.processing
    )
    job.started_at = datetime.utcnow()
    await db_session.commit()
    await db_session.refresh(job)

    # Act
    response = await client.get(f"/git-sync/{job.id}")

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "processing"
    assert data["started_at"] is not None


@pytest.mark.asyncio
async def test_get_git_sync_status_completed(
    client: AsyncClient, db_session: AsyncSession
):
    """Test GET /git-sync/{job_id} returns completed status with commit SHA"""
    # Arrange
    artifact = await setup_approved_artifact(db_session)
    job = await create_test_git_sync_job(
        db_session, artifact.id, TEST_TENANT_ID, GitSyncJobStatus.completed
    )
    job.commit_sha = "abc123def456"
    job.completed_at = datetime.utcnow()
    await db_session.commit()
    await db_session.refresh(job)

    # Act
    response = await client.get(f"/git-sync/{job.id}")

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "completed"
    assert data["commit_sha"] == "abc123def456"
    assert data["completed_at"] is not None


@pytest.mark.asyncio
async def test_get_git_sync_status_failed(
    client: AsyncClient, db_session: AsyncSession
):
    """Test GET /git-sync/{job_id} returns failed status with error message"""
    # Arrange
    artifact = await setup_approved_artifact(db_session)
    job = await create_test_git_sync_job(
        db_session, artifact.id, TEST_TENANT_ID, GitSyncJobStatus.failed
    )
    job.error_message = "Authentication failed"
    job.retry_count = 3
    job.completed_at = datetime.utcnow()
    await db_session.commit()
    await db_session.refresh(job)

    # Act
    response = await client.get(f"/git-sync/{job.id}")

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "failed"
    assert data["error_message"] == "Authentication failed"
    assert data["retry_count"] == 3


# =============================================================================
# Test Case 3: Sync for non-existent artifact returns 404
# =============================================================================


@pytest.mark.asyncio
async def test_sync_nonexistent_artifact_returns_404(
    client: AsyncClient, valid_sync_request
):
    """Test POST /artifacts/{id}/sync-git with non-existent artifact returns 404"""
    # Act
    response = await client.post(
        "/artifacts/nonexistent-artifact-id/sync-git", json=valid_sync_request
    )

    # Assert
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "ARTIFACT_NOT_FOUND"


@pytest.mark.asyncio
async def test_sync_draft_artifact_returns_400(
    client: AsyncClient, db_session: AsyncSession, valid_sync_request
):
    """Test POST /artifacts/{id}/sync-git with draft (unapproved) artifact returns 400"""
    # Arrange
    artifact = await setup_draft_artifact(db_session)

    # Act
    response = await client.post(
        f"/artifacts/{artifact.id}/sync-git", json=valid_sync_request
    )

    # Assert
    assert response.status_code == 400

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "ARTIFACT_NOT_APPROVED"


@pytest.mark.asyncio
async def test_sync_invalid_repository_url_returns_400(
    client: AsyncClient, db_session: AsyncSession
):
    """Test POST /artifacts/{id}/sync-git with invalid repository URL returns 400"""
    # Arrange
    artifact = await setup_approved_artifact(db_session)
    invalid_request = {
        "repository_url": "not-a-valid-url",
        "branch": "main",
        "commit_message": "Test commit",
    }

    # Act
    response = await client.post(
        f"/artifacts/{artifact.id}/sync-git", json=invalid_request
    )

    # Assert
    assert response.status_code == 400

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_REPOSITORY_URL"


@pytest.mark.asyncio
async def test_get_nonexistent_job_returns_404(client: AsyncClient):
    """Test GET /git-sync/{job_id} with non-existent job returns 404"""
    # Act
    response = await client.get("/git-sync/nonexistent-job-id")

    # Assert
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "GIT_SYNC_JOB_NOT_FOUND"


# =============================================================================
# Test Case 4: Tenant isolation - Cannot sync other tenant's artifacts
# =============================================================================


@pytest.mark.asyncio
async def test_tenant_isolation_cannot_sync_other_tenant_artifact(
    client: AsyncClient, db_session: AsyncSession, valid_sync_request
):
    """
    Test that a tenant cannot sync artifacts belonging to another tenant.
    The client fixture is configured with tenant_id = "test-tenant-id".
    Artifact belongs to "other-tenant-id" should return 404.
    """
    # Arrange - Create artifact for a different tenant
    artifact = await setup_approved_artifact(db_session, tenant_id=OTHER_TENANT_ID)

    # Act - Try to sync with the test tenant's credentials
    response = await client.post(
        f"/artifacts/{artifact.id}/sync-git", json=valid_sync_request
    )

    # Assert - Should return 404 (artifact not found for this tenant)
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "ARTIFACT_NOT_FOUND"


@pytest.mark.asyncio
async def test_tenant_isolation_cannot_view_other_tenant_job(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Test that a tenant cannot view Git sync jobs belonging to another tenant.
    The client fixture is configured with tenant_id = "test-tenant-id".
    Job belongs to "other-tenant-id" should return 404.
    """
    # Arrange - Create artifact and job for a different tenant
    artifact = await setup_approved_artifact(db_session, tenant_id=OTHER_TENANT_ID)
    job = await create_test_git_sync_job(db_session, artifact.id, OTHER_TENANT_ID)

    # Act - Try to get job status with the test tenant's credentials
    response = await client.get(f"/git-sync/{job.id}")

    # Assert - Should return 404 (job not found for this tenant)
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "GIT_SYNC_JOB_NOT_FOUND"


@pytest.mark.asyncio
async def test_tenant_can_view_own_job(
    client: AsyncClient, db_session: AsyncSession
):
    """Test that a tenant can view their own Git sync jobs"""
    # Arrange - Create artifact and job for the test tenant
    artifact = await setup_approved_artifact(db_session, tenant_id=TEST_TENANT_ID)
    job = await create_test_git_sync_job(db_session, artifact.id, TEST_TENANT_ID)

    # Act
    response = await client.get(f"/git-sync/{job.id}")

    # Assert - Should succeed
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == job.id
    assert data["artifact_id"] == artifact.id


# =============================================================================
# Additional edge case tests
# =============================================================================


@pytest.mark.asyncio
async def test_sync_with_default_branch(
    client: AsyncClient, db_session: AsyncSession
):
    """Test POST /artifacts/{id}/sync-git uses default branch when not specified"""
    # Arrange
    artifact = await setup_approved_artifact(db_session)
    request_without_branch = {
        "repository_url": "https://github.com/test/repo.git",
        "commit_message": "Test commit",
    }

    # Act
    response = await client.post(
        f"/artifacts/{artifact.id}/sync-git", json=request_without_branch
    )

    # Assert
    assert response.status_code == 202

    # Verify the job was created with default branch "main"
    job_id = response.json()["sync_job_id"]
    from sqlmodel import select

    result = await db_session.execute(select(GitSyncJob).where(GitSyncJob.id == job_id))
    job = result.scalar_one_or_none()
    assert job.branch == "main"


@pytest.mark.asyncio
async def test_sync_multiple_jobs_for_same_artifact(
    client: AsyncClient, db_session: AsyncSession
):
    """Test that multiple sync jobs can be created for the same artifact"""
    # Arrange
    artifact = await setup_approved_artifact(db_session)
    request1 = {
        "repository_url": "https://github.com/test/repo1.git",
        "branch": "main",
        "commit_message": "First sync",
    }
    request2 = {
        "repository_url": "https://github.com/test/repo2.git",
        "branch": "develop",
        "commit_message": "Second sync",
    }

    # Act
    response1 = await client.post(f"/artifacts/{artifact.id}/sync-git", json=request1)
    response2 = await client.post(f"/artifacts/{artifact.id}/sync-git", json=request2)

    # Assert
    assert response1.status_code == 202
    assert response2.status_code == 202

    job_id1 = response1.json()["sync_job_id"]
    job_id2 = response2.json()["sync_job_id"]
    assert job_id1 != job_id2
