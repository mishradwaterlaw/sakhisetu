"""Intake entities: Media, InboundMessage, Order, ExtractedField, Clarification, OrderLine."""

from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Media(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "media"

    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    media_type: Mapped[str] = mapped_column(String(32), nullable=False)  # audio | image | pdf | text
    storage_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False, default="application/octet-stream")
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)


class InboundMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Normalized inbound message from WhatsApp, Exotel Voice/DTMF, or JanAI Café (§3, §4)."""

    __tablename__ = "inbound_messages"

    shg_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("shgs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    channel: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # whatsapp_smartphone | basic_phone_voice | janai_cafe
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    sender_phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    sender_member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    sender_party_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("parties.id", ondelete="SET NULL"), nullable=True
    )
    is_quarantined: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    detected_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    media_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("media.id", ondelete="SET NULL"), nullable=True
    )
    # §20: Photo disambiguation (ORDER_DOCUMENT | SAMPLE_OR_FINISHED_ITEM | AMBIGUOUS)
    photo_kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Intent routing (§4.4)
    intent: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"
    )  # NEW_ORDER | BLOCKER_REPORT | FINISHED_WORK | CLARIFICATION_REPLY | UNROUTED | QUARANTINED
    intent_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    routing_method: Mapped[str | None] = mapped_column(String(32), nullable=True)  # deterministic | llm | user_disambiguated
    # Assisted-entry audit for JanAI Café
    operator_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    member_consented: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Order(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "orders"

    shg_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    buyer_party_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("parties.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_message_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("inbound_messages.id", ondelete="SET NULL"), nullable=True
    )
    product_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    order_code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    # State machine status (§2, §4, §5, §6, §7)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="DRAFT", index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    offered_price_per_unit_inr: Mapped[float | None] = mapped_column(Float, nullable=True)
    agreed_price_per_unit_inr: Mapped[float | None] = mapped_column(Float, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    spec_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_terms: Mapped[str | None] = mapped_column(String(250), nullable=True)
    reference_media_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    has_uncertain_fields: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rubric_disagreement_risk: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    extracted_fields: Mapped[list["ExtractedField"]] = relationship(back_populates="order")
    lines: Mapped[list["OrderLine"]] = relationship(back_populates="order")


class ExtractedField(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Stores value, confidence score, and exact source span (§4.5)."""

    __tablename__ = "extracted_fields"

    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_span: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_uncertain: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    leader_override_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    leader_override_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    order: Mapped[Order] = relationship(back_populates="extracted_fields")


class Clarification(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "clarifications"

    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    inbound_message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inbound_messages.id", ondelete="CASCADE"), nullable=False
    )
    target_field: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="OPEN"
    )  # OPEN | ANSWERED | ESCALATED_LEADER
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)


class OrderLine(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "order_lines"

    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_inr: Mapped[float | None] = mapped_column(Float, nullable=True)

    order: Mapped[Order] = relationship(back_populates="lines")
