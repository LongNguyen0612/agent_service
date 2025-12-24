# Integration Test Guide - Agent Service

## Overview

This document describes the integration testing setup for the agent_service, including issues encountered, solutions implemented, and best practices for running tests.

## Critical Discovery: pytest-cov Compatibility Issue

### Problem
When running integration tests with coverage enabled (`pytest-cov`), SQLModel metadata incorrectly uses the SQLite compiler instead of PostgreSQL, causing errors:

```
sqlalchemy.exc.UnsupportedCompilationError: Compiler <sqlalchemy.dialects.sqlite.base.SQLiteTypeCompiler>
can't render element of type ARRAY
```

### Root Cause
The `pytest-cov` plugin interferes with module loading, causing SQLAlchemy to bind metadata to the wrong database dialect despite the engine being configured for PostgreSQL.

### Solution
**Run integration tests without coverage:**

```bash
# Single test
PYTHONPATH=/Users/frednguyen/Documents/super_agent uv run pytest tests/integration/api/test_pipeline_api.py -v --no-cov

# All integration tests
PYTHONPATH=/Users/frednguyen/Documents/super_agent uv run pytest tests/integration/ -v --no-cov
```

## Test Configuration

### PostgreSQL Test Database
Integration tests use a dedicated PostgreSQL database on port 5434:

```yaml
# From tests/integration/conftest.py
Database: postgresql+asyncpg://postgres:postgres@localhost:5434/agent_service_test
```

**Ensure PostgreSQL is running:**
```bash
docker ps | grep agent_postgres
# Should show: 0.0.0.0:5434->5432/tcp
```

### Test Fixtures

#### Engine Fixture
Located in `tests/integration/conftest.py:20-41`:
- Creates PostgreSQL async engine
- Drops and recreates schema for clean state per test
- Disposes engine after tests complete

#### Database Session Fixture
Located in `tests/integration/conftest.py:45-48`:
- Provides async session for database operations
- Scoped to function level (new session per test)

#### Client Fixture
Located in `tests/integration/conftest.py:109-111`:
- Creates FastAPI test client with ASGI transport
- Overrides dependencies (UoW, audit service, auth, billing client)
- Provides authenticated test context

#### FakeBillingClient
Located in `tests/integration/conftest.py:55-106`:
- Implements BillingClient interface for testing
- Returns sufficient credits (10000.00) for all tenants
- Avoids real HTTP calls to billing service

## Production Code Fixes

### 1. Pipeline Route - Billing Client Dependency Injection

**File**: `src/api/routes/pipeline.py`

**Changes Made**:
```python
# Added import
from src.depends import get_billing_client
from src.app.services.billing_client import BillingClient

# Updated endpoint signature (line 65-69)
async def validate_pipeline(
    task_id: str,
    current_user: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    billing_client: BillingClient = Depends(get_billing_client),  # NEW
):

# Use injected client (line 85-88)
use_case = ValidatePipeline(
    task_repository=task_repo,
    billing_client=billing_client,  # Use dependency instead of creating new instance
    cost_estimator=cost_estimator,
)
```

**Same changes applied to**:
- `run_pipeline` endpoint (lines 117-144)

### 2. Billing Client Dependency

**File**: `src/depends.py:43-45`

**Added**:
```python
def get_billing_client() -> HttpBillingClient:
    """Dependency for billing client with configured base URL"""
    return HttpBillingClient(base_url=ApplicationConfig.BILLING_SERVICE_URL)
```

### 3. Configuration

**File**: `env.yaml:20`

**Added**:
```yaml
BILLING_SERVICE_URL: "http://billing_api:8000"
```

**File**: `config.py`
- Already had `BILLING_SERVICE_URL` configuration support

## Running Integration Tests

### Prerequisites
1. PostgreSQL running on port 5434
2. Environment configured (env.yaml)
3. Dependencies installed (`uv sync`)

### Commands

**Run specific test file:**
```bash
cd agent_service
PYTHONPATH=/Users/frednguyen/Documents/super_agent uv run pytest tests/integration/api/test_pipeline_api.py -v --no-cov
```

**Run all integration tests:**
```bash
cd agent_service
PYTHONPATH=/Users/frednguyen/Documents/super_agent uv run pytest tests/integration/ -v --no-cov
```

**Run specific test:**
```bash
PYTHONPATH=/Users/frednguyen/Documents/super_agent uv run pytest \
  tests/integration/api/test_pipeline_api.py::test_validate_pipeline_eligible_with_sufficient_credits \
  -v --no-cov
```

### Common Issues

#### Issue: SQLite ARRAY type errors
**Symptom**: `UnsupportedCompilationError: can't render element of type ARRAY`
**Solution**: Add `--no-cov` flag to pytest command

#### Issue: PostgreSQL connection refused
**Symptom**: `Connection refused` or `nodename nor servname provided`
**Solution**:
```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Start if not running
docker-compose up -d agent_postgres
```

#### Issue: Test database not clean
**Symptom**: Foreign key violations or duplicate key errors
**Solution**: Engine fixture automatically drops/recreates schema. If issues persist:
```bash
# Manually clean test database
PGPASSWORD=postgres psql -h localhost -p 5434 -U postgres -d agent_service_test \
  -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"
```

## Test Structure

### Integration Test Organization

```
tests/integration/
├── conftest.py                    # Shared fixtures (engine, session, client, mocks)
├── api/
│   ├── test_pipeline_api.py      # Pipeline endpoint tests (Story 2.7)
│   └── ...
├── services/
│   └── ...
└── test_cancel_pipeline.py       # Use case integration tests
```

