"""Dead Letter Event Repository Interface - Story 2.5

Interface for managing DeadLetterEvent entities (exhausted retry tracking).
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.dead_letter_event import DeadLetterEvent


class IDeadLetterEventRepository(ABC):
    """Interface for DeadLetterEvent repository - AC-2.5.3"""

    @abstractmethod
    async def create(self, dead_letter_event: DeadLetterEvent) -> DeadLetterEvent:
        """
        Create a new dead letter event record.

        Args:
            dead_letter_event: DeadLetterEvent entity to create

        Returns:
            DeadLetterEvent: Created dead letter event with generated ID
        """
        pass

    @abstractmethod
    async def get_by_id(self, event_id: str) -> Optional[DeadLetterEvent]:
        """
        Get dead letter event by ID.

        Args:
            event_id: ID of the dead letter event

        Returns:
            Optional[DeadLetterEvent]: Dead letter event if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_step_run_id(self, step_run_id: str) -> Optional[DeadLetterEvent]:
        """
        Get dead letter event for a specific step run.

        Args:
            step_run_id: ID of the pipeline step run

        Returns:
            Optional[DeadLetterEvent]: Dead letter event if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_pipeline_run_id(self, pipeline_run_id: str) -> List[DeadLetterEvent]:
        """
        Get all dead letter events for a pipeline run.

        Args:
            pipeline_run_id: ID of the pipeline run

        Returns:
            List[DeadLetterEvent]: List of dead letter events
        """
        pass

    @abstractmethod
    async def get_unresolved(self) -> List[DeadLetterEvent]:
        """
        Get all unresolved dead letter events.

        Returns:
            List[DeadLetterEvent]: List of unresolved dead letter events
        """
        pass
