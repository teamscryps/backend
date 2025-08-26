"""Add indexes for trades user_id and trader_id; backfill trader_id NULL

Revision ID: b2f7d8e9c123
Revises: 9b1c0a1a6f01
Create Date: 2025-08-26 00:15:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b2f7d8e9c123'
down_revision: Union[str, Sequence[str], None] = '9b1c0a1a6f01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create indexes if they do not already exist
    conn = op.get_bind()
    existing_indexes = {row[0] for row in conn.execute(sa.text("SELECT indexname FROM pg_indexes WHERE tablename='trades'"))}

    if 'ix_trades_user_id' not in existing_indexes:
        op.create_index('ix_trades_user_id', 'trades', ['user_id'])
    if 'ix_trades_trader_id' not in existing_indexes:
        op.create_index('ix_trades_trader_id', 'trades', ['trader_id'])

    # Backfill trader_id to NULL explicitly (no-op if already NULL)
    conn.execute(sa.text("UPDATE trades SET trader_id = NULL WHERE trader_id IS NOT NULL AND trader_id = 0"))


def downgrade() -> None:
    # Drop indexes if they exist
    conn = op.get_bind()
    existing_indexes = {row[0] for row in conn.execute(sa.text("SELECT indexname FROM pg_indexes WHERE tablename='trades'"))}
    if 'ix_trades_trader_id' in existing_indexes:
        op.drop_index('ix_trades_trader_id', table_name='trades')
    if 'ix_trades_user_id' in existing_indexes:
        op.drop_index('ix_trades_user_id', table_name='trades')
