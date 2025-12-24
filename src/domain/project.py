from datetime import datetime
from typing import Optional
from sqlmodel import Field
from src.domain.base import BaseModel, generate_uuid
from src.domain.enums import ProjectStatus


class Project(BaseModel, table=True):
    __tablename__ = "projects"

    id: str = Field(default_factory=generate_uuid, primary_key=True)
    tenant_id: str = Field(index=True, nullable=False)
    name: str = Field(max_length=255, nullable=False)
    description: Optional[str] = Field(default=None)
    status: ProjectStatus = Field(default=ProjectStatus.active, nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    class Config:
        use_enum_values = True
