import pytest
from httpx import AsyncClient
from src.domain.enums import TaskStatus, ProjectStatus


@pytest.mark.asyncio
async def test_create_task_success(client: AsyncClient):
    """Test POST /projects/{id}/tasks endpoint creates a task successfully"""
    # Arrange - First create a project
    project_payload = {
        "name": "Test Project for Tasks",
        "description": "Test project",
        
        
    }
    project_response = await client.post("/projects", json=project_payload)
    assert project_response.status_code == 201
    project_id = project_response.json()["id"]

    # Act - Create a task
    task_payload = {
        "title": "Implement authentication",
        "input_spec": {"requirement": "Add JWT authentication", "priority": "high"},
        
        
    }
    response = await client.post(f"/projects/{project_id}/tasks", json=task_payload)

    # Assert
    assert response.status_code == 201

    data = response.json()
    assert data["title"] == "Implement authentication"
    assert data["project_id"] == project_id
    assert data["tenant_id"] == "test-tenant-id"
    assert data["status"] == TaskStatus.draft.value
    assert data["input_spec"] == {"requirement": "Add JWT authentication", "priority": "high"}
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_task_empty_title(client: AsyncClient):
    """Test POST /projects/{id}/tasks with empty title returns 400"""
    # Arrange - Create a project first
    project_payload = {
        "name": "Test Project",
        
        
    }
    project_response = await client.post("/projects", json=project_payload)
    project_id = project_response.json()["id"]

    # Act
    task_payload = {
        "title": "",
        "input_spec": {"requirement": "Test"},
        
        
    }
    response = await client.post(f"/projects/{project_id}/tasks", json=task_payload)

    # Assert
    assert response.status_code == 400

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_INPUT"
    assert "title cannot be empty" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_create_task_invalid_input_spec(client: AsyncClient):
    """Test POST /projects/{id}/tasks with invalid input_spec returns 400"""
    # Arrange - Create a project first
    project_payload = {
        "name": "Test Project",
        
        
    }
    project_response = await client.post("/projects", json=project_payload)
    project_id = project_response.json()["id"]

    # Act - Empty input_spec is invalid
    task_payload = {
        "title": "Test Task",
        "input_spec": {},
        
        
    }
    response = await client.post(f"/projects/{project_id}/tasks", json=task_payload)

    # Assert
    assert response.status_code == 400

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_INPUT_SPEC"


@pytest.mark.asyncio
async def test_create_task_project_not_found(client: AsyncClient):
    """Test POST /projects/{id}/tasks with non-existent project returns 404"""
    # Arrange
    task_payload = {
        "title": "Test Task",
        "input_spec": {"requirement": "Test"},
        
        
    }

    # Act
    response = await client.post("/projects/non-existent-project-id/tasks", json=task_payload)

    # Assert
    assert response.status_code == 404

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "PROJECT_NOT_FOUND"


@pytest.mark.asyncio
async def test_create_task_project_archived(client: AsyncClient):
    """Test POST /projects/{id}/tasks fails when project is archived"""
    # Arrange - Create a project and archive it
    project_payload = {
        "name": "Project to Archive",
        
        
    }
    project_response = await client.post("/projects", json=project_payload)
    project_id = project_response.json()["id"]

    # Archive the project
    update_payload = {
        "status": ProjectStatus.archived.value,
        
        
    }
    await client.put(f"/projects/{project_id}", json=update_payload)

    # Act - Try to create a task in archived project
    task_payload = {
        "title": "Test Task",
        "input_spec": {"requirement": "Test"},
        
        
    }
    response = await client.post(f"/projects/{project_id}/tasks", json=task_payload)

    # Assert
    assert response.status_code == 400

    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "PROJECT_NOT_ACTIVE"


@pytest.mark.asyncio
async def test_create_task_tenant_isolation(client: AsyncClient):
    """Test that tenant_id from request payload is ignored (comes from JWT only)"""
    # Arrange - Create a project
    project_payload = {
        "name": "Tenant A Project",


    }
    project_response = await client.post("/projects", json=project_payload)
    project_id = project_response.json()["id"]

    # Act - Try to send a different tenant_id in payload (should be ignored)
    task_payload = {
        "title": "Test Task",
        "input_spec": {"requirement": "Test"},
        # Note: tenant_id in payload is no longer accepted - comes from JWT only

    }
    response = await client.post(f"/projects/{project_id}/tasks", json=task_payload)

    # Assert - Task created successfully using tenant_id from JWT
    assert response.status_code == 201

    data = response.json()
    # Verify tenant_id comes from JWT, not from payload
    assert data["tenant_id"] == "test-tenant-id"
    assert data["title"] == "Test Task"


