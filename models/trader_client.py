from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base


class TraderClient(Base):
    __tablename__ = "trader_clients"

    id = Column(Integer, primary_key=True, index=True)
    trader_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    client_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint('trader_id', 'client_id', name='uq_trader_client_pair'),
    )
