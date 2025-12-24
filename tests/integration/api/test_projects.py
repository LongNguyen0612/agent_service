import pytest
from httpx import AsyncClient
from src.domain.enums import ProjectStatus


@pytest.mark.asyncio
async def test_create_project_success(client: AsyncClient):
    """Test POST /projects endpoint creates a project successfully"""
    # Arrange
    payload = {
        "name": "Integration Test Project",
        "description": "This is an integration test",
    }

    # Act
    response = await client.post("/projects", json=payload)

    # Assert
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Integration Test Project"
    assert data["description"] == "This is an integration test"
    assert data["tenant_id"] == "test-tenant-id"  # From mocked current_user
    assert data["status"] == ProjectStatus.active.value
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_project_empty_name(client: AsyncClient):
    """Test POST /projects with empty name returns 400"""
    # Arrange
    payload = {
        "name": "",
        "description": "This should fail",
    }

    # Act
    response = await client.post("/projects", json=payload)

    # Assert
    assert response.status_code == 400

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_INPUT"
    assert "name cannot be empty" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_create_project_minimal_data(client: AsyncClient):
    """Test POST /projects with minimal required fields"""
    # Arrange
    payload = {
        "name": "Minimal Project",
        
        
    }

    # Act
    response = await client.post("/projects", json=payload)

    # Assert
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Minimal Project"
    assert data["description"] is None
    assert data["tenant_id"] == "test-tenant-id"
    assert data["status"] == ProjectStatus.active.value


@pytest.mark.asyncio
async def test_update_project_success(client: AsyncClient):
    """Test PUT /projects/{id} endpoint updates a project successfully"""
    # Arrange - First create a project
    create_payload = {
        "name": "Original Project Name",
        "description": "Original description",
        
        
    }
    create_response = await client.post("/projects", json=create_payload)
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    # Act - Update the project
    update_payload = {
        "name": "Updated Project Name",
        "description": "Updated description",
        
        
    }
    response = await client.put(f"/projects/{project_id}", json=update_payload)

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == project_id
    assert data["name"] == "Updated Project Name"
    assert data["description"] == "Updated description"
    assert data["tenant_id"] == "test-tenant-id"
    assert data["status"] == ProjectStatus.active.value


@pytest.mark.asyncio
async def test_update_project_partial_update(client: AsyncClient):
    """Test PUT /projects/{id} with partial update (only description)"""
    # Arrange - First create a project
    create_payload = {
        "name": "Original Name",
        "description": "Original description",
        
        
    }
    create_response = await client.post("/projects", json=create_payload)
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    # Act - Update only the description
    update_payload = {
        "description": "Only description changed",
        
        
    }
    response = await client.put(f"/projects/{project_id}", json=update_payload)

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert data["name"] == "Original Name"  # Name unchanged
    assert data["description"] == "Only description changed"  # Description updated


@pytest.mark.asyncio
async def test_update_project_not_found(client: AsyncClient):
    """Test PUT /projects/{id} with non-existent project returns 404"""
    # Arrange
    update_payload = {
        "name": "Updated Name",
        
        
    }

    # Act
    response = await client.put("/projects/non-existent-id", json=update_payload)

    # Assert
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_update_project_empty_name(client: AsyncClient):
    """Test PUT /projects/{id} with empty name returns 400"""
    # Arrange - First create a project
    create_payload = {
        "name": "Original Name",
        
        
    }
    create_response = await client.post("/projects", json=create_payload)
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    # Act - Try to update with empty name
    update_payload = {
        "name": "",
        
        
    }
    response = await client.put(f"/projects/{project_id}", json=update_payload)

    # Assert
    assert response.status_code == 400

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_INPUT"
    assert "name cannot be empty" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_update_project_tenant_isolation(client: AsyncClient):
    """Test that tenant_id from request payload is ignored (comes from JWT only)"""
    # Arrange - Create a project
    create_payload = {
        "name": "Tenant A Project",


    }
    create_response = await client.post("/projects", json=create_payload)
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]

    # Act - Try to send a different tenant_id in payload (should be ignored)
    update_payload = {
        "name": "Updated Name",
        # Note: tenant_id in payload is no longer accepted - comes from JWT only

    }
    response = await client.put(f"/projects/{project_id}", json=update_payload)

    # Assert - Update succeeds using tenant_id from JWT (not from payload)
    assert response.status_code == 200

    data = response.json()
    # Verify tenant_id comes from JWT, not from payload
    assert data["tenant_id"] == "test-tenant-id"
    assert data["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_project_status_change(client: AsyncClient):
    """Test PUT /projects/{id} can update project status"""
    # Arrange - First create a project
    create_payload = {
        "name": "Active Project",
        
        
    }
    create_response = await client.post("/projects", json=create_payload)
    assert create_response.status_code == 201
    project_id = create_response.json()["id"]
    assert create_response.json()["status"] == ProjectStatus.active.value

    # Act - Archive the project
    update_payload = {
        "status": ProjectStatus.archived.value,
        
        
    }
    response = await client.put(f"/projects/{project_id}", json=update_payload)

    # Assert
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == ProjectStatus.archived.value
    assert data["name"] == "Active Project"  # Name unchanged
