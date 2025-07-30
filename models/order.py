
from sqlalchemy import Boolean, Column, Float,Integer,String,ForeignKey, DateTime
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
    trades = relationship("Trade", back_populates="order")
 
# If theres incomplete order, we can use this to track the order