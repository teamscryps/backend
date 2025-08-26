"""Add composite index on audit_logs (actor_user_id, action, created_at)

Revision ID: 20250826_03
Revises: 20250826_02
Create Date: 2025-08-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20250826_03'
down_revision = '20250826_02'
branch_labels = None
depends_on = None

INDEX_NAME = 'ix_audit_logs_actor_action_created'

def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {idx['name'] for idx in inspector.get_indexes('audit_logs')}
    if INDEX_NAME not in existing:
        op.create_index(INDEX_NAME, 'audit_logs', ['actor_user_id', 'action', 'created_at'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing = {idx['name'] for idx in inspector.get_indexes('audit_logs')}
    if INDEX_NAME in existing:
        op.drop_index(INDEX_NAME, table_name='audit_logs')
