"""add_order_execution_type_to_trades

Revision ID: a1d6090050c2
Revises: ee7fc289cc37
Create Date: 2025-09-08 15:58:41.901019

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1d6090050c2'
down_revision: Union[str, Sequence[str], None] = 'ee7fc289cc37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('trades', sa.Column('order_execution_type', sa.String(), nullable=False, server_default='MARKET'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('trades', 'order_execution_type')
