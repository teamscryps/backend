from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON as GenericJSON
from sqlalchemy import inspect
from sqlalchemy import create_engine
import os
from database import Base


# Determine if using SQLite (e.g., in tests) to fallback from JSONB
_DATABASE_URL = os.getenv("DATABASE_URL", "")
if _DATABASE_URL.startswith("sqlite") or _DATABASE_URL == "":
    JSONType = GenericJSON  # fallback for tests
else:
    JSONType = JSONB


class AuditLog(Base):
    """Fine-grained trader action log (actor -> target)."""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_actor_action_created", "actor_user_id", "action", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    target_user_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    details = Column(JSONType, nullable=True)  # renamed from metadata; JSONB in prod, JSON in tests
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    prev_hash = Column(String(128), nullable=True, index=True)
    hash = Column(String(128), nullable=True, index=True)
