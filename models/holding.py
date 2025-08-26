from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint
from database import Base


class Holding(Base):
	__tablename__ = "holdings"

	id = Column(Integer, primary_key=True, index=True)
	user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
	symbol = Column(String, nullable=False)
	quantity = Column(Integer, nullable=False, default=0)
	reserved_qty = Column(Integer, nullable=False, default=0)
	avg_price = Column(Float, nullable=False, default=0.0)
	last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)

	__table_args__ = (
		UniqueConstraint('user_id', 'symbol', name='uq_user_symbol'),
	)

