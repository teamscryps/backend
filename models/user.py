from sqlalchemy import Column, Integer, String, DateTime, Boolean, Numeric
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
    # New trader/client role separation (nullable initially, default handled in migration)
    role = Column(String(10), nullable=True)  # 'trader' | 'client'
    # Track currently uncommitted free funds separate from allocated capital
    # Deprecated: available_funds (will be phased out after migration). Use cash_available & cash_blocked
    available_funds = Column(Integer, nullable=True)
    cash_available = Column(Numeric(18,2), nullable=True)
    cash_blocked = Column(Numeric(18,2), nullable=False, default=0)
    orders = relationship("Order", back_populates="user")
    # Trades where this user is the client (user_id)
    trades = relationship(
        "Trade",
        back_populates="user",
        foreign_keys="Trade.user_id"
    )
    # Trades this user executed as trader (trader_id)
    executed_trades = relationship(
        "Trade",
        back_populates="trader",
        foreign_keys="Trade.trader_id"
    )
