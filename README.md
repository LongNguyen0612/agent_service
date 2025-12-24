# Agent Service

AI Agent Platform - Project & Task Management Module

## Overview

This service manages projects, tasks, pipeline execution, and artifact versioning for the AI agent platform.

## Documentation

- User Stories: `/_bmad-output/agent-service-user-stories.md`
- Sprint Plan: `/_bmad-output/agent-service-sprint-plan.md`

## Quick Start

```bash
# Install dependencies
uv sync

# Run migrations
uv run alembic upgrade head

# Run service
uv run api.py

# Run tests
uv run pytest
```

## Architecture

- **Domain Layer**: `src/domain/` - Entity models (Project, Task, PipelineRun, PipelineStep, Artifact)
- **Application Layer**: `src/app/` - Use cases and repository interfaces
- **Adapter Layer**: `src/adapter/` - Database implementations
- **API Layer**: `src/api/` - FastAPI routes

## Database

- **PostgreSQL**: Transactional data (projects, tasks, pipelines, artifacts)
- **MongoDB**: Audit events (shared with IAM service)

## Environment

Copy `env.yaml.example` to `env.yaml` and configure:
- Database connection
- Redis connection
- API settings
