from datetime import datetime
from time import timezone
from sqlalchemy import Column, DateTime, Integer, String, Text, JSON
from database import Base


class Audit(Base):
    __tablename__ = "audit"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    level = Column(String)  # INFO, ERROR, WARNING, DEBUG
    action = Column(String)  # The action being performed
    user_id = Column(String)  # User ID or "anonymous"
    user_email = Column(String)  # User email or "anonymous"
    correlation_id = Column(String)  # Unique correlation ID for request tracking
    context = Column(JSON)  # Additional context data as JSON
    method = Column(String, nullable=True)  # HTTP method
    url = Column(String, nullable=True)  # Request URL
    client_ip = Column(String, nullable=True)  # Client IP address
    error_message = Column(Text, nullable=True)  # Error message if any
    stack_trace = Column(Text, nullable=True)  # Stack trace for errors
    request_data = Column(JSON, nullable=True)  # Request data
    response_data = Column(JSON, nullable=True)  # Response data
    duration_ms = Column(Integer, nullable=True)  # Request duration in milliseconds
    status_code = Column(Integer, nullable=True)  # HTTP status code
    