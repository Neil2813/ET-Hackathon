from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from db.orm_models import Base

class Message(Base):
    __tablename__ = "copilot_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(50), ForeignKey("copilot_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
