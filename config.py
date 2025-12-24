import os
import yaml

ROOT_PATH = os.path.dirname(__file__)
CONFIG_FILE_PATH = os.path.join(ROOT_PATH, "env.yaml")

if os.path.exists(CONFIG_FILE_PATH):
    with open(CONFIG_FILE_PATH, "r") as r_file:
        data = yaml.safe_load(r_file)
else:
    data = dict()


class ApplicationConfig:
    DB_URI = data.get("DB_URI", "postgresql+asyncpg://postgres:postgres@localhost:5434/agent_service")
    MIGRATION_DB_URI = data.get("MIGRATION_DB_URI", "postgresql://postgres:postgres@localhost:5434/agent_service")
    MONGODB_URI = data.get("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB_NAME = data.get("MONGODB_DB_NAME", "agent_service_audit")
    REDIS_URL = data.get("REDIS_URL", "redis://localhost:6379/0")
    API_PREFIX = data.get("API_PREFIX", "/api")
    API_PORT = data.get("API_PORT", 8000)
    API_HOST = data.get("API_HOST", "0.0.0.0")
    CORS_ORIGINS = data.get("CORS_ORIGINS", [])
    CORS_ALLOW_CREDENTIALS = data.get("CORS_ALLOW_CREDENTIALS", True)
    LOG_LEVEL = data.get("LOG_LEVEL", "INFO")
    AUTH_DISABLED = bool(data.get("AUTH_DISABLED", False))
    ENABLE_LOGGING_MIDDLEWARE = bool(data.get("ENABLE_LOGGING_MIDDLEWARE", 1))
    ENABLE_SENTRY = data.get("ENABLE_SENTRY", 0)
    DSN_SENTRY = data.get("DSN_SENTRY", "")
    SENTRY_ENVIRONMENT = data.get("SENTRY_ENVIRONMENT", "dev")
    CACHE_BACKEND = data.get("CACHE_BACKEND", "redis")
    JWT_SECRET = data.get("JWT_SECRET", "dev-secret-key-change-in-production")
    # Billing Service Integration - Story 2.2
    BILLING_SERVICE_URL = data.get("BILLING_SERVICE_URL", "http://localhost:8001")
    # File Storage - UC-30
    FILE_STORAGE_PATH = data.get("FILE_STORAGE_PATH", os.path.join(ROOT_PATH, "storage"))
    FILE_STORAGE_BASE_URL = data.get("FILE_STORAGE_BASE_URL", "http://localhost:8000/files")
    EXPORT_URL_EXPIRY_SECONDS = data.get("EXPORT_URL_EXPIRY_SECONDS", 3600)
