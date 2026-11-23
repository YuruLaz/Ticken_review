"""add review_note to triage_runs

Revision ID: 3523f67653ba
Revises: e198b4552e34
Create Date: 2026-11-22 00:36:55.756784

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3523f67653ba'
down_revision: Union[str, Sequence[str], None] = 'e198b4552e34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('triage_runs', sa.Column('review_note', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('triage_runs', 'review_note')
