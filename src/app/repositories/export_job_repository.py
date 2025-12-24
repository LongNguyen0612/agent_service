from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.export_job import ExportJob


class IExportJobRepository(ABC):
    """Interface for ExportJob repository - UC-30"""

    @abstractmethod
    async def create(self, export_job: ExportJob) -> ExportJob:
        """Create a new export job"""
        pass

    @abstractmethod
    async def get_by_id(self, job_id: str, tenant_id: str = None) -> Optional[ExportJob]:
        """Get export job by ID, optionally filtered by tenant for security"""
        pass

    @abstractmethod
    async def get_by_project(self, project_id: str, tenant_id: str) -> List[ExportJob]:
        """Get all export jobs for a project"""
        pass

    @abstractmethod
    async def update(self, export_job: ExportJob) -> ExportJob:
        """Update an existing export job"""
        pass

    @abstractmethod
    async def get_pending_jobs(self, limit: int = 10) -> List[ExportJob]:
        """Get pending export jobs for processing"""
        pass
