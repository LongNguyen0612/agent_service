import pytest
from unittest.mock import AsyncMock, patch
from src.app.use_cases.projects import UpdateProjectUseCase, UpdateProjectCommand
from src.domain import Project, ProjectStatus


@pytest.mark.asyncio
async def test_update_project_success(mock_uow):
    """Test successful project update"""
    # Arrange
    mock_audit_service = AsyncMock()
    use_case = UpdateProjectUseCase(mock_uow, mock_audit_service)

    command = UpdateProjectCommand(
        project_id="project-789",
        name="Updated Project Name",
        description="Updated description",
        status=None,
        tenant_id="tenant-123",
        user_id="user-456",
    )

    # Create existing project
    existing_project = Project(
        id="project-789",
        tenant_id="tenant-123",
        name="Original Project",
        description="Original description",
        status=ProjectStatus.active,
    )

    # Mock the repository
    with patch(
        "src.app.use_cases.projects.update_project_use_case.SqlAlchemyProjectRepository"
    ) as MockRepo:
        mock_repo_instance = MockRepo.return_value
        mock_repo_instance.get_by_id = AsyncMock(return_value=existing_project)
        mock_repo_instance.update = AsyncMock(return_value=existing_project)

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.id == "project-789"
        assert result.value.name == "Updated Project Name"
        assert result.value.description == "Updated description"
        assert result.value.tenant_id == "tenant-123"

        # Verify get_by_id was called with correct parameters
        mock_repo_instance.get_by_id.assert_called_once_with("project-789", "tenant-123")

        # Verify update was called
        mock_repo_instance.update.assert_called_once()

        # Verify commit was called
        mock_uow.commit.assert_called_once()

        # Verify audit event was logged
        mock_audit_service.log_event.assert_called_once()
        call_args = mock_audit_service.log_event.call_args[1]
        assert call_args["event_type"] == "project_updated"
        assert call_args["tenant_id"] == "tenant-123"
        assert call_args["user_id"] == "user-456"
        assert call_args["resource_id"] == "project-789"


@pytest.mark.asyncio
async def test_update_project_not_found(mock_uow):
    """Test update project when project doesn't exist"""
    # Arrange
    mock_audit_service = AsyncMock()
    use_case = UpdateProjectUseCase(mock_uow, mock_audit_service)

    command = UpdateProjectCommand(
        project_id="non-existent-id",
        name="Updated Project Name",
        description=None,
        status=None,
        tenant_id="tenant-123",
        user_id="user-456",
    )

    # Mock the repository to return None (project not found)
    with patch(
        "src.app.use_cases.projects.update_project_use_case.SqlAlchemyProjectRepository"
    ) as MockRepo:
        mock_repo_instance = MockRepo.return_value
        mock_repo_instance.get_by_id = AsyncMock(return_value=None)

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_err()
        assert result.error.code == "NOT_FOUND"
        assert "non-existent-id" in result.error.message

        # Verify update was not called
        mock_repo_instance.update.assert_not_called()

        # Verify commit was not called
        mock_uow.commit.assert_not_called()

        # Verify no audit event was logged
        mock_audit_service.log_event.assert_not_called()


@pytest.mark.asyncio
async def test_update_project_empty_name(mock_uow):
    """Test update project with empty name returns error"""
    # Arrange
    mock_audit_service = AsyncMock()
    use_case = UpdateProjectUseCase(mock_uow, mock_audit_service)

    command = UpdateProjectCommand(
        project_id="project-789",
        name="",
        description=None,
        status=None,
        tenant_id="tenant-123",
        user_id="user-456",
    )

    # Create existing project
    existing_project = Project(
        id="project-789",
        tenant_id="tenant-123",
        name="Original Project",
        description="Original description",
        status=ProjectStatus.active,
    )

    # Mock the repository
    with patch(
        "src.app.use_cases.projects.update_project_use_case.SqlAlchemyProjectRepository"
    ) as MockRepo:
        mock_repo_instance = MockRepo.return_value
        mock_repo_instance.get_by_id = AsyncMock(return_value=existing_project)

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_err()
        assert result.error.code == "INVALID_INPUT"
        assert "name cannot be empty" in result.error.message.lower()

        # Verify update was not called
        mock_repo_instance.update.assert_not_called()

        # Verify no audit event was logged
        mock_audit_service.log_event.assert_not_called()


