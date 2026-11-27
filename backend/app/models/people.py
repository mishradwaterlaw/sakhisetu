"""People & group entities: Federation, SHG, Member, Party."""

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.security import EncryptedString


class Federation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "federations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    district: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(120), nullable=False)
    contact_phone_enc: Mapped[str | None] = mapped_column(EncryptedString(512), nullable=True)

    shgs: Mapped[list["SHG"]] = relationship(back_populates="federation")


class SHG(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "shgs"

    federation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("federations.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    village: Mapped[str] = mapped_column(String(150), nullable=False, default="")
    primary_language: Mapped[str] = mapped_column(String(16), nullable=False, default="kn")
    rotation_epoch: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    federation: Mapped[Federation | None] = relationship(back_populates="shgs")
    members: Mapped[list["Member"]] = relationship(back_populates="shg")


class Member(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "members"

    shg_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")  # leader | member
    phone_enc: Mapped[str] = mapped_column(EncryptedString(512), nullable=False)
    phone_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    preferred_language: Mapped[str] = mapped_column(String(16), nullable=False, default="kn")
    # Stored property per §3: whatsapp_smartphone | basic_phone_voice | janai_cafe
    default_channel: Mapped[str] = mapped_column(
        String(32), nullable=False, default="basic_phone_voice"
    )
    has_completed_onboarding: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Capabilities for CP-SAT planner (§5, §10)
    skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    tools: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    available_minutes_per_day: Mapped[int] = mapped_column(Integer, nullable=False, default=240)
    # §19: Workload preference (standard | more | less) + anti-favoritism cycle tracking
    workload_preference: Mapped[str] = mapped_column(String(16), nullable=False, default="standard")
    consecutive_max_share_cycles: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Encrypted payout bank details
    bank_account_enc: Mapped[str | None] = mapped_column(EncryptedString(512), nullable=True)
    ifsc_enc: Mapped[str | None] = mapped_column(EncryptedString(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    shg: Mapped[SHG] = relationship(back_populates="members")


class Party(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """External party: buyer, supplier, or NGO/federation partner."""

    __tablename__ = "parties"

    party_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )  # buyer | supplier | ngo | bank
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone_enc: Mapped[str | None] = mapped_column(EncryptedString(512), nullable=True)
    phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    preferred_language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    default_channel: Mapped[str] = mapped_column(
        String(32), nullable=False, default="whatsapp_smartphone"
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
