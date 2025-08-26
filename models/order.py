
from sqlalchemy import Boolean, Column, Float,Integer,String,ForeignKey, DateTime, Numeric
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Order(Base):
    __tablename__ = "orders"
    
    id=Column(Integer,primary_key=True,index=True)
    user_id=Column(Integer,ForeignKey('users.id'))
    stock_symbol=Column(String)
    quantity=Column(Integer)
    price=Column(Float)
    order_type=Column(String)
    mtf_enabled=Column(Boolean, default=False)
    order_executed_at=Column(DateTime, default=datetime.utcnow)
    status = Column(String(30), nullable=True)  # NEW, ACCEPTED, PARTIALLY_FILLED, FILLED, REJECTED, CANCELLED
    broker_order_id = Column(String(100), nullable=True)
    filled_qty = Column(Integer, nullable=False, default=0)
    avg_fill_price = Column(Numeric(18,4), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="orders")
    trades = relationship("Trade", back_populates="order")
 
# If theres incomplete order, we can use this to track the order