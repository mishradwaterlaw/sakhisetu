"""Catalogue & cost entities: Product, TaskTemplate, TemplateRequirement, Tool, Material, PriceModel."""

from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Tool(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tools"

    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Material(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "materials"

    name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="meters")
    unit_cost_inr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class Product(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="stitching")
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="piece")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    task_templates: Mapped[list["TaskTemplate"]] = relationship(
        back_populates="product", order_by="TaskTemplate.sequence_order"
    )
    price_models: Mapped[list["PriceModel"]] = relationship(back_populates="product")


class TaskTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "task_templates"

    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_name: Mapped[str] = mapped_column(String(100), nullable=False)  # cut | stitch | check | pack
    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    depends_on_step_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    minutes_per_unit: Mapped[float] = mapped_column(Float, nullable=False, default=15.0)
    required_skill: Mapped[str] = mapped_column(String(80), nullable=False)
    piece_rate_inr: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)

    product: Mapped[Product] = relationship(back_populates="task_templates")
    requirements: Mapped[list["TemplateRequirement"]] = relationship(back_populates="task_template")


class TemplateRequirement(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "template_requirements"

    task_template_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("task_templates.id", ondelete="CASCADE"), nullable=False
    )
    requirement_type: Mapped[str] = mapped_column(String(20), nullable=False)  # tool | material
    tool_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("tools.id", ondelete="SET NULL"), nullable=True
    )
    material_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("materials.id", ondelete="SET NULL"), nullable=True
    )
    quantity_per_unit: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    task_template: Mapped[TaskTemplate] = relationship(back_populates="requirements")


class PriceModel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "price_models"

    product_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hourly_wage_benchmark_inr: Mapped[float] = mapped_column(Float, nullable=False, default=75.0)
    overhead_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.12)
    target_margin_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.15)
    # Explicitly labeled placeholder parameter per §11 (no fake live market feed)
    market_trend_placeholder_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    market_trend_note: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
        default="Configured placeholder assumption (not a live external market feed)",
    )

    product: Mapped[Product] = relationship(back_populates="price_models")
