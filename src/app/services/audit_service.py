from abc import ABC, abstractmethod
from typing import Dict, Any
from datetime import datetime


class AuditService(ABC):
    """Service interface for audit event logging"""

    @abstractmethod
    async def log_event(
        self,
        event_type: str,
        tenant_id: str,
        user_id: str,
        resource_type: str,
        resource_id: str,
        metadata: Dict[str, Any] = None,
    ) -> None:
        """
        Log an audit event

        Args:
            event_type: Type of event (e.g. "project_created", "task_updated")
            tenant_id: Tenant identifier
            user_id: User who triggered the event
            resource_type: Type of resource (e.g. "project", "task")
            resource_id: ID of the affected resource
            metadata: Additional event metadata
        """
        pass
