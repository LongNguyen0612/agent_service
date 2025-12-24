import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession
from src.domain.project import Project
from src.domain.task import Task
from src.domain.pipeline_run import PipelineRun
from src.domain.pipeline_step import PipelineStepRun
from src.domain.artifact import Artifact
from src.domain.enums import (
    ProjectStatus,
    TaskStatus,
    PipelineRunStatus,
    ArtifactType,
    StepStatus,
    StepType,
)
from datetime import datetime


@pytest.mark.asyncio
async def test_compare_artifacts_success(client: AsyncClient, db_session: AsyncSession):
    """Test GET /tasks/{id}/artifacts/compare returns artifact versions"""
    # Arrange - Create project, task, pipeline runs, and artifacts
    tenant_id = "test-tenant-id"

    # Create project
    project = Project(
        id="project-artifact-1",
        tenant_id=tenant_id,
        name="Test Project",
        status=ProjectStatus.active,
    )
    db_session.add(project)

    # Create task
    task = Task(
        id="task-artifact-1",
        tenant_id=tenant_id,
        project_id=project.id,
        title="Test Task",
        input_spec={"requirement": "Build something"},
        status=TaskStatus.completed,
    )
    db_session.add(task)
    await db_session.flush()  # Flush to ensure task exists before creating dependencies

    # Create 3 pipeline runs
    run1 = PipelineRun(
        id="run-artifact-1",
        task_id=task.id,
        tenant_id=tenant_id,
        status=PipelineRunStatus.completed,
        started_at=datetime(2025, 1, 1, 9, 0, 0),
    )
    run2 = PipelineRun(
        id="run-artifact-2",
        task_id=task.id,
        tenant_id=tenant_id,
        status=PipelineRunStatus.completed,
        started_at=datetime(2025, 1, 1, 10, 0, 0),
    )
    run3 = PipelineRun(
        id="run-artifact-3",
        task_id=task.id,
        tenant_id=tenant_id,
        status=PipelineRunStatus.completed,
        started_at=datetime(2025, 1, 1, 11, 0, 0),
    )
    db_session.add_all([run1, run2, run3])
    await db_session.flush()  # Flush to ensure runs exist before creating steps

    # Create pipeline step runs
    step_run1 = PipelineStepRun(
        id="step-run-1",
        pipeline_run_id=run1.id,
        step_number=2,
        step_name="ANALYSIS",
        step_type=StepType.ANALYSIS,
        status=StepStatus.completed,
    )
    step_run2 = PipelineStepRun(
        id="step-run-2",
        pipeline_run_id=run2.id,
        step_number=2,
        step_name="ANALYSIS",
        step_type=StepType.ANALYSIS,
        status=StepStatus.completed,
    )
    step_run3 = PipelineStepRun(
        id="step-run-3",
        pipeline_run_id=run3.id,
        step_number=2,
        step_name="ANALYSIS",
        step_type=StepType.ANALYSIS,
        status=StepStatus.completed,
    )
    db_session.add_all([step_run1, step_run2, step_run3])
    await db_session.flush()  # Flush to ensure steps exist before creating artifacts

    # Create 3 document artifacts (different versions) with new schema
    artifact1 = Artifact(
        id="artifact-doc-1",
        task_id=task.id,
        pipeline_run_id=run1.id,
        step_run_id=step_run1.id,
        artifact_type=ArtifactType.document,
        version=1,
        content={
            "url": "/artifacts/task-artifact-1/document_v1.txt",
            "metadata": {"size": 1024}
        },
        created_at=datetime(2025, 1, 1, 9, 5, 0),
    )
    artifact2 = Artifact(
        id="artifact-doc-2",
        task_id=task.id,
        pipeline_run_id=run2.id,
        step_run_id=step_run2.id,
        artifact_type=ArtifactType.document,
        version=2,
        content={
            "url": "/artifacts/task-artifact-1/document_v2.txt",
            "metadata": {"size": 2048}
        },
        created_at=datetime(2025, 1, 1, 10, 5, 0),
    )
    artifact3 = Artifact(
        id="artifact-doc-3",
        task_id=task.id,
        pipeline_run_id=run3.id,
        step_run_id=step_run3.id,
        artifact_type=ArtifactType.document,
        version=3,
        content={
            "url": "/artifacts/task-artifact-1/document_v3.txt",
            "metadata": {"size": 3072}
        },
        created_at=datetime(2025, 1, 1, 11, 5, 0),
    )
    db_session.add_all([artifact1, artifact2, artifact3])

    # Store ID before commit
    task_id = task.id

    await db_session.commit()

    # Act
    response = await client.get(
        f"/tasks/{task_id}/artifacts/compare?tenant_id={tenant_id}&type=document"
    )

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert data["task_id"] == task_id
    assert data["artifact_type"] == "document"
    assert len(data["versions"]) == 3

    # Verify versions are in ascending order
    assert data["versions"][0]["version"] == 1
    assert data["versions"][1]["version"] == 2
    assert data["versions"][2]["version"] == 3

    # Verify version 1 details
    v1 = data["versions"][0]
    assert v1["id"] == "artifact-doc-1"
    assert v1["pipeline_run_id"] == "run-artifact-1"
    assert v1["step_run_id"] == "step-run-1"


