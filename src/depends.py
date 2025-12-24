from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from motor.motor_asyncio import AsyncIOMotorClient
from config import ApplicationConfig
from src.adapter.services.unit_of_work import SqlAlchemyUnitOfWork
from src.adapter.services.audit_service import MongoAuditService
from src.adapter.services.http_billing_client import HttpBillingClient
from src.adapter.services.local_file_storage import LocalFileStorage
from src.adapter.services.git_service import GitService, MockGitService
from src.app.services.input_spec_validator import InputSpecValidator
from src.app.services.file_storage import FileStorage
from src.app.services.git_service import IGitService
from src.api.utils.jwt import verify_jwt

# PostgreSQL engine
engine = create_async_engine(ApplicationConfig.DB_URI, echo=False, future=True)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)

# MongoDB client
mongo_client = AsyncIOMotorClient(ApplicationConfig.MONGODB_URI)


async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def get_unit_of_work():
    async with AsyncSessionLocal() as session:
        yield SqlAlchemyUnitOfWork(session)


async def get_audit_service() -> MongoAuditService:
    return MongoAuditService(mongo_client, ApplicationConfig.MONGODB_DB_NAME)


def get_input_spec_validator() -> InputSpecValidator:
    return InputSpecValidator()


def get_billing_client() -> HttpBillingClient:
    """Dependency for billing client with configured base URL"""
    return HttpBillingClient(base_url=ApplicationConfig.BILLING_SERVICE_URL)


def get_file_storage() -> FileStorage:
    """Dependency for file storage - UC-30"""
    return LocalFileStorage(
        base_path=ApplicationConfig.FILE_STORAGE_PATH,
        base_url=ApplicationConfig.FILE_STORAGE_BASE_URL
    )


def get_git_service() -> IGitService:
    """Dependency for Git service - UC-31"""
    git_credentials = getattr(ApplicationConfig, "GIT_CREDENTIALS", None)
    use_mock = getattr(ApplicationConfig, "USE_MOCK_GIT_SERVICE", False)

    if use_mock:
        return MockGitService()
    return GitService(git_credentials=git_credentials)


# Security
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Dependency to extract and validate JWT token from Authorization header

    Returns:
        dict: Decoded JWT payload with user_id, tenant_id, role

    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"get_current_user called - AUTH_DISABLED: {ApplicationConfig.AUTH_DISABLED}")
    logger.info(f"Credentials received: {credentials is not None}")

    if ApplicationConfig.AUTH_DISABLED:
        # For testing/development - return mock user
        return {
            "user_id": "test-user-id",
            "tenant_id": "test-tenant-id",
            "role": "owner",
        }

    if credentials is None:
        logger.error("No credentials provided - HTTPBearer failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    logger.info(f"Token extracted: {token[:30] if token else 'NONE'}...")

    payload = verify_jwt(token)

    if payload is None:
        logger.error("verify_jwt returned None - raising 401")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.info(f"Auth successful for user: {payload.get('user_id')}")
    return payload
