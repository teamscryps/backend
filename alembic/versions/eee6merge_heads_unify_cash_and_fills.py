"""merge heads for cash columns and fill processing

Revision ID: eee6mergeheads
Revises: d7e8f9a0b1c2, ddd1e2f3g4h5
Create Date: 2025-08-26
"""
from typing import Sequence, Union
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'eee6mergeheads'
down_revision: Union[str, Sequence[str], None] = ('d7e8f9a0b1c2','ddd1e2f3g4h5')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # No-op merge
    pass

def downgrade() -> None:
    # Can't un-merge cleanly
    pass
