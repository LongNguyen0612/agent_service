from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.pipeline_run import PipelineRun


class IPipelineRunRepository(ABC):
    """Interface for PipelineRun repository"""

    @abstractmethod
    async def create(self, pipeline_run: PipelineRun) -> PipelineRun:
        """Create a new pipeline run"""
        pass

    @abstractmethod
    async def get_by_id(self, pipeline_run_id: str) -> Optional[PipelineRun]:
        """Get pipeline run by ID"""
        pass

    @abstractmethod
    async def get_by_task_id(self, task_id: str) -> Optional[PipelineRun]:
        """Get the most recent pipeline run for a task"""
        pass

    @abstractmethod
    async def get_all_by_task_id(self, task_id: str) -> List[PipelineRun]:
        """Get all pipeline runs for a task, ordered by created_at desc"""
        pass

    @abstractmethod
    async def update(self, pipeline_run: PipelineRun) -> PipelineRun:
        """Update an existing pipeline run"""
        pass
