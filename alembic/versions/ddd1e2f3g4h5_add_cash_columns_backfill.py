"""Add cash_available & cash_blocked columns if missing and backfill

Revision ID: ddd1e2f3g4h5
Revises: c1a2b3c4d5e6
Create Date: 2025-08-26
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = 'ddd1e2f3g4h5'
down_revision: Union[str, Sequence[str], None] = 'c1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    user_columns = {c['name'] for c in inspector.get_columns('users')}
    # Only add if truly absent (production DB that missed earlier migration)
    with op.batch_alter_table('users') as batch_op:
        if 'cash_available' not in user_columns:
            batch_op.add_column(sa.Column('cash_available', sa.Numeric(18,2), nullable=True))
        if 'cash_blocked' not in user_columns:
            batch_op.add_column(sa.Column('cash_blocked', sa.Numeric(18,2), nullable=False, server_default='0'))
    # Backfill newly added columns
    if 'cash_available' not in user_columns:
        op.execute("UPDATE users SET cash_available = COALESCE(available_funds, capital)")
    if 'cash_blocked' not in user_columns:
        op.execute("UPDATE users SET cash_blocked = 0 WHERE cash_blocked IS NULL")


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        # Only drop if present (safety)
        batch_op.drop_column('cash_blocked')
        batch_op.drop_column('cash_available')
