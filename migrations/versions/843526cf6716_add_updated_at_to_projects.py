"""add_updated_at_to_projects

Revision ID: 843526cf6716
Revises: d737e2bdb6ed
Create Date: 2025-12-25 08:11:26.495524

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '843526cf6716'
down_revision: Union[str, Sequence[str], None] = 'd737e2bdb6ed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add updated_at column to projects table
    # Set default to created_at for existing rows
    op.add_column('projects', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.execute('UPDATE projects SET updated_at = created_at WHERE updated_at IS NULL')
    op.alter_column('projects', 'updated_at', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove updated_at column
    op.drop_column('projects', 'updated_at')
