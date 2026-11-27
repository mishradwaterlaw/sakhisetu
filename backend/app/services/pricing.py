"""Pricing engine (§11): transparent MVP calculation vs buyer offer."""

from dataclasses import dataclass
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalogue import Material, PriceModel, Product, TaskTemplate, TemplateRequirement
from app.models.pricing import QuoteCheck


@dataclass
class PricingBreakdown:
    material_cost_per_unit_inr: float
    labour_cost_per_unit_inr: float
    overhead_per_unit_inr: float
    margin_per_unit_inr: float
    market_trend_adjustment_inr: float
    market_trend_is_placeholder: bool
    market_trend_note: str
    minimum_viable_price_per_unit_inr: float
    buyer_offer_per_unit_inr: float | None
    gap_pct: float | None
    recommendation: str


def compute_order_pricing(
    db: Session,
    *,
    order_id: str,
    product_id: str,
    quantity: int,
    buyer_offer_per_unit_inr: float | None,
    persist: bool = True,
) -> PricingBreakdown:
    product = db.get(Product, product_id)
    if not product:
        raise ValueError(f"Product {product_id} not found")

    price_model = db.scalar(select(PriceModel).where(PriceModel.product_id == product_id))
    hourly_wage = price_model.hourly_wage_benchmark_inr if price_model else 75.0
    overhead_pct = price_model.overhead_pct if price_model else 0.12
    margin_pct = price_model.target_margin_pct if price_model else 0.15
    trend_pct = price_model.market_trend_placeholder_pct if price_model else 0.0
    trend_note = (
        price_model.market_trend_note
        if price_model
        else "Configured placeholder assumption (not a live external market feed)"
    )

    templates = db.scalars(select(TaskTemplate).where(TaskTemplate.product_id == product_id)).all()

    total_minutes_per_unit = sum(t.minutes_per_unit for t in templates)
    labour_cost = (total_minutes_per_unit / 60.0) * hourly_wage

    material_cost = 0.0
    for tmpl in templates:
        reqs = db.scalars(
            select(TemplateRequirement).where(
                TemplateRequirement.task_template_id == tmpl.id,
                TemplateRequirement.requirement_type == "material",
            )
        ).all()
        for req in reqs:
            if req.material_id:
                mat = db.get(Material, req.material_id)
                if mat:
                    material_cost += req.quantity_per_unit * mat.unit_cost_inr

    direct_cost = material_cost + labour_cost
    overhead = direct_cost * overhead_pct
    subtotal = direct_cost + overhead
    margin = subtotal * margin_pct
    trend_adj = subtotal * trend_pct
    mvp = round(subtotal + margin + trend_adj, 2)

    gap_pct: float | None = None
    recommendation = "COUNTER_OFFER"
    if buyer_offer_per_unit_inr is not None and mvp > 0:
        gap_pct = round(((buyer_offer_per_unit_inr - mvp) / mvp) * 100.0, 2)
        if buyer_offer_per_unit_inr >= mvp:
            recommendation = "ACCEPT"
        elif buyer_offer_per_unit_inr >= (direct_cost + overhead):
            recommendation = "COUNTER_OFFER"
        else:
            recommendation = "DECLINE"

    if persist:
        qc = QuoteCheck(
            order_id=order_id,
            material_cost_inr=round(material_cost, 2),
            labour_cost_inr=round(labour_cost, 2),
            overhead_inr=round(overhead, 2),
            margin_inr=round(margin, 2),
            market_trend_adjustment_inr=round(trend_adj, 2),
            minimum_viable_price_per_unit_inr=mvp,
            buyer_offer_per_unit_inr=buyer_offer_per_unit_inr,
            gap_pct=gap_pct,
            recommendation=recommendation,
            breakdown_details={
                "quantity": quantity,
                "hourly_wage_benchmark_inr": hourly_wage,
                "total_minutes_per_unit": total_minutes_per_unit,
                "overhead_pct": overhead_pct,
                "target_margin_pct": margin_pct,
                "market_trend_placeholder_pct": trend_pct,
                "market_trend_is_placeholder": True,
                "market_trend_note": trend_note,
            },
        )
        db.add(qc)
        db.flush()

    return PricingBreakdown(
        material_cost_per_unit_inr=round(material_cost, 2),
        labour_cost_per_unit_inr=round(labour_cost, 2),
        overhead_per_unit_inr=round(overhead, 2),
        margin_per_unit_inr=round(margin, 2),
        market_trend_adjustment_inr=round(trend_adj, 2),
        market_trend_is_placeholder=True,
        market_trend_note=trend_note,
        minimum_viable_price_per_unit_inr=mvp,
        buyer_offer_per_unit_inr=buyer_offer_per_unit_inr,
        gap_pct=gap_pct,
        recommendation=recommendation,
    )


def compare_supplier_quotes(
    db: Session,
    *,
    material_id: str,
    required_quantity: float,
    federation_id: str | None = None,
) -> list[dict]:
    """Side-by-side supplier comparison (§15) & federation pooled-buying (§17a) reusing the same cost engine."""
    from app.models.people import Party
    from app.models.pricing import SupplierQuote

    stmt = select(SupplierQuote).where(SupplierQuote.material_id == material_id)
    if federation_id:
        stmt = stmt.where(SupplierQuote.federation_id == federation_id)
    quotes = db.scalars(stmt).all()

    comparisons = []
    for q in quotes:
        supplier = db.get(Party, q.supplier_party_id)
        effective_qty = max(float(q.min_order_qty), required_quantity)
        total_cost = round(effective_qty * q.unit_price_inr, 2)
        comparisons.append(
            {
                "supplier_quote_id": q.id,
                "supplier_name": supplier.name if supplier else q.supplier_party_id,
                "unit_price_inr": q.unit_price_inr,
                "min_order_qty": q.min_order_qty,
                "delivery_days": q.delivery_days,
                "effective_order_qty": effective_qty,
                "total_cost_inr": total_cost,
                "notes": q.notes,
            }
        )
    comparisons.sort(key=lambda x: (x["total_cost_inr"], x["delivery_days"]))
    return comparisons


def draft_buyer_counter_offer(
    breakdown: PricingBreakdown,
    *,
    order_code: str,
    product_name: str,
    quantity: int,
    leader_language: str = "en",
) -> dict:
    """Draft (never auto-send) a buyer counter-offer grounded in the real QuoteCheck breakdown (§15)."""
    mvp = breakdown.minimum_viable_price_per_unit_inr
    offer = breakdown.buyer_offer_per_unit_inr or 0.0
    draft_text = (
        f"Namaste, regarding order {order_code} ({quantity} x {product_name}): "
        f"your offer is ₹{offer:.2f}/unit. Our transparent minimum viable cost is ₹{mvp:.2f}/unit "
        f"(Material ₹{breakdown.material_cost_per_unit_inr:.2f} + "
        f"Labour ₹{breakdown.labour_cost_per_unit_inr:.2f} + "
        f"Overhead ₹{breakdown.overhead_per_unit_inr:.2f} + "
        f"SHG Margin ₹{breakdown.margin_per_unit_inr:.2f}). "
        f"We propose ₹{mvp:.2f}/unit so every artisan receives fair wage. Please confirm."
    )
    return {
        "order_code": order_code,
        "language": leader_language,
        "requires_leader_review_before_send": True,
        "proposed_unit_price_inr": mvp,
        "draft_message": draft_text,
    }
