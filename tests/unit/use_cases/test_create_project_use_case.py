import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.app.use_cases.projects import CreateProjectUseCase, CreateProjectCommand
from src.domain import Project, ProjectStatus


@pytest.mark.asyncio
async def test_create_project_success(mock_uow):
    """Test successful project creation"""
    # Arrange
    mock_audit_service = AsyncMock()
    use_case = CreateProjectUseCase(mock_uow, mock_audit_service)

    command = CreateProjectCommand(
        name="Test Project",
        description="A test project",
        tenant_id="tenant-123",
        user_id="user-456",
    )

    # Create a mock project that will be returned
    mock_project = Project(
        id="project-789",
        tenant_id="tenant-123",
        name="Test Project",
        description="A test project",
        status=ProjectStatus.active,
    )

    # Mock the repository
    with patch(
        "src.app.use_cases.projects.create_project_use_case.SqlAlchemyProjectRepository"
    ) as MockRepo:
        mock_repo_instance = MockRepo.return_value
        mock_repo_instance.create = AsyncMock(return_value=mock_project)

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.id == "project-789"
        assert result.value.name == "Test Project"
        assert result.value.description == "A test project"
        assert result.value.tenant_id == "tenant-123"
        assert result.value.status == ProjectStatus.active

        # Verify repository create was called
        mock_repo_instance.create.assert_called_once()

        # Verify commit was called
        mock_uow.commit.assert_called_once()

        # Verify audit event was logged
        mock_audit_service.log_event.assert_called_once_with(
            event_type="project_created",
            tenant_id="tenant-123",
            user_id="user-456",
            resource_type="project",
            resource_id="project-789",
            metadata={"project_name": "Test Project"},
        )


@pytest.mark.asyncio
async def test_create_project_empty_name(mock_uow):
    """Test project creation with empty name returns error"""
    # Arrange
    mock_audit_service = AsyncMock()
    use_case = CreateProjectUseCase(mock_uow, mock_audit_service)

    command = CreateProjectCommand(
        name="",
        description="A test project",
        tenant_id="tenant-123",
        user_id="user-456",
    )

    # Act
    result = await use_case.execute(command)

    # Assert
    assert result.is_err()
    assert result.error.code == "INVALID_INPUT"
    assert "name cannot be empty" in result.error.message.lower()

    # Verify no audit event was logged
    mock_audit_service.log_event.assert_not_called()


@pytest.mark.asyncio
async def test_create_project_whitespace_name(mock_uow):
    """Test project creation with whitespace-only name returns error"""
    # Arrange
    mock_audit_service = AsyncMock()
    use_case = CreateProjectUseCase(mock_uow, mock_audit_service)

    command = CreateProjectCommand(
        name="   ",
        description="A test project",
        tenant_id="tenant-123",
        user_id="user-456",
    )

    # Act
    result = await use_case.execute(command)

    # Assert
    assert result.is_err()
    assert result.error.code == "INVALID_INPUT"
