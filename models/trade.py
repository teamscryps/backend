from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from sqlalchemy_utils import ChoiceType
from enum import Enum

class TradeType(Enum):
    EQ = 'eq'
    MTF = 'mtf'

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    stock_ticker = Column(String, nullable=False)
    buy_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    capital_used = Column(Float, nullable=False)
    order_executed_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String)  # e.g., 'open', 'closed', etc.
    sell_price = Column(Float)
    brokerage_charge = Column(Float)  # deduction: brokerage
    mtf_charge = Column(Float)  # deduction: mtf charge
    type = Column(ChoiceType(TradeType)) # 'eq' or 'mtf'
    order_id = Column(Integer, ForeignKey('orders.id'))
    order = relationship("Order", back_populates="trades")