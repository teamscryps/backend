"""Create portfolio_snapshots table

Revision ID: 20250826_01
Revises: d7e8f9a0b1c2
Create Date: 2025-08-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250826_01'
# IMPORTANT: This migration was initially chained to 'd7e8f9a0b1c2' directly,
# but after the merge migration 'eee6mergeheads' (which unified
# d7e8f9a0b1c2 + ddd1e2f3g4h5) it must depend on the merged head to avoid
# reintroducing a branch. Adjusted down_revision accordingly.
down_revision = 'eee6mergeheads'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'portfolio_snapshots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('cash_available', sa.Numeric(18,2), nullable=False, server_default='0'),
        sa.Column('cash_blocked', sa.Numeric(18,2), nullable=False, server_default='0'),
        sa.Column('realized_pnl', sa.Numeric(18,2), nullable=False, server_default='0'),
        sa.Column('unrealized_pnl', sa.Numeric(18,2), nullable=False, server_default='0'),
        sa.Column('holdings', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_snapshot_user_date', 'portfolio_snapshots', ['user_id', 'snapshot_date'])


def downgrade() -> None:
    op.drop_index('ix_snapshot_user_date', table_name='portfolio_snapshots')
    op.drop_table('portfolio_snapshots')
