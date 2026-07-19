from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from db.orm_models import Base

class Conversation(Base):
    __tablename__ = "copilot_conversations"

    id = Column(String(50), primary_key=True, index=True)
    user_id = Column(String(50), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    title = Column(String(100), nullable=True)
