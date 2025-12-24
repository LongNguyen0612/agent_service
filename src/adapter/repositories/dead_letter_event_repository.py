"""Dead Letter Event Repository Implementation - Story 2.5

SQLAlchemy implementation for managing DeadLetterEvent entities.
"""
from typing import List, Optional
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select
from src.app.repositories.dead_letter_event_repository import IDeadLetterEventRepository
from src.domain.dead_letter_event import DeadLetterEvent


class DeadLetterEventRepository(IDeadLetterEventRepository):
    """SQLAlchemy implementation of Dead Letter Event repository - Story 2.5, AC-2.5.3"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, dead_letter_event: DeadLetterEvent) -> DeadLetterEvent:
        """
        Create a new dead letter event record.

        Args:
            dead_letter_event: DeadLetterEvent entity to create

        Returns:
            DeadLetterEvent: Created dead letter event with generated ID
        """
        self.session.add(dead_letter_event)
        await self.session.flush()
        await self.session.refresh(dead_letter_event)
        return dead_letter_event

    async def get_by_id(self, event_id: str) -> Optional[DeadLetterEvent]:
        """
        Get dead letter event by ID.

        Args:
            event_id: ID of the dead letter event

        Returns:
            Optional[DeadLetterEvent]: Dead letter event if found, None otherwise
        """
        stmt = select(DeadLetterEvent).where(DeadLetterEvent.id == event_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_step_run_id(self, step_run_id: str) -> Optional[DeadLetterEvent]:
        """
        Get dead letter event for a specific step run.

        Args:
            step_run_id: ID of the pipeline step run

        Returns:
            Optional[DeadLetterEvent]: Dead letter event if found, None otherwise
        """
        stmt = select(DeadLetterEvent).where(DeadLetterEvent.step_run_id == step_run_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_pipeline_run_id(self, pipeline_run_id: str) -> List[DeadLetterEvent]:
        """
        Get all dead letter events for a pipeline run.

        Args:
            pipeline_run_id: ID of the pipeline run

        Returns:
            List[DeadLetterEvent]: List of dead letter events
        """
        stmt = (
            select(DeadLetterEvent)
            .where(DeadLetterEvent.pipeline_run_id == pipeline_run_id)
            .order_by(DeadLetterEvent.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_unresolved(self) -> List[DeadLetterEvent]:
        """
        Get all unresolved dead letter events.

        Returns:
            List[DeadLetterEvent]: List of unresolved dead letter events
        """
        stmt = (
            select(DeadLetterEvent)
            .where(DeadLetterEvent.resolved == False)
            .order_by(DeadLetterEvent.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
