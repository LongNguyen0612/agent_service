"""add_dead_letter_event_table

Revision ID: dc10b0401537
Revises: 843526cf6716
Create Date: 2025-12-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'dc10b0401537'
down_revision: Union[str, Sequence[str], None] = '843526cf6716'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('dead_letter_events',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('pipeline_run_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('step_run_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('failure_reason', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('retry_count', sa.Integer(), nullable=False),
    sa.Column('context', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('resolved', sa.Boolean(), nullable=False, server_default='false'),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('resolution_notes', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.ForeignKeyConstraint(['pipeline_run_id'], ['pipeline_runs.id'], ),
    sa.ForeignKeyConstraint(['step_run_id'], ['pipeline_steps.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dead_letter_events_pipeline_run_id'), 'dead_letter_events', ['pipeline_run_id'], unique=False)
    op.create_index(op.f('ix_dead_letter_events_step_run_id'), 'dead_letter_events', ['step_run_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_dead_letter_events_step_run_id'), table_name='dead_letter_events')
    op.drop_index(op.f('ix_dead_letter_events_pipeline_run_id'), table_name='dead_letter_events')
    op.drop_table('dead_letter_events')
