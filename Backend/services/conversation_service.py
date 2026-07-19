from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from db.orm_models import SessionLocal
from models.conversation import Conversation as SQLConversation
from models.message import Message as SQLMessage
from services.firestore import is_firestore_enabled, _client as get_firestore_client
from services.firestore_store import _safe_doc_id

class ConversationService:
    @staticmethod
    def get_or_create_active_conversation(user_id: str) -> str:
        """
        Retrieves the most recent conversation ID for the user,
        or creates a new one if none exists.
        """
        if is_firestore_enabled():
            db = get_firestore_client()
            query = db.collection("copilot_conversations")\
                      .where("user_id", "==", user_id)\
                      .order_by("updated_at", direction="DESCENDING")\
                      .limit(1)\
                      .stream()
            results = list(query)
            if results:
                return results[0].id
            
            # Create a new conversation doc
            conv_id = f"conv_{uuid.uuid4().hex}"
            db.collection("copilot_conversations").document(conv_id).set({
                "id": conv_id,
                "user_id": user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "title": "Active Session",
                "messages": []
            })
            return conv_id
        else:
            session = SessionLocal()
            try:
                # Find most recent
                conv = session.query(SQLConversation)\
                              .filter(SQLConversation.user_id == user_id)\
                              .order_by(SQLConversation.updated_at.desc())\
                              .first()
                if conv:
                    return conv.id

                # Create new
                conv_id = f"conv_{uuid.uuid4().hex}"
                new_conv = SQLConversation(
                    id=conv_id,
                    user_id=user_id,
                    title="Active Session",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                session.add(new_conv)
                session.commit()
                return conv_id
            finally:
                session.close()

    @staticmethod
    def add_message(conversation_id: str, role: str, content: str) -> None:
        """
        Adds a message to the active conversation.
        """
        timestamp_str = datetime.now(timezone.utc).isoformat()
        if is_firestore_enabled():
            db = get_firestore_client()
            doc_ref = db.collection("copilot_conversations").document(conversation_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict() or {}
                messages = data.get("messages") or []
                messages.append({
                    "role": role,
                    "content": content,
                    "timestamp": timestamp_str
                })
                doc_ref.set({
                    "messages": messages,
                    "updated_at": timestamp_str
                }, merge=True)
        else:
            session = SessionLocal()
            try:
                # Add SQL message
                msg = SQLMessage(
                    conversation_id=conversation_id,
                    role=role,
                    content=content,
                    timestamp=datetime.now(timezone.utc)
                )
                session.add(msg)
                
                # Update conversation updated_at
                conv = session.query(SQLConversation).filter(SQLConversation.id == conversation_id).first()
                if conv:
                    conv.updated_at = datetime.now(timezone.utc)
                
                session.commit()
            finally:
                session.close()

    @staticmethod
    def get_conversation_messages(conversation_id: str) -> list[dict[str, Any]]:
        """
        Retrieves all messages for the specified conversation.
        """
        if is_firestore_enabled():
            db = get_firestore_client()
            doc = db.collection("copilot_conversations").document(conversation_id).get()
            if doc.exists:
                return doc.to_dict().get("messages") or []
            return []
        else:
            session = SessionLocal()
            try:
                msgs = session.query(SQLMessage)\
                              .filter(SQLMessage.conversation_id == conversation_id)\
                              .order_by(SQLMessage.timestamp.asc())\
                              .all()
                return [
                    {
                        "role": m.role,
                        "content": m.content,
                        "timestamp": m.timestamp.isoformat() if m.timestamp else None
                    }
                    for m in msgs
                ]
            finally:
                session.close()

    @staticmethod
    def clear_conversation(conversation_id: str) -> None:
        """
        Clears all messages from the specified conversation.
        """
        if is_firestore_enabled():
            db = get_firestore_client()
            doc_ref = db.collection("copilot_conversations").document(conversation_id)
            doc_ref.set({
                "messages": [],
                "updated_at": datetime.now(timezone.utc).isoformat()
            }, merge=True)
        else:
            session = SessionLocal()
            try:
                session.query(SQLMessage).filter(SQLMessage.conversation_id == conversation_id).delete()
                conv = session.query(SQLConversation).filter(SQLConversation.id == conversation_id).first()
                if conv:
                    conv.updated_at = datetime.now(timezone.utc)
                session.commit()
            finally:
                session.close()
