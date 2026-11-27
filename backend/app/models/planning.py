"""Plan, track, recover entities: Task, TaskDependency, TaskAssignment, Blocker, RecoveryOption, Inventory, MaterialTransaction."""

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Task(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tasks"

    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    template_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("task_templates.id", ondelete="SET NULL"), nullable=True
    )
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)
    required_skill: Mapped[str] = mapped_column(String(80), nullable=False)
    total_units: Mapped[int] = mapped_column(Integer, nullable=False)
    minutes_per_unit: Mapped[float] = mapped_column(Float, nullable=False)
    piece_rate_inr: Mapped[float] = mapped_column(Float, nullable=False)
    required_tools: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PENDING"
    )  # PENDING | ASSIGNED | IN_PROGRESS | BLOCKED | COMPLETED


class TaskDependency(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "task_dependencies"

    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    depends_on_task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )


class TaskAssignment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "task_assignments"

    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_units: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    passed_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    # Solver-grounded explanation (§5)
    solver_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    solver_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_leader_override: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="PROPOSED"
    )  # PROPOSED | APPROVED | IN_PROGRESS | COMPLETED | REASSIGNED


class Blocker(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "blockers"

    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("task_assignments.id", ondelete="SET NULL"), nullable=True
    )
    reported_by_member_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("members.id", ondelete="CASCADE"), nullable=False
    )
    source_message_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("inbound_messages.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    remaining_units: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="OPEN"
    )  # OPEN | RECOVERY_APPROVED | RESOLVED

    recovery_options: Mapped[list["RecoveryOption"]] = relationship(back_populates="blocker")


class RecoveryOption(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "recovery_options"

    blocker_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("blockers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    option_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # REASSIGN_UNITS | EXTEND_DEADLINE | SPLIT_BATCH
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    blocker: Mapped[Blocker] = relationship(back_populates="recovery_options")


class Inventory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "inventories"

    shg_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shgs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    material_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("materials.id", ondelete="CASCADE"), nullable=False
    )
    quantity_on_hand: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class MaterialTransaction(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "material_transactions"

    inventory_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inventories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    delta_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
