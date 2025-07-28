from sqlalchemy import Column, Integer, String, DateTime
from database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    mobile = Column(String)
    api_key = Column(String)
    api_secret = Column(String)
    broker = Column(String)  # e.g., 'zerodha', 'grow'
    session_id = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    session_updated_at = Column(DateTime, default=datetime.utcnow)