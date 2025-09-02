"""add_pan_and_status_to_users

Revision ID: ee7fc289cc37
Revises: 20250826_03
Create Date: 2025-08-31 12:02:29.944218

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee7fc289cc37'
down_revision: Union[str, Sequence[str], None] = '20250826_03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('pan', sa.String(), nullable=True))
    op.add_column('users', sa.Column('status', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'status')
    op.drop_column('users', 'pan')
