"""Quality & shared rotation entities: QualityRubric, QCCheck, ReviewRotation, Contest."""

from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class QualityRubric(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quality_rubrics"

    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    criteria: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    reference_media_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    leader_agreed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    buyer_agreed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disagreement_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="STUB"
    )  # STUB | AGREED | DISAGREEMENT_FLAGGED


class ReviewRotation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Single shared rotation mechanism parameterized by purpose (QUALITY vs PAYOUT) (§7, §10).
    Uses auditable seeded random selection; leader-assignment is structurally excluded.
    """

    __tablename__ = "review_rotations"

    shg_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(24), nullable=False, index=True)  # QUALITY | PAYOUT
    target_entity_type: Mapped[str] = mapped_column(String(32), nullable=False)  # order | payout_batch
    target_entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    selection_seed: Mapped[str] = mapped_column(String(128), nullable=False)
    eligible_member_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    selected_member_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    opted_out_member_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    committee_size: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ACTIVE"
    )  # ACTIVE | COMPLETED


class QCCheck(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "qc_checks"

    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task_assignments.id", ondelete="CASCADE"), nullable=False
    )
    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submitted_media_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("media.id", ondelete="SET NULL"), nullable=True
    )
    reviewer_member_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    rotation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("review_rotations.id", ondelete="SET NULL"), nullable=True
    )
    units_checked: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    outcome: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"
    )  # PENDING | PASS | FLAG | ESCALATE | RESOLVED
    flag_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    private_coaching_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    contest_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Contest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Generalized contest referencing either a QC check or a Payout batch (§10)."""

    __tablename__ = "contests"

    shg_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )  # QC_CHECK | PAYOUT_BATCH
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    raised_by_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="OPEN"
    )  # OPEN | RESOLVED_UPHELD | RESOLVED_DISMISSED
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
