"""Governance & audit entities: Approval, ConsentEvent, AgentEvent, CommsLog, UsageMeter."""

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Approval(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Mandatory proof of explicit human sign-off before any gated state transition (§2, §8)."""

    __tablename__ = "approvals"

    shg_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    transition_name: Mapped[str] = mapped_column(String(80), nullable=False)
    actor_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # LEADER | REVIEW_COMMITTEE | BUYER | FEDERATION
    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    decision: Mapped[str] = mapped_column(String(24), nullable=False, default="APPROVED")  # APPROVED | REJECTED
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class ConsentEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Mandatory checkpoint before any external data/bank-file release (§8)."""

    __tablename__ = "consent_events"

    shg_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    granted_by_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    recipient_type: Mapped[str] = mapped_column(String(32), nullable=False)  # BANK | BUYER | FEDERATION
    recipient_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    purpose: Mapped[str] = mapped_column(String(200), nullable=False)
    scope: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    consented: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class AgentEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Step-by-step Lyzr ADK SuperFlow audit trace (§8)."""

    __tablename__ = "agent_events"

    shg_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("shgs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_name: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="OK")  # OK | FALLBACK | ERROR


class CommsLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Every outbound message/call, enabling on-demand replayability (§7, §12)."""

    __tablename__ = "comms_logs"

    shg_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("shgs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recipient_member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="SET NULL"), nullable=True, index=True
    )
    recipient_party_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("parties.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="kn")
    message_category: Mapped[str] = mapped_column(
        String(40), nullable=False
    )  # GROUP_PAYOUT_NOTICE | GROUP_APPROVAL_BROADCAST | EARNINGS_READBACK | CLARIFICATION | ONBOARDING | REMINDER
    fact_text: Mapped[str] = mapped_column(Text, nullable=False)
    action_text: Mapped[str] = mapped_column(Text, nullable=False)
    request_text: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    audio_media_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("media.id", ondelete="SET NULL"), nullable=True
    )
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False, default="SENT")
    is_replayable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class UsageMeter(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Real cost & usage metering per group & billing period (§9)."""

    __tablename__ = "usage_meters"

    shg_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_ym: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # YYYY-MM
    resource_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )  # LLM_TOKENS | ASR_MINUTES | TTS_MINUTES | VOICE_MINUTES | WHATSAPP_MSG | VISION_CALL
    provider: Mapped[str] = mapped_column(String(40), nullable=False)  # lyzr | bhashini | sarvam | exotel | gupshup
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unit: Mapped[str] = mapped_column(String(24), nullable=False)  # tokens | minutes | messages | calls
    estimated_cost_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
