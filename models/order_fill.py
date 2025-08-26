from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class OrderFill(Base):
    __tablename__ = "order_fills"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey('orders.id', ondelete='CASCADE'), index=True, nullable=False)
    broker_fill_id = Column(String(100), nullable=True)
    quantity = Column(Integer, nullable=False)
    price = Column(Numeric(18,4), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