@pytest.mark.asyncio
async def test_create_task_complex_input_spec(client: AsyncClient):
    """Test POST /projects/{id}/tasks with complex input_spec"""
    # Arrange - Create a project
    project_payload = {
        "name": "Complex Spec Project",
        
        
    }
    project_response = await client.post("/projects", json=project_payload)
    project_id = project_response.json()["id"]

    # Act - Create task with complex nested input_spec
    task_payload = {
        "title": "Complex Task",
        "input_spec": {
            "requirement": "Build feature",
            "priority": "high",
            "acceptance_criteria": ["AC1", "AC2", "AC3"],
            "metadata": {"estimated_hours": 40, "assignee": "john@example.com"},
        },
        
        
    }
    response = await client.post(f"/projects/{project_id}/tasks", json=task_payload)

    # Assert
    assert response.status_code == 201

    data = response.json()
    assert data["input_spec"]["requirement"] == "Build feature"
    assert data["input_spec"]["acceptance_criteria"] == ["AC1", "AC2", "AC3"]
    assert data["input_spec"]["metadata"]["estimated_hours"] == 40


@pytest.mark.asyncio
async def test_list_project_tasks_success(client: AsyncClient):
    """Test GET /projects/{id}/tasks returns all tasks"""
    # Arrange - Create a project and multiple tasks
    project_payload = {
        "name": "List Tasks Project",
        
        
    }
    project_response = await client.post("/projects", json=project_payload)
    project_id = project_response.json()["id"]

    # Create 3 tasks
    for i in range(1, 4):
        task_payload = {
            "title": f"Task {i}",
            "input_spec": {"requirement": f"Requirement {i}"},
            
            
        }
        await client.post(f"/projects/{project_id}/tasks", json=task_payload)

    # Act
    response = await client.get(
        f"/projects/{project_id}/tasks",
        params={"tenant_id": "tenant-list-123"}
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert len(data["tasks"]) == 3

    # Verify tasks are ordered by created_at (newest first)
    # Since they were created in order 1, 2, 3, the response should be 3, 2, 1
    assert data["tasks"][0]["title"] == "Task 3"
    assert data["tasks"][1]["title"] == "Task 2"
    assert data["tasks"][2]["title"] == "Task 1"

    # Verify each task has required fields
    for task in data["tasks"]:
        assert "id" in task
        assert "title" in task
        assert "status" in task
        assert "created_at" in task
        assert task["status"] == TaskStatus.draft.value


@pytest.mark.asyncio
async def test_list_project_tasks_empty_project(client: AsyncClient):
    """Test GET /projects/{id}/tasks returns empty array for project with no tasks"""
    # Arrange - Create a project with no tasks
    project_payload = {
        "name": "Empty Project",
        
        
    }
    project_response = await client.post("/projects", json=project_payload)
    project_id = project_response.json()["id"]

    # Act
    response = await client.get(
        f"/projects/{project_id}/tasks",
        params={"tenant_id": "tenant-empty-list"}
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["tasks"] == []


@pytest.mark.asyncio
async def test_list_project_tasks_with_status_filter(client: AsyncClient):
    """Test GET /projects/{id}/tasks?status=completed filters by status"""
    # Arrange - Create project and tasks
    project_payload = {
        "name": "Filter Project",
        
        
    }
    project_response = await client.post("/projects", json=project_payload)
    project_id = project_response.json()["id"]

    # Create 3 tasks (all will be in draft status initially)
    task_ids = []
    for i in range(1, 4):
        task_payload = {
            "title": f"Task {i}",
            "input_spec": {"requirement": f"Test {i}"},
            
            
        }
        task_response = await client.post(f"/projects/{project_id}/tasks", json=task_payload)
        task_ids.append(task_response.json()["id"])

    # Act - Filter by draft status (all tasks should match)
    response = await client.get(
        f"/projects/{project_id}/tasks",
        params={"tenant_id": "tenant-filter", "status": TaskStatus.draft.value}
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 3
    
    # All should be draft status
    for task in data["tasks"]:
        assert task["status"] == TaskStatus.draft.value


@pytest.mark.asyncio
async def test_list_project_tasks_tenant_isolation(client: AsyncClient):
    """Test that tenant_id from query param is ignored (comes from JWT only)"""
    # Arrange - Create project with tasks
    project_payload = {
        "name": "Tenant A Project",


    }
    project_response = await client.post("/projects", json=project_payload)
    project_id = project_response.json()["id"]

    # Create tasks
    task_payload = {
        "title": "Tenant A Task",
        "input_spec": {"requirement": "Test"},


    }
    await client.post(f"/projects/{project_id}/tasks", json=task_payload)

    # Act - Try to pass tenant_id as query param (should be ignored)
    response = await client.get(
        f"/projects/{project_id}/tasks",
        params={"tenant_id": "tenant-b-list"}  # This is ignored - JWT is used instead
    )

    # Assert - Returns tasks using tenant_id from JWT (not from query param)
    assert response.status_code == 200
    data = response.json()
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["title"] == "Tenant A Task"


@pytest.mark.asyncio
async def test_list_project_tasks_nonexistent_project(client: AsyncClient):
    """Test GET /projects/{id}/tasks for non-existent project returns empty"""
    # Act
    response = await client.get("/projects/non-existent-project/tasks")

    # Assert - Returns empty array (not 404)
    assert response.status_code == 200
    data = response.json()
    assert data["tasks"] == []
