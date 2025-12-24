import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from tests.fixtures.json_loader import TestDataLoader
from src.depends import get_unit_of_work
from src.adapter.services.unit_of_work import SqlAlchemyUnitOfWork
from src.app.services.audit_service import AuditService
from src.app.services.billing_client import BillingClient
from src.app.services.billing_dtos import BalanceResponse, CreditTransactionResponse
from src.app.services.git_service import IGitService, GitPushResult
from decimal import Decimal
from datetime import datetime
from typing import Dict, Any, Optional


@pytest_asyncio.fixture
def test_data():
    return TestDataLoader()


@pytest_asyncio.fixture
async def engine():
    # Use PostgreSQL for tests to support ARRAY types and match production
    engine = create_async_engine(
        "postgresql+asyncpg://postgres:postgres@localhost:5432/agent_service_test",
        echo=False
    )

    # Drop and recreate all tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session


class FakeBillingClient(BillingClient):
    """Fake billing client for integration tests - returns sufficient credits"""

    async def get_balance(self, tenant_id: str) -> BalanceResponse:
        """Return high balance for all tenants"""
        print(f"[FakeBillingClient] get_balance called for tenant: {tenant_id}")
        return BalanceResponse(
            tenant_id=tenant_id,
            balance=Decimal("10000.00"),
            last_updated=datetime.utcnow()
        )

    async def consume_credits(
        self,
        tenant_id: str,
        amount: Decimal,
        idempotency_key: str,
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CreditTransactionResponse:
        """Mock credit consumption - always succeeds"""
        print(f"[FakeBillingClient] consume_credits called for tenant: {tenant_id}, amount: {amount}")
        return CreditTransactionResponse(
            transaction_id="fake-transaction-123",
            tenant_id=tenant_id,
            amount=amount,
            new_balance=Decimal("10000.00"),
            timestamp=datetime.utcnow()
        )

    async def refund_credits(
        self,
        tenant_id: str,
        amount: Decimal,
        idempotency_key: str,
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CreditTransactionResponse:
        """Mock credit refund - always succeeds"""
        print(f"[FakeBillingClient] refund_credits called for tenant: {tenant_id}, amount: {amount}")
        return CreditTransactionResponse(
            transaction_id="fake-refund-123",
            tenant_id=tenant_id,
            amount=amount,
            new_balance=Decimal("10000.00"),
            timestamp=datetime.utcnow()
        )


@pytest_asyncio.fixture
async def client(engine):
    from src.api.app import create_app
    from config import ApplicationConfig
    from src.depends import get_audit_service, get_current_user, get_billing_client, get_session, get_git_service
    from unittest.mock import AsyncMock
    from httpx import ASGITransport

    app = create_app(ApplicationConfig)

    # Create a sessionmaker for the test
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Override to create a new session per request
    async def override_get_unit_of_work():
        async with Session() as session:
            yield SqlAlchemyUnitOfWork(session)

    async def override_get_session():
        async with Session() as session:
            yield session

    async def override_get_audit_service():
        return AsyncMock()

    async def override_get_current_user():
        return {"tenant_id": "test-tenant-id", "user_id": "test-user-id"}

    def override_get_billing_client():
        print("[CONFTEST] override_get_billing_client called - returning FakeBillingClient")
        return FakeBillingClient()

    def override_get_git_service():
        print("[CONFTEST] override_get_git_service called - returning FakeGitService")
        return FakeGitService()

    app.dependency_overrides[get_unit_of_work] = override_get_unit_of_work
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_audit_service] = override_get_audit_service
    app.dependency_overrides[get_current_user] = override_get_current_user
    app.dependency_overrides[get_billing_client] = override_get_billing_client
    app.dependency_overrides[get_git_service] = override_get_git_service

    print(f"[CONFTEST] Dependency overrides set: {list(app.dependency_overrides.keys())}")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class StubAuditService(AuditService):
    """Stub audit service for integration tests - does nothing"""

    async def log_event(
        self,
        event_type: str,
        tenant_id: str,
        user_id: str,
        resource_type: str,
        resource_id: str,
        metadata: Dict[str, Any] = None,
    ) -> None:
        """Do nothing - stub implementation"""
        pass


class FakeGitService(IGitService):
    """Fake Git service for integration tests - simulates successful Git operations"""

    async def push_content(
        self,
        repository_url: str,
        branch: str,
        file_path: str,
        content: str,
        commit_message: str,
    ) -> GitPushResult:
        """Simulate successful Git push"""
        print(f"[FakeGitService] push_content called for {repository_url}")
        return GitPushResult(
            success=True,
            commit_sha="fake-commit-sha-abc123",
            error_message=None
        )

    async def validate_repository(self, repository_url: str) -> bool:
        """Always return True for validation"""
        print(f"[FakeGitService] validate_repository called for {repository_url}")
        return True


@pytest_asyncio.fixture
def audit_service():
    """Provide a stub audit service for integration tests"""
    return StubAuditService()
