"""fill processing structures

Revision ID: d7e8f9a0b1c2
Revises: c1a2b3c4d5e6
Create Date: 2025-08-26

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, Sequence[str], None] = 'c1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # holdings reserved_qty
    holding_cols = {c['name'] for c in inspector.get_columns('holdings')} if 'holdings' in inspector.get_table_names() else set()
    if 'holdings' in inspector.get_table_names() and 'reserved_qty' not in holding_cols:
        with op.batch_alter_table('holdings') as batch_op:
            batch_op.add_column(sa.Column('reserved_qty', sa.Integer(), nullable=False, server_default='0'))

    # order_fills table
    if 'order_fills' not in inspector.get_table_names():
        op.create_table(
            'order_fills',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id', ondelete='CASCADE'), nullable=False, index=True),
            sa.Column('broker_fill_id', sa.String(length=100), nullable=True),
            sa.Column('quantity', sa.Integer(), nullable=False),
            sa.Column('price', sa.Numeric(18,4), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
        )
        op.create_index('ix_order_fills_order_id', 'order_fills', ['order_id'])
        # broker_fill_id uniqueness per order when provided
        op.create_unique_constraint('uq_order_fill_broker_id', 'order_fills', ['order_id', 'broker_fill_id'])


def downgrade() -> None:
    if op.get_bind().dialect.name != 'sqlite':
        op.drop_constraint('uq_order_fill_broker_id', 'order_fills', type_='unique')
    op.drop_index('ix_order_fills_order_id', table_name='order_fills')
    op.drop_table('order_fills')
    with op.batch_alter_table('holdings') as batch_op:
        batch_op.drop_column('reserved_qty')
