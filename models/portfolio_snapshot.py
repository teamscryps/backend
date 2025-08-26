from datetime import datetime, date
from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey, Numeric, Text, Index
from sqlalchemy.types import JSON as GenericJSON
from database import Base
import os

_DATABASE_URL = os.getenv("DATABASE_URL", "")
# Keep JSON generic (can be migrated to JSONB if needed) simplicity

class PortfolioSnapshot(Base):
    __tablename__ = 'portfolio_snapshots'
    __table_args__ = (
        Index('ix_snapshot_user_date', 'user_id', 'snapshot_date'),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), index=True, nullable=False)
    snapshot_date = Column(Date, nullable=False)
    cash_available = Column(Numeric(18,2), nullable=False, default=0)
    cash_blocked = Column(Numeric(18,2), nullable=False, default=0)
    realized_pnl = Column(Numeric(18,2), nullable=False, default=0)
    unrealized_pnl = Column(Numeric(18,2), nullable=False, default=0)
    holdings = Column(GenericJSON, nullable=False)  # [{symbol, qty, avg_price, mkt_price, unrealized}]
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
