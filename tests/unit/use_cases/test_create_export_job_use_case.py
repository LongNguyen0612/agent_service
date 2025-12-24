"""
Unit tests for CreateExportJobUseCase (UC-30)
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from src.app.use_cases.exports import CreateExportJobUseCase
from src.domain.project import Project
from src.domain.task import Task
from src.domain.artifact import Artifact
from src.domain.export_job import ExportJob
from src.domain.enums import ProjectStatus, ArtifactType, ArtifactStatus, ExportJobStatus


@pytest.fixture
def mock_uow():
    """Create a mock unit of work"""
    uow = MagicMock()
    uow.__aenter__ = AsyncMock(return_value=uow)
    uow.__aexit__ = AsyncMock()
    uow.commit = AsyncMock()
    uow.rollback = AsyncMock()
    uow.projects = MagicMock()
    uow.tasks = MagicMock()
    uow.artifacts = MagicMock()
    uow.export_jobs = MagicMock()
    return uow


@pytest.fixture
def sample_project():
    """Create a sample project"""
    return Project(
        id="project-123",
        tenant_id="tenant-789",
        name="Test Project",
        description="Test Description",
        status=ProjectStatus.active,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_task():
    """Create a sample task"""
    return Task(
        id="task-123",
        project_id="project-123",
        tenant_id="tenant-789",
        title="Test Task",
        input_spec={"requirement": "test"},
    )


@pytest.fixture
def approved_artifact():
    """Create an approved artifact"""
    return Artifact(
        id="artifact-1",
        task_id="task-123",
        pipeline_run_id="run-1",
        step_run_id="step-1",
        artifact_type=ArtifactType.CODE_FILES,
        status=ArtifactStatus.approved,
        version=1,
        content={"files": [{"filename": "test.py", "content": "print('hello')"}]},
        created_at=datetime.utcnow(),
        approved_at=datetime.utcnow(),
    )


@pytest.fixture
def draft_artifact():
    """Create a draft artifact"""
    return Artifact(
        id="artifact-2",
        task_id="task-123",
        pipeline_run_id="run-1",
        step_run_id="step-1",
        artifact_type=ArtifactType.CODE_FILES,
        status=ArtifactStatus.draft,
        version=1,
        created_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_create_export_job_success(mock_uow, sample_project, sample_task, approved_artifact):
    """AC-3.1.1: Successfully create export job for project with approved artifacts"""
    # Arrange
    mock_uow.projects.get_by_id = AsyncMock(return_value=sample_project)
    mock_uow.tasks.find_by_project_id = AsyncMock(return_value=[sample_task])
    mock_uow.artifacts.get_by_task = AsyncMock(return_value=[approved_artifact])

    export_job = ExportJob(
        id="job-123",
        project_id="project-123",
        tenant_id="tenant-789",
        status=ExportJobStatus.pending,
        created_at=datetime.utcnow(),
    )
    mock_uow.export_jobs.create = AsyncMock(return_value=export_job)

    use_case = CreateExportJobUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("project-123")

    # Assert
    assert result.is_ok()
    assert result.value.export_job_id == "job-123"
    assert result.value.status == "pending"

    mock_uow.export_jobs.create.assert_called_once()
    mock_uow.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_export_job_project_not_found(mock_uow):
    """Project not found returns error"""
    # Arrange
    mock_uow.projects.get_by_id = AsyncMock(return_value=None)

    use_case = CreateExportJobUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("nonexistent-project")

    # Assert
    assert result.is_err()
    assert result.error.code == "PROJECT_NOT_FOUND"
    mock_uow.export_jobs.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_export_job_no_tasks(mock_uow, sample_project):
    """No tasks in project returns error"""
    # Arrange
    mock_uow.projects.get_by_id = AsyncMock(return_value=sample_project)
    mock_uow.tasks.find_by_project_id = AsyncMock(return_value=[])

    use_case = CreateExportJobUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("project-123")

    # Assert
    assert result.is_err()
    assert result.error.code == "NO_ARTIFACTS"
    mock_uow.export_jobs.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_export_job_no_approved_artifacts(
    mock_uow, sample_project, sample_task, draft_artifact
):
    """No approved artifacts returns error"""
    # Arrange
    mock_uow.projects.get_by_id = AsyncMock(return_value=sample_project)
    mock_uow.tasks.find_by_project_id = AsyncMock(return_value=[sample_task])
    mock_uow.artifacts.get_by_task = AsyncMock(return_value=[draft_artifact])

    use_case = CreateExportJobUseCase(mock_uow, tenant_id="tenant-789")

    # Act
    result = await use_case.execute("project-123")

    # Assert
    assert result.is_err()
    assert result.error.code == "NO_APPROVED_ARTIFACTS"
    mock_uow.export_jobs.create.assert_not_called()


@pytest.mark.asyncio
async def test_create_export_job_tenant_isolation(mock_uow, sample_project):
    """Tenant isolation - project from other tenant returns not found"""
    # Arrange
    mock_uow.projects.get_by_id = AsyncMock(return_value=None)

    use_case = CreateExportJobUseCase(mock_uow, tenant_id="different-tenant")

    # Act
    result = await use_case.execute("project-123")

    # Assert
    assert result.is_err()
    assert result.error.code == "PROJECT_NOT_FOUND"
