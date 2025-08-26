"""order lifecycle + blocked funds

Revision ID: c1a2b3c4d5e6
Revises: b2f7d8e9c123
Create Date: 2025-08-26

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = 'c1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'b2f7d8e9c123'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # Users table: add cash_available, cash_blocked if not exist
    user_columns = {c['name'] for c in inspector.get_columns('users')}
    with op.batch_alter_table('users') as batch_op:
        if 'cash_available' not in user_columns:
            batch_op.add_column(sa.Column('cash_available', sa.Numeric(18,2), nullable=True))
        if 'cash_blocked' not in user_columns:
            batch_op.add_column(sa.Column('cash_blocked', sa.Numeric(18,2), nullable=False, server_default='0'))

    # Backfill cash_available from available_funds or capital
    if 'cash_available' not in user_columns:
        op.execute("UPDATE users SET cash_available = COALESCE(available_funds, capital)")
    # Ensure blocked default to 0
    op.execute("UPDATE users SET cash_blocked = 0 WHERE cash_blocked IS NULL")

    # Orders table modifications
    order_columns = {c['name'] for c in inspector.get_columns('orders')}
    with op.batch_alter_table('orders') as batch_op:
        if 'status' not in order_columns:
            batch_op.add_column(sa.Column('status', sa.String(length=30), nullable=True))
        if 'broker_order_id' not in order_columns:
            batch_op.add_column(sa.Column('broker_order_id', sa.String(length=100), nullable=True))
        if 'filled_qty' not in order_columns:
            batch_op.add_column(sa.Column('filled_qty', sa.Integer(), nullable=False, server_default='0'))
        if 'avg_fill_price' not in order_columns:
            batch_op.add_column(sa.Column('avg_fill_price', sa.Numeric(18,4), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('orders') as batch_op:
        batch_op.drop_column('avg_fill_price')
        batch_op.drop_column('filled_qty')
        batch_op.drop_column('broker_order_id')
        batch_op.drop_column('status')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('cash_blocked')
        batch_op.drop_column('cash_available')