@pytest.mark.asyncio
async def test_update_project_partial_update(mock_uow):
    """Test partial project update (only description)"""
    # Arrange
    mock_audit_service = AsyncMock()
    use_case = UpdateProjectUseCase(mock_uow, mock_audit_service)

    command = UpdateProjectCommand(
        project_id="project-789",
        name=None,  # Don't update name
        description="Only update description",
        status=None,
        tenant_id="tenant-123",
        user_id="user-456",
    )

    # Create existing project
    existing_project = Project(
        id="project-789",
        tenant_id="tenant-123",
        name="Original Project",
        description="Original description",
        status=ProjectStatus.active,
    )

    # Mock the repository
    with patch(
        "src.app.use_cases.projects.update_project_use_case.SqlAlchemyProjectRepository"
    ) as MockRepo:
        mock_repo_instance = MockRepo.return_value
        mock_repo_instance.get_by_id = AsyncMock(return_value=existing_project)
        mock_repo_instance.update = AsyncMock(return_value=existing_project)

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.name == "Original Project"  # Name unchanged
        assert result.value.description == "Only update description"  # Description updated

        # Verify update was called
        mock_repo_instance.update.assert_called_once()

        # Verify commit was called
        mock_uow.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_project_status_change(mock_uow):
    """Test updating project status"""
    # Arrange
    mock_audit_service = AsyncMock()
    use_case = UpdateProjectUseCase(mock_uow, mock_audit_service)

    command = UpdateProjectCommand(
        project_id="project-789",
        name=None,
        description=None,
        status=ProjectStatus.archived,  # Change status
        tenant_id="tenant-123",
        user_id="user-456",
    )

    # Create existing project
    existing_project = Project(
        id="project-789",
        tenant_id="tenant-123",
        name="Original Project",
        description="Original description",
        status=ProjectStatus.active,
    )

    # Mock the repository
    with patch(
        "src.app.use_cases.projects.update_project_use_case.SqlAlchemyProjectRepository"
    ) as MockRepo:
        mock_repo_instance = MockRepo.return_value
        mock_repo_instance.get_by_id = AsyncMock(return_value=existing_project)
        mock_repo_instance.update = AsyncMock(return_value=existing_project)

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_ok()
        assert result.value.status == ProjectStatus.archived

        # Verify update was called
        mock_repo_instance.update.assert_called_once()

        # Verify commit was called
        mock_uow.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_project_tenant_isolation(mock_uow):
    """Test that project update respects tenant isolation"""
    # Arrange
    mock_audit_service = AsyncMock()
    use_case = UpdateProjectUseCase(mock_uow, mock_audit_service)

    command = UpdateProjectCommand(
        project_id="project-789",
        name="Updated Name",
        description=None,
        status=None,
        tenant_id="tenant-999",  # Different tenant
        user_id="user-456",
    )

    # Mock the repository to return None (project not found in this tenant)
    with patch(
        "src.app.use_cases.projects.update_project_use_case.SqlAlchemyProjectRepository"
    ) as MockRepo:
        mock_repo_instance = MockRepo.return_value
        mock_repo_instance.get_by_id = AsyncMock(return_value=None)

        # Act
        result = await use_case.execute(command)

        # Assert
        assert result.is_err()
        assert result.error.code == "NOT_FOUND"

        # Verify get_by_id was called with correct tenant_id
        mock_repo_instance.get_by_id.assert_called_once_with("project-789", "tenant-999")

        # Verify update was not called
        mock_repo_instance.update.assert_not_called()
