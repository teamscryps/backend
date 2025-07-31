from sqlalchemy import Column, Integer, String, DateTime
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password = Column(String, nullable=False)  # Changed from hashed_password to match DB
    mobile = Column(String)
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