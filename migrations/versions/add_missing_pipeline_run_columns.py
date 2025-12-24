"""Add missing columns to pipeline_runs table

Revision ID: add_missing_cols
Revises: dc10b0401537
Create Date: 2026-01-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_missing_cols'
down_revision: Union[str, Sequence[str], None] = 'dc10b0401537'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing columns to pipeline_runs table."""
    # Add pause_reasons as JSONB with default empty array
    op.add_column(
        'pipeline_runs',
        sa.Column('pause_reasons', postgresql.JSONB, server_default='[]', nullable=False)
    )

    # Add current_step with default 1
    op.add_column(
        'pipeline_runs',
        sa.Column('current_step', sa.Integer(), server_default='1', nullable=False)
    )

    # Add created_at timestamp
    op.add_column(
        'pipeline_runs',
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
    )

    # Add updated_at timestamp
    op.add_column(
        'pipeline_runs',
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False)
    )

    # Add paused_at timestamp (nullable)
    op.add_column(
        'pipeline_runs',
        sa.Column('paused_at', sa.DateTime(), nullable=True)
    )

    # Add pause_expires_at timestamp (nullable)
    op.add_column(
        'pipeline_runs',
        sa.Column('pause_expires_at', sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    """Remove added columns from pipeline_runs table."""
    op.drop_column('pipeline_runs', 'pause_expires_at')
    op.drop_column('pipeline_runs', 'paused_at')
    op.drop_column('pipeline_runs', 'updated_at')
    op.drop_column('pipeline_runs', 'created_at')
    op.drop_column('pipeline_runs', 'current_step')
    op.drop_column('pipeline_runs', 'pause_reasons')