### Test Naming Conventions

```python
# Pattern: test_{endpoint/usecase}_{scenario}_{expected_result}
async def test_validate_pipeline_eligible_with_sufficient_credits(...)
async def test_validate_pipeline_not_eligible_with_insufficient_credits(...)
async def test_run_pipeline_fails_with_insufficient_credits(...)
```

## Known Limitations & Future Work

### 1. Dependency Override Not Working (ISSUE)

**Current Status**: UNRESOLVED

**Problem**: FastAPI dependency override for `get_billing_client` doesn't take effect at runtime, despite correct configuration.

**Evidence**:
- FakeBillingClient properly implements BillingClient interface ✓
- Dependency override registered before client creation ✓
- Route correctly injects billing_client parameter ✓
- Tests still make real HTTP calls ✗

**Workarounds Attempted**:
1. ❌ Mock patching with `unittest.mock.patch` - Failed (FastAPI test client isolation)
2. ❌ respx HTTP mocking - Failed (HttpBillingClient creates own AsyncClient)
3. ❌ Dependency override with FakeBillingClient - Failed (override not applied)

**Recommended Solutions**:
1. **Option A**: Start actual billing_service container for integration tests
   ```yaml
   # docker-compose.test.yml
   services:
     billing_api:
       build: ../billing_service
       ports: ["8001:8000"]
   ```

2. **Option B**: Split test levels:
   - **Unit tests**: Test use cases with mocked BillingClient
   - **Integration tests**: Test routes end-to-end with real service containers

3. **Option C**: Investigate FastAPI dependency resolution timing
   - May need to override dependency BEFORE app creation
   - Or use different approach for async dependencies

### 2. Test Coverage Reporting

**Issue**: Can't generate coverage for integration tests due to `--no-cov` requirement

**Solution**:
- Use unit tests for coverage metrics
- Keep integration tests for end-to-end validation
- Consider separating test commands in CI/CD:
  ```bash
  # Unit tests with coverage
  pytest tests/unit/ --cov=src --cov-report=xml

  # Integration tests without coverage
  pytest tests/integration/ --no-cov
  ```

## Best Practices

### 1. Test Isolation
- Each test gets fresh database schema (via engine fixture)
- Use unique IDs for test data to avoid conflicts
- Don't rely on test execution order

### 2. Async Test Writing
```python
@pytest.mark.asyncio
async def test_something(client: AsyncClient, db_session: AsyncSession):
    # Create test data using db_session
    task = Task(id="test-123", ...)
    db_session.add(task)
    await db_session.commit()

    # Make API call
    response = await client.post("/endpoint", json={...})

    # Assertions
    assert response.status_code == 200
```

### 3. Using Test Data
```python
# Good: Direct fixture usage
async def test_example(task: Task):
    assert task.id == "task-test-123"

# Good: Create in test when specific attributes needed
async def test_example(db_session: AsyncSession):
    custom_task = Task(id="custom-123", status=TaskStatus.running)
    db_session.add(custom_task)
    await db_session.commit()
```

### 4. Response Validation
```python
# Validate status code
assert response.status_code == 200

# Validate response structure
data = response.json()
assert data["eligible"] is True
assert float(data["estimated_cost"]) == 500.0
assert data["current_balance"] == "10000.00"  # From FakeBillingClient
```

## Debugging Tests

### Enable Verbose Logging
```bash
pytest tests/integration/api/test_pipeline_api.py -v -s --log-cli-level=DEBUG --no-cov
```

### Show Full Traceback
```bash
pytest tests/integration/api/test_pipeline_api.py -v --tb=long --no-cov
```

### Run Single Test with Print Statements
```bash
pytest tests/integration/api/test_pipeline_api.py::test_name -v -s --no-cov
```

### Check PostgreSQL Logs
```bash
docker logs agent_postgres --tail 50
```

### Inspect Database State
```bash
PGPASSWORD=postgres psql -h localhost -p 5434 -U postgres -d agent_service_test

# Inside psql:
\dt                           # List tables
SELECT * FROM tasks;          # Check test data
SELECT * FROM pipeline_runs;  # Check pipeline state
```

## CI/CD Configuration

### Recommended GitHub Actions Setup

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  integration-test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: agent_service_test
        ports:
          - 5434:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: uv sync
        working-directory: ./agent_service

      - name: Run integration tests
        run: |
          PYTHONPATH=$PWD uv run pytest tests/integration/ -v --no-cov
        working-directory: ./agent_service
```

## Related Documentation

- **Architecture**: See `/docs/architecture.md`
- **API Documentation**: See `/docs/api-specification.md`
- **Story 2.7**: Pipeline API endpoints - See `/_bmad-output/epics/story-2.7-pipeline-api-integration-tests.md`
- **Unit Tests**: See `/tests/unit/README.md`

## Changelog

### 2025-12-26
- **Fixed**: pytest-cov causing SQLite compiler errors
- **Fixed**: Pipeline routes missing dependency injection for billing client
- **Fixed**: ValidatePipeline constructor parameter mismatch
- **Added**: FakeBillingClient for integration tests
- **Added**: BILLING_SERVICE_URL configuration
- **Added**: `get_billing_client()` dependency in src/depends.py
- **Documented**: Integration test setup and known issues

## Contact

For questions or issues with integration tests:
- Review this guide first
- Check known limitations section
- Consult Story 2.7 acceptance criteria
- Review test implementation in `tests/integration/api/test_pipeline_api.py`
