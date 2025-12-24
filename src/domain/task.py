from datetime import datetime
from typing import Optional, Dict, Any
from sqlmodel import Field, Column, JSON
from sqlalchemy import JSON as SQLJSON
from src.domain.base import BaseModel, generate_uuid
from src.domain.enums import TaskStatus


class Task(BaseModel, table=True):
    __tablename__ = "tasks"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    project_id: str = Field(foreign_key="projects.id", index=True, nullable=False)
    tenant_id: str = Field(index=True, nullable=False)
    title: str = Field(max_length=500, nullable=False)
    input_spec: Dict[str, Any] = Field(sa_column=Column(SQLJSON, nullable=False))
    status: TaskStatus = Field(default=TaskStatus.draft, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: Optional[datetime] = Field(default=None)

    class Config:
        use_enum_values = True

    def transition_to_queued(self) -> None:
        """Transition task from draft to queued status"""
        if self.status == TaskStatus.draft:
            self.status = TaskStatus.queued
            self.updated_at = datetime.utcnow()

    def transition_to_running(self) -> None:
        """Transition task to running status"""
        if self.status == TaskStatus.queued:
            self.status = TaskStatus.running
            self.updated_at = datetime.utcnow()

    def transition_to_completed(self) -> None:
        """Transition task to completed status"""
        if self.status == TaskStatus.running:
            self.status = TaskStatus.completed
            self.updated_at = datetime.utcnow()

    def transition_to_failed(self) -> None:
        """Transition task to failed status"""
        if self.status in [TaskStatus.queued, TaskStatus.running]:
            self.status = TaskStatus.failed
            self.updated_at = datetime.utcnow()
