from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from enum import Enum

class TradeType(Enum):
    EQ = 'eq'
    MTF = 'mtf'

class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), index=True)
    # Optional reference to the trader who executed on behalf of the user (client)
    trader_id = Column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    stock_ticker = Column(String, nullable=False)
    buy_price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    capital_used = Column(Float, nullable=False)
    order_executed_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String)  # e.g., 'open', 'closed'
    sell_price = Column(Float, nullable=True)
    brokerage_charge = Column(Float, nullable=True)  # deduction: brokerage
    mtf_charge = Column(Float, nullable=True)  # deduction: mtf charge
    type = Column(String, nullable=False)  # 'eq' or 'mtf'
    order_execution_type = Column(String, nullable=False, default='MARKET')  # 'MARKET' or 'LIMIT'
    order_id = Column(Integer, ForeignKey('orders.id'))
    
    # Relationships
    user = relationship("User", back_populates="trades", foreign_keys=[user_id])
    order = relationship("Order", back_populates="trades")
    trader = relationship("User", back_populates="executed_trades", foreign_keys=[trader_id])