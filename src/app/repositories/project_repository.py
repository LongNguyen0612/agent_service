from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain import Project


class ProjectRepository(ABC):
    """Repository interface for Project entity"""

    @abstractmethod
    async def create(self, project: Project) -> Project:
        """Create a new project"""
        pass

    @abstractmethod
    async def get_by_id(self, project_id: str, tenant_id: str = None) -> Optional[Project]:
        """Get project by ID, optionally filtered by tenant for security"""
        pass

    @abstractmethod
    async def get_by_tenant_id(self, tenant_id: str) -> List[Project]:
        """Get all projects for a tenant"""
        pass

    @abstractmethod
    async def update(self, project: Project) -> Project:
        """Update an existing project"""
        pass
