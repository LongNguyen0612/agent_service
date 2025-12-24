import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.app.use_cases.tasks import CreateTaskUseCase, CreateTaskCommand
from src.app.services.input_spec_validator import InputSpecValidator
from src.domain import Task, Project, TaskStatus, ProjectStatus
from libs.result import Return, Error


@pytest.mark.asyncio
async def test_create_task_success(mock_uow):
    """Test successful task creation"""
    # Arrange
    mock_audit_service = AsyncMock()
    input_spec_validator = InputSpecValidator()
    use_case = CreateTaskUseCase(mock_uow, mock_audit_service, input_spec_validator)

    command = CreateTaskCommand(
        project_id="project-123",
        title="Test Task",
        input_spec={"requirement": "Build a feature", "priority": "high"},
        tenant_id="tenant-123",
        user_id="user-456",
    )

    # Mock existing project
    existing_project = Project(
        id="project-123",
        tenant_id="tenant-123",
        name="Test Project",
        status=ProjectStatus.active,
    )

    # Mock created task
    mock_task = Task(
        id="task-789",
        project_id="project-123",
        tenant_id="tenant-123",
        title="Test Task",
        input_spec={"requirement": "Build a feature", "priority": "high"},
        status=TaskStatus.draft,
    )

    # Mock the repositories
    with patch(
        "src.app.use_cases.tasks.create_task_use_case.SqlAlchemyProjectRepository"
    ) as MockProjectRepo, patch(
        "src.app.use_cases.tasks.create_task_use_case.SqlAlchemyTaskRepository"
    ) as MockTaskRepo:
        mock_project_repo_instance = MockProjectRepo.return_value
        mock_project_repo_instance.get_by_id = AsyncMock(return_value=existing_project)

        mock_task_repo_instance = MockTaskRepo.return_value
        mock_task_repo_instance.create = AsyncMock(return_value=mock_task)

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.id == "task-789"
        assert result.value.title == "Test Task"
        assert result.value.project_id == "project-123"
        assert result.value.tenant_id == "tenant-123"
        assert result.value.status == TaskStatus.draft
        assert result.value.input_spec == {"requirement": "Build a feature", "priority": "high"}

        # Verify project was checked
        mock_project_repo_instance.get_by_id.assert_called_once_with("project-123")

        # Verify task was created
        mock_task_repo_instance.create.assert_called_once()

        # Verify commit was called
        mock_uow.commit.assert_called_once()

        # Verify audit event was logged
        mock_audit_service.log_event.assert_called_once()
        call_args = mock_audit_service.log_event.call_args[1]
        assert call_args["event_type"] == "task_created"
        assert call_args["resource_id"] == "task-789"


@pytest.mark.asyncio
async def test_create_task_empty_title(mock_uow):
    """Test task creation with empty title returns error"""
    # Arrange
    mock_audit_service = AsyncMock()
    input_spec_validator = InputSpecValidator()
    use_case = CreateTaskUseCase(mock_uow, mock_audit_service, input_spec_validator)

    command = CreateTaskCommand(
        project_id="project-123",
        title="",
        input_spec={"requirement": "Build a feature"},
        tenant_id="tenant-123",
        user_id="user-456",
    )

    # Act
    result = await use_case.execute(command)

    # Assert
    assert result.is_err()
    assert result.error.code == "INVALID_INPUT"
    assert "title cannot be empty" in result.error.message.lower()

    # Verify no audit event was logged
    mock_audit_service.log_event.assert_not_called()


@pytest.mark.asyncio
async def test_create_task_invalid_input_spec(mock_uow):
    """Test task creation with invalid input_spec returns error"""
    # Arrange
    mock_audit_service = AsyncMock()
    input_spec_validator = InputSpecValidator()
    use_case = CreateTaskUseCase(mock_uow, mock_audit_service, input_spec_validator)

    command = CreateTaskCommand(
        project_id="project-123",
        title="Test Task",
        input_spec={},  # Empty input_spec is invalid
        tenant_id="tenant-123",
        user_id="user-456",
    )

    # Act
    result = await use_case.execute(command)

    # Assert
    assert result.is_err()
    assert result.error.code == "INVALID_INPUT_SPEC"
    assert "cannot be empty" in result.error.message.lower()


@pytest.mark.asyncio
async def test_create_task_project_not_found(mock_uow):
    """Test task creation when project doesn't exist"""
    # Arrange
    mock_audit_service = AsyncMock()
    input_spec_validator = InputSpecValidator()
    use_case = CreateTaskUseCase(mock_uow, mock_audit_service, input_spec_validator)

    command = CreateTaskCommand(
        project_id="non-existent-project",
        title="Test Task",
        input_spec={"requirement": "Build a feature"},
        tenant_id="tenant-123",
        user_id="user-456",
    )

    # Mock the repositories
    with patch(
        "src.app.use_cases.tasks.create_task_use_case.SqlAlchemyProjectRepository"
    ) as MockProjectRepo:
        mock_project_repo_instance = MockProjectRepo.return_value
        mock_project_repo_instance.get_by_id = AsyncMock(return_value=None)

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_err()
        assert result.error.code == "PROJECT_NOT_FOUND"
        assert "non-existent-project" in result.error.message


@pytest.mark.asyncio
async def test_create_task_project_not_active(mock_uow):
    """Test task creation fails when project is archived"""
    # Arrange
    mock_audit_service = AsyncMock()
    input_spec_validator = InputSpecValidator()
    use_case = CreateTaskUseCase(mock_uow, mock_audit_service, input_spec_validator)

    command = CreateTaskCommand(
        project_id="project-123",
        title="Test Task",
        input_spec={"requirement": "Build a feature"},
        tenant_id="tenant-123",
        user_id="user-456",
    )

    # Mock archived project
    archived_project = Project(
        id="project-123",
        tenant_id="tenant-123",
        name="Archived Project",
        status=ProjectStatus.archived,
    )

    # Mock the repositories
    with patch(
        "src.app.use_cases.tasks.create_task_use_case.SqlAlchemyProjectRepository"
    ) as MockProjectRepo:
        mock_project_repo_instance = MockProjectRepo.return_value
        mock_project_repo_instance.get_by_id = AsyncMock(return_value=archived_project)

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_err()
        assert result.error.code == "PROJECT_NOT_ACTIVE"
        assert "non-active project" in result.error.message.lower()


@pytest.mark.asyncio
async def test_create_task_tenant_isolation(mock_uow):
    """Test that task creation respects tenant isolation"""
    # Arrange
    mock_audit_service = AsyncMock()
    input_spec_validator = InputSpecValidator()
    use_case = CreateTaskUseCase(mock_uow, mock_audit_service, input_spec_validator)

    command = CreateTaskCommand(
        project_id="project-123",
        title="Test Task",
        input_spec={"requirement": "Build a feature"},
        tenant_id="tenant-999",  # Different tenant
        user_id="user-456",
    )

    # Mock the repositories
    with patch(
        "src.app.use_cases.tasks.create_task_use_case.SqlAlchemyProjectRepository"
    ) as MockProjectRepo:
        mock_project_repo_instance = MockProjectRepo.return_value
        mock_project_repo_instance.get_by_id = AsyncMock(return_value=None)

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_err()
        assert result.error.code == "PROJECT_NOT_FOUND"

        # Verify get_by_id was called with project_id
        mock_project_repo_instance.get_by_id.assert_called_once_with("project-123")
