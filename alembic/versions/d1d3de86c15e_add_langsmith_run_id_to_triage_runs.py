"""add langsmith_run_id to triage_runs

Revision ID: d1d3de86c15e
Revises: 7df1a86865e5
Create Date: 2026-11-22 02:16:28.540842

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1d3de86c15e'
down_revision: Union[str, Sequence[str], None] = '7df1a86865e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('triage_runs', sa.Column('langsmith_run_id', sa.Uuid(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('triage_runs', 'langsmith_run_id')
