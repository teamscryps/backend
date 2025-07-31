from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    name = Column(String, nullable=False)
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)  # Changed from hashed_password to match DB
    mobile = Column(String, nullable=False)  # Mobile is now required
    api_key = Column(String)
    api_secret = Column(String)
    broker = Column(String)  # e.g., 'zerodha', 'grow'
    session_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    session_updated_at = Column(DateTime, default=datetime.utcnow)
    refresh_token = Column(String, nullable=True)
    otp = Column(String, nullable=True)
    otp_expiry = Column(DateTime, nullable=True)
    broker_refresh_token = Column(String, nullable=True)
    capital = Column(Integer, nullable=False, default=0)  # New field for user capital
    api_credentials_set = Column(Boolean, default=False)  # Track if API credentials are set
    orders = relationship("Order", back_populates="user")
    trades = relationship("Trade", back_populates="user")
