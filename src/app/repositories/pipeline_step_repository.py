from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.pipeline_step import PipelineStepRun


class IPipelineStepRunRepository(ABC):
    """Interface for PipelineStepRun repository - Story 2.4"""

    @abstractmethod
    async def create(self, pipeline_step: PipelineStepRun) -> PipelineStepRun:
        """Create a new pipeline step run"""
        pass

    @abstractmethod
    async def get_by_id(self, step_id: str) -> Optional[PipelineStepRun]:
        """Get pipeline step run by ID"""
        pass

    @abstractmethod
    async def get_by_pipeline_run_id(self, pipeline_run_id: str) -> List[PipelineStepRun]:
        """Get all step runs for a pipeline run, ordered by step_number"""
        pass

    @abstractmethod
    async def update(self, pipeline_step: PipelineStepRun) -> PipelineStepRun:
        """Update an existing pipeline step run"""
        pass
