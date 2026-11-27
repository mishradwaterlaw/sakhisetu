"""Money entities: PayoutBatch, LedgerAccount, LedgerEntry."""

from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class LedgerAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ledger_accounts"

    shg_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_type: Mapped[str] = mapped_column(String(24), nullable=False)  # MEMBER | SHG_POOL
    member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="CASCADE"), nullable=True, unique=True
    )
    balance_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class PayoutBatch(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "payout_batches"

    shg_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rotation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("review_rotations.id", ondelete="SET NULL"), nullable=True
    )
    total_amount_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # State machine: PAYOUT_PENDING -> PAYOUT_APPROVED -> DISBURSED (or DISPUTED)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PAYOUT_PENDING", index=True
    )
    group_notice_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    group_approval_broadcast_sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contest_window_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    disbursed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    breakdown_snapshot: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)


class LedgerEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ledger_entries"

    payout_batch_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("payout_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ledger_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="SET NULL"), nullable=True, index=True
    )
    amount_inr: Mapped[float] = mapped_column(Float, nullable=False)
    entry_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="EARNINGS_ACCRUAL"
    )  # EARNINGS_ACCRUAL | DISBURSEMENT | ADJUSTMENT
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_disbursed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
