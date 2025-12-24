"""Diagnostic script to test engine creation and SQLModel"""
import asyncio
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

# Import all domain models so they're registered with SQLModel.metadata
from src.domain.project import Project
from src.domain.task import Task
from src.domain.pipeline_run import PipelineRun
from src.domain.pipeline_step import PipelineStepRun
from src.domain.agent_run import AgentRun
from src.domain.artifact import Artifact


async def main():
    # Test engine creation
    engine = create_async_engine(
        "postgresql+asyncpg://postgres:postgres@localhost:5434/agent_service_test",
        echo=True
    )

    print(f"Engine dialect: {engine.dialect.name}")
    print(f"Engine driver: {engine.dialect.driver}")
    print(f"Engine URL: {engine.url}")

    # Try to connect
    async with engine.begin() as conn:
        result = await conn.execute(sqlalchemy.text("SELECT 1"))
        print(f"Connection successful! Result: {result.scalar()}")

        # Test metadata create_all like in conftest
        print("\nAttempting to create tables...")
        await conn.run_sync(SQLModel.metadata.create_all)
        print("Tables created successfully!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
