import pytest
from unittest.mock import AsyncMock, patch
from src.app.use_cases.tasks import ListProjectTasksUseCase, ListProjectTasksCommand
from src.domain import Task, TaskStatus


@pytest.mark.asyncio
async def test_list_project_tasks_success(mock_uow):
    """Test successful listing of project tasks"""
    # Arrange
    use_case = ListProjectTasksUseCase(mock_uow)

    command = ListProjectTasksCommand(
        project_id="project-123",
        tenant_id="tenant-123",
        status=None,  # No filtering
    )

    # Mock tasks
    mock_tasks = [
        Task(
            id="task-1",
            project_id="project-123",
            tenant_id="tenant-123",
            title="Task 1",
            input_spec={"requirement": "Test 1"},
            status=TaskStatus.draft,
        ),
        Task(
            id="task-2",
            project_id="project-123",
            tenant_id="tenant-123",
            title="Task 2",
            input_spec={"requirement": "Test 2"},
            status=TaskStatus.completed,
        ),
        Task(
            id="task-3",
            project_id="project-123",
            tenant_id="tenant-123",
            title="Task 3",
            input_spec={"requirement": "Test 3"},
            status=TaskStatus.running,
        ),
    ]

    # Mock the repository
    with patch(
        "src.app.use_cases.tasks.list_project_tasks_use_case.SqlAlchemyTaskRepository"
    ) as MockTaskRepo:
        mock_task_repo_instance = MockTaskRepo.return_value
        mock_task_repo_instance.find_by_project_id = AsyncMock(return_value=mock_tasks)

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert len(result.value.tasks) == 3
        assert result.value.tasks[0].id == "task-1"
        assert result.value.tasks[0].title == "Task 1"
        assert result.value.tasks[0].status == TaskStatus.draft
        assert result.value.tasks[1].id == "task-2"
        assert result.value.tasks[2].id == "task-3"

        # Verify repository was called correctly
        mock_task_repo_instance.find_by_project_id.assert_called_once_with(
            "project-123", "tenant-123", status=None
        )


@pytest.mark.asyncio
async def test_list_project_tasks_empty_project(mock_uow):
    """Test listing tasks for an empty project returns empty array"""
    # Arrange
    use_case = ListProjectTasksUseCase(mock_uow)

    command = ListProjectTasksCommand(
        project_id="empty-project",
        tenant_id="tenant-123",
        status=None,
    )

    # Mock the repository to return empty list
    with patch(
        "src.app.use_cases.tasks.list_project_tasks_use_case.SqlAlchemyTaskRepository"
    ) as MockTaskRepo:
        mock_task_repo_instance = MockTaskRepo.return_value
        mock_task_repo_instance.find_by_project_id = AsyncMock(return_value=[])

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.tasks == []
        assert len(result.value.tasks) == 0


@pytest.mark.asyncio
async def test_list_project_tasks_with_status_filter(mock_uow):
    """Test listing tasks with status filter"""
    # Arrange
    use_case = ListProjectTasksUseCase(mock_uow)

    command = ListProjectTasksCommand(
        project_id="project-123",
        tenant_id="tenant-123",
        status=TaskStatus.completed,  # Filter by completed
    )

    # Mock only completed tasks
    mock_tasks = [
        Task(
            id="task-2",
            project_id="project-123",
            tenant_id="tenant-123",
            title="Completed Task",
            input_spec={"requirement": "Test 2"},
            status=TaskStatus.completed,
        ),
    ]

    # Mock the repository
    with patch(
        "src.app.use_cases.tasks.list_project_tasks_use_case.SqlAlchemyTaskRepository"
    ) as MockTaskRepo:
        mock_task_repo_instance = MockTaskRepo.return_value
        mock_task_repo_instance.find_by_project_id = AsyncMock(return_value=mock_tasks)

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert len(result.value.tasks) == 1
        assert result.value.tasks[0].status == TaskStatus.completed

        # Verify repository was called with status filter
        mock_task_repo_instance.find_by_project_id.assert_called_once_with(
            "project-123", "tenant-123", status="completed"
        )


@pytest.mark.asyncio
async def test_list_project_tasks_tenant_isolation(mock_uow):
    """Test that listing respects tenant isolation"""
    # Arrange
    use_case = ListProjectTasksUseCase(mock_uow)

    command = ListProjectTasksCommand(
        project_id="project-123",
        tenant_id="tenant-999",  # Different tenant
        status=None,
    )

    # Mock the repository to return empty (no tasks for this tenant)
    with patch(
        "src.app.use_cases.tasks.list_project_tasks_use_case.SqlAlchemyTaskRepository"
    ) as MockTaskRepo:
        mock_task_repo_instance = MockTaskRepo.return_value
        mock_task_repo_instance.find_by_project_id = AsyncMock(return_value=[])

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.tasks == []

        # Verify repository was called with correct tenant_id
        mock_task_repo_instance.find_by_project_id.assert_called_once_with(
            "project-123", "tenant-999", status=None
        )
