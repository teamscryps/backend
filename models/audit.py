from datetime import datetime
from time import timezone
from sqlalchemy import Column, DateTime, Integer, String
from database import Base


class Audit(Base):
    __tablename__ = "audit"

    id=Column(Integer, primary_key=True, index=True)
    action=Column(String)
    timestamp=Column(DateTime(timezone=True),default=lambda: datetime.now(timezone.utc))
    