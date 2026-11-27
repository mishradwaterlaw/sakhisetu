"""Pricing, sourcing, and federation pooled-buying seam (§10, §11)."""

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class QuoteCheck(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "quote_checks"

    order_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    material_cost_inr: Mapped[float] = mapped_column(Float, nullable=False)
    labour_cost_inr: Mapped[float] = mapped_column(Float, nullable=False)
    overhead_inr: Mapped[float] = mapped_column(Float, nullable=False)
    margin_inr: Mapped[float] = mapped_column(Float, nullable=False)
    market_trend_adjustment_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    minimum_viable_price_per_unit_inr: Mapped[float] = mapped_column(Float, nullable=False)
    buyer_offer_per_unit_inr: Mapped[float | None] = mapped_column(Float, nullable=True)
    gap_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommendation: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # ACCEPT | COUNTER_OFFER | DECLINE
    breakdown_details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SupplierQuote(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "supplier_quotes"

    federation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("federations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    shg_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("shgs.id", ondelete="SET NULL"), nullable=True
    )
    supplier_party_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("parties.id", ondelete="CASCADE"), nullable=False
    )
    material_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("materials.id", ondelete="CASCADE"), nullable=False
    )
    unit_price_inr: Mapped[float] = mapped_column(Float, nullable=False)
    min_order_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    delivery_days: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PooledBuyAllocation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Extensible seam (§10) allowing a supplier quote/material order to span multiple SHGs under one federation."""

    __tablename__ = "pooled_buy_allocations"

    federation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("federations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    supplier_quote_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("supplier_quotes.id", ondelete="CASCADE"), nullable=False
    )
    shg_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("shgs.id", ondelete="CASCADE"), nullable=False
    )
    allocated_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PROPOSED")
