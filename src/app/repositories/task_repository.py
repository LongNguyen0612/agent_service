from abc import ABC, abstractmethod
from typing import Optional, List
from src.domain import Task


class TaskRepository(ABC):
    """Repository interface for Task entity"""

    @abstractmethod
    async def create(self, task: Task) -> Task:
        """Create a new task"""
        pass

    @abstractmethod
    async def get_by_id(self, task_id: str, tenant_id: str) -> Optional[Task]:
        """Get task by ID with tenant isolation"""
        pass

    @abstractmethod
    async def find_by_project_id(
        self, project_id: str, tenant_id: str, status: Optional[str] = None
    ) -> List[Task]:
        """Find all tasks for a project with optional status filter"""
        pass

    @abstractmethod
    async def update(self, task: Task) -> Task:
        """Update an existing task"""
        pass
