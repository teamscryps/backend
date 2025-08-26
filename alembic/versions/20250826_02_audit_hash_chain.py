"""Add hash chaining columns to audit_logs

Revision ID: 20250826_02
Revises: 20250826_01
Create Date: 2025-08-26
"""
from alembic import op
import sqlalchemy as sa

revision = '20250826_02'
down_revision = '20250826_01'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('audit_logs', sa.Column('prev_hash', sa.String(length=128), nullable=True))
    op.add_column('audit_logs', sa.Column('hash', sa.String(length=128), nullable=True))
    op.create_index('ix_audit_logs_prev_hash', 'audit_logs', ['prev_hash'])
    op.create_index('ix_audit_logs_hash', 'audit_logs', ['hash'])

def downgrade() -> None:
    op.drop_index('ix_audit_logs_hash', table_name='audit_logs')
    op.drop_index('ix_audit_logs_prev_hash', table_name='audit_logs')
    op.drop_column('audit_logs', 'hash')
    op.drop_column('audit_logs', 'prev_hash')