@pytest.mark.asyncio
async def test_compare_artifacts_empty_list(client: AsyncClient, db_session: AsyncSession):
    """Test GET /tasks/{id}/artifacts/compare with no artifacts returns empty list"""
    # Arrange - Create task without artifacts
    tenant_id = "test-tenant-id"

    project = Project(
        id="project-empty",
        tenant_id=tenant_id,
        name="Test Project",
        status=ProjectStatus.active,
    )
    db_session.add(project)

    task = Task(
        id="task-empty",
        tenant_id=tenant_id,
        project_id=project.id,
        title="Test Task",
        input_spec={"requirement": "Build something"},
        status=TaskStatus.draft,
    )
    db_session.add(task)
    await db_session.flush()  # Flush to ensure task exists before querying

    # Store ID before commit
    task_id = task.id

    await db_session.commit()

    # Act
    response = await client.get(
        f"/tasks/{task_id}/artifacts/compare?tenant_id={tenant_id}&type=document"
    )

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert data["task_id"] == task_id
    assert data["artifact_type"] == "document"
    assert len(data["versions"]) == 0


@pytest.mark.asyncio
async def test_compare_artifacts_task_not_found(client: AsyncClient):
    """Test GET /tasks/{id}/artifacts/compare with non-existent task returns 404"""
    # Act
    response = await client.get(
        "/tasks/non-existent/artifacts/compare?tenant_id=tenant-123&type=document"
    )

    # Assert
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "TASK_NOT_FOUND"


@pytest.mark.asyncio
async def test_compare_artifacts_invalid_type(client: AsyncClient, db_session: AsyncSession):
    """Test GET /tasks/{id}/artifacts/compare with invalid artifact type returns 400"""
    # Arrange - Create task
    tenant_id = "test-tenant-id"

    project = Project(
        id="project-invalid",
        tenant_id=tenant_id,
        name="Test Project",
        status=ProjectStatus.active,
    )
    db_session.add(project)

    task = Task(
        id="task-invalid",
        tenant_id=tenant_id,
        project_id=project.id,
        title="Test Task",
        input_spec={"requirement": "Test"},
        status=TaskStatus.draft,
    )
    db_session.add(task)
    await db_session.flush()  # Flush to ensure task exists before querying

    # Store ID before commit
    task_id = task.id

    await db_session.commit()

    # Act
    response = await client.get(
        f"/tasks/{task_id}/artifacts/compare?tenant_id={tenant_id}&type=invalid_type"
    )

    # Assert
    assert response.status_code == 400

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_ARTIFACT_TYPE"


