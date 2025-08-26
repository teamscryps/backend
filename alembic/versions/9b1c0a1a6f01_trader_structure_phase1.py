"""trader structure phase1

Revision ID: 9b1c0a1a6f01
Revises: 6233d1524e9b
Create Date: 2025-08-26 00:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '9b1c0a1a6f01'
down_revision: Union[str, Sequence[str], None] = '6233d1524e9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)

    # 1. Extend users table conditionally
    user_columns = {c['name'] for c in inspector.get_columns('users')}
    with op.batch_alter_table('users') as batch_op:
        if 'role' not in user_columns:
            batch_op.add_column(sa.Column('role', sa.String(length=10), nullable=True, server_default='client'))
        if 'available_funds' not in user_columns:
            batch_op.add_column(sa.Column('available_funds', sa.Integer(), nullable=True))

    # 2. trader_clients table (skip if exists)
    if 'trader_clients' not in inspector.get_table_names():
        op.create_table(
            'trader_clients',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('trader_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('client_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('trader_id', 'client_id', name='uq_trader_client_pair')
        )

    # 3. holdings table
    if 'holdings' not in inspector.get_table_names():
        op.create_table(
            'holdings',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('symbol', sa.String(), nullable=False),
            sa.Column('quantity', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('avg_price', sa.Float(), nullable=False, server_default='0'),
            sa.Column('last_updated', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint('user_id', 'symbol', name='uq_user_symbol')
        )

    # 4. audit_logs table
    if 'audit_logs' not in inspector.get_table_names():
        op.create_table(
            'audit_logs',
            sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
            sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('target_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('action', sa.String(length=50), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now())
        )

    # 5. Add trader_id to trades
    trade_columns = {c['name'] for c in inspector.get_columns('trades')}
    if 'trader_id' not in trade_columns:
        with op.batch_alter_table('trades') as batch_op:
            batch_op.add_column(sa.Column('trader_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))

    # 6. Backfill available_funds = capital (safe re-run)
    op.execute("UPDATE users SET available_funds = capital WHERE available_funds IS NULL;")


def downgrade() -> None:
    with op.batch_alter_table('trades') as batch_op:
        batch_op.drop_column('trader_id')

    op.drop_table('audit_logs')
    op.drop_table('holdings')
    op.drop_table('trader_clients')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('available_funds')
        batch_op.drop_column('role')
