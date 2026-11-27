"""SHG-scoped conversations and per-leader inbox position."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import UUIDPrimaryKeyMixin, utc_now


class Conversation(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "conversations"

    shg_id: Mapped[str] = mapped_column(ForeignKey("shgs.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(32))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class ConversationParticipant(Base):
    __tablename__ = "conversation_participants"

    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    identity: Mapped[str] = mapped_column(String(80), primary_key=True)
    member_id: Mapped[str | None] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    party_id: Mapped[str | None] = mapped_column(ForeignKey("parties.id", ondelete="CASCADE"))


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (Index("ix_conversation_message_position", "conversation_id", "position"),)

    position: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"))
    source_key: Mapped[str] = mapped_column(String(128), unique=True)
    inbound_id: Mapped[str | None] = mapped_column(ForeignKey("inbound_messages.id", ondelete="CASCADE"))
    direction: Mapped[str] = mapped_column(String(16))
    sender: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    topic: Mapped[str] = mapped_column(String(16), default="general")
    sample_photo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ConversationOrder(Base):
    __tablename__ = "conversation_orders"

    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), primary_key=True)


class ConversationRead(Base):
    __tablename__ = "conversation_reads"

    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    leader_id: Mapped[str] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