@pytest.mark.asyncio
async def test_compare_artifacts_filter_by_type(
    client: AsyncClient, db_session: AsyncSession
):
    """Test that artifacts are correctly filtered by type"""
    # Arrange - Create task with document and code artifacts
    tenant_id = "test-tenant-id"

    project = Project(
        id="project-filter",
        tenant_id=tenant_id,
        name="Test Project",
        status=ProjectStatus.active,
    )
    db_session.add(project)

    task = Task(
        id="task-filter",
        tenant_id=tenant_id,
        project_id=project.id,
        title="Test Task",
        input_spec={"requirement": "Test"},
        status=TaskStatus.completed,
    )
    db_session.add(task)
    await db_session.flush()  # Flush to ensure task exists before creating dependencies

    run = PipelineRun(
        id="run-filter",
        task_id=task.id,
        tenant_id=tenant_id,
        status=PipelineRunStatus.completed,
        started_at=datetime(2025, 1, 1, 10, 0, 0),
    )
    db_session.add(run)
    await db_session.flush()  # Flush to ensure run exists before creating steps

    # Create pipeline step runs
    step_run_doc = PipelineStepRun(
        id="step-run-filter-doc",
        pipeline_run_id=run.id,
        step_number=2,
        step_name="ANALYSIS",
        step_type=StepType.ANALYSIS,
        status=StepStatus.completed,
    )
    step_run_code = PipelineStepRun(
        id="step-run-filter-code",
        pipeline_run_id=run.id,
        step_number=3,
        step_name="CODE_SKELETON",
        step_type=StepType.CODE_SKELETON,
        status=StepStatus.completed,
    )
    db_session.add_all([step_run_doc, step_run_code])
    await db_session.flush()  # Flush to ensure steps exist before creating artifacts

    # Create document artifacts with new schema
    doc1 = Artifact(
        id="doc-1",
        task_id=task.id,
        pipeline_run_id=run.id,
        step_run_id=step_run_doc.id,
        artifact_type=ArtifactType.document,
        version=1,
        content={"url": "/doc_v1.txt"},
        created_at=datetime(2025, 1, 1, 10, 1, 0),
    )
    doc2 = Artifact(
        id="doc-2",
        task_id=task.id,
        pipeline_run_id=run.id,
        step_run_id=step_run_doc.id,
        artifact_type=ArtifactType.document,
        version=2,
        content={"url": "/doc_v2.txt"},
        created_at=datetime(2025, 1, 1, 10, 2, 0),
    )

    # Create code artifact with new schema
    code1 = Artifact(
        id="code-1",
        task_id=task.id,
        pipeline_run_id=run.id,
        step_run_id=step_run_code.id,
        artifact_type=ArtifactType.code,
        version=1,
        content={"url": "/code_v1.py"},
        created_at=datetime(2025, 1, 1, 10, 3, 0),
    )

    db_session.add_all([doc1, doc2, code1])

    # Store ID before commit
    task_id = task.id

    await db_session.commit()

    # Act - Request document artifacts
    response_doc = await client.get(
        f"/tasks/{task_id}/artifacts/compare?tenant_id={tenant_id}&type=document"
    )

    # Assert - Should only get document artifacts
    assert response_doc.status_code == 200
    doc_data = response_doc.json()
    assert len(doc_data["versions"]) == 2
    assert doc_data["versions"][0]["id"] == "doc-1"
    assert doc_data["versions"][1]["id"] == "doc-2"

    # Act - Request code artifacts
    response_code = await client.get(
        f"/tasks/{task_id}/artifacts/compare?tenant_id={tenant_id}&type=code"
    )

    # Assert - Should only get code artifacts
    assert response_code.status_code == 200
    code_data = response_code.json()
    assert len(code_data["versions"]) == 1
    assert code_data["versions"][0]["id"] == "code-1"
