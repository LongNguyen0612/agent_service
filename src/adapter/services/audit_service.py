from typing import Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from src.app.services.audit_service import AuditService


class MongoAuditService(AuditService):
    """MongoDB implementation of AuditService"""

    def __init__(self, mongo_client: AsyncIOMotorClient, db_name: str):
        self.client = mongo_client
        self.db = self.client[db_name]
        self.collection = self.db["audit_events"]

    async def log_event(
        self,
        event_type: str,
        tenant_id: str,
        user_id: str,
        resource_type: str,
        resource_id: str,
        metadata: Dict[str, Any] = None,
    ) -> None:
        """Log an audit event to MongoDB"""
        event = {
            "event_type": event_type,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow(),
        }
        await self.collection.insert_one(event)
