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
    product_id: str | None,
    quantity: int,
    buyer_offer_per_unit_inr: float | None,
    persist: bool = True,
) -> PricingBreakdown:
    product = db.get(Product, product_id) if product_id else None
    templates = (
        db.scalars(select(TaskTemplate).where(TaskTemplate.product_id == product_id)).all()
        if product
        else []
    )

    if not product or not templates:
        note = "Insufficient catalogue/task cost data to compute a reliable minimum viable price."
        if persist:
            db.add(
                QuoteCheck(
                    order_id=order_id,
                    material_cost_inr=0.0,
                    labour_cost_inr=0.0,
                    overhead_inr=0.0,
                    margin_inr=0.0,
                    market_trend_adjustment_inr=0.0,
                    minimum_viable_price_per_unit_inr=0.0,
                    buyer_offer_per_unit_inr=buyer_offer_per_unit_inr,
                    gap_pct=None,
                    recommendation="INSUFFICIENT_DATA",
                    breakdown_details={"quantity": quantity, "reason": note},
                )
            )
            db.flush()
        return PricingBreakdown(
            material_cost_per_unit_inr=0.0,
            labour_cost_per_unit_inr=0.0,
            overhead_per_unit_inr=0.0,
            margin_per_unit_inr=0.0,
            market_trend_adjustment_inr=0.0,
            market_trend_is_placeholder=True,
            market_trend_note=note,
            minimum_viable_price_per_unit_inr=0.0,
            buyer_offer_per_unit_inr=buyer_offer_per_unit_inr,
            gap_pct=None,
            recommendation="INSUFFICIENT_DATA",
        )

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
    force_draft: bool = False,
) -> dict:
    """Deterministic margin-aware analysis & counter-offer draft (never auto-sends, §15).

    Branches cleanly on recommendation:
    - INSUFFICIENT_DATA: refuses to guess a counter-offer.
    - ACCEPT (offer >= MVP): confirms surplus/margin; does NOT propose a lower price.
    - COUNTER_OFFER / DECLINE (offer < MVP or missing): proposes MVP citing exact shortfall.
    """
    mvp = breakdown.minimum_viable_price_per_unit_inr
    offer = breakdown.buyer_offer_per_unit_inr
    base_cost = round(
        breakdown.material_cost_per_unit_inr
        + breakdown.labour_cost_per_unit_inr
        + breakdown.overhead_per_unit_inr,
        2,
    )

    if breakdown.recommendation == "INSUFFICIENT_DATA" or mvp <= 0:
        return {
            "order_code": order_code,
            "language": leader_language,
            "verdict": "INSUFFICIENT_DATA",
            "needs_counter_offer": False,
            "requires_leader_review_before_send": True,
            "proposed_unit_price_inr": offer,
            "rationale": "Can't compute a reliable cost basis for this product yet (missing catalogue/task cost data).",
            "draft_message": None,
            "engine": "local_deterministic_fallback",
            "agent_name": "DeterministicPricingAnalyst",
            "tokens": 0,
            "trace_id": None,
        }

    if breakdown.recommendation == "ACCEPT" and offer is not None and not force_draft:
        surplus = round(offer - mvp, 2)
        realized_margin = round(offer - base_cost, 2)
        return {
            "order_code": order_code,
            "language": leader_language,
            "verdict": "ACCEPT",
            "needs_counter_offer": False,
            "requires_leader_review_before_send": True,
            "proposed_unit_price_inr": offer,
            "rationale": (
                f"Buyer offer ₹{offer:.2f}/unit meets or exceeds minimum viable price ₹{mvp:.2f}/unit "
                f"(+₹{surplus:.2f}/unit above MVP; ₹{realized_margin:.2f}/unit margin above base cost ₹{base_cost:.2f})."
            ),
            "draft_message": None,
            "engine": "local_deterministic_fallback",
            "agent_name": "DeterministicPricingAnalyst",
            "tokens": 0,
            "trace_id": None,
        }

    if breakdown.recommendation == "ACCEPT" and offer is not None and force_draft:
        target_price = round(offer * 1.1, 2)
        draft_text = (
            f"Namaste, regarding order {order_code} ({quantity} x {product_name}): "
            f"thank you for your offer of ₹{offer:.2f}/unit. Given current material and artisan capacity, "
            f"we propose ₹{target_price:.2f}/unit for this batch. Please confirm if this works."
        )
        return {
            "order_code": order_code,
            "language": leader_language,
            "verdict": "ACCEPT",
            "needs_counter_offer": False,
            "requires_leader_review_before_send": True,
            "proposed_unit_price_inr": target_price,
            "rationale": f"Optional custom quote drafted above buyer offer ₹{offer:.2f}/unit.",
            "draft_message": draft_text,
            "engine": "local_deterministic_fallback",
            "agent_name": "DeterministicPricingAnalyst",
            "tokens": 0,
            "trace_id": None,
        }

    offer_val = offer if offer is not None else 0.0
    shortfall = round(mvp - offer_val, 2)
    offer_phrase = (
        f"your offer of ₹{offer_val:.2f}/unit is ₹{shortfall:.2f}/unit below our minimum viable cost"
        if offer is not None
        else "no unit price was specified yet"
    )
    draft_text = (
        f"Namaste, regarding order {order_code} ({quantity} x {product_name}): "
        f"{offer_phrase} of ₹{mvp:.2f}/unit "
        f"(Material ₹{breakdown.material_cost_per_unit_inr:.2f} + "
        f"Labour ₹{breakdown.labour_cost_per_unit_inr:.2f} + "
        f"Overhead ₹{breakdown.overhead_per_unit_inr:.2f} + "
        f"SHG Margin ₹{breakdown.margin_per_unit_inr:.2f}). "
        f"We propose ₹{mvp:.2f}/unit so every artisan receives fair wage. Please confirm."
    )
    return {
        "order_code": order_code,
        "language": leader_language,
        "verdict": breakdown.recommendation,
        "needs_counter_offer": True,
        "requires_leader_review_before_send": True,
        "proposed_unit_price_inr": mvp,
        "rationale": f"Buyer offer is below MVP ₹{mvp:.2f}/unit by ₹{shortfall:.2f}/unit.",
        "draft_message": draft_text,
        "engine": "local_deterministic_fallback",
        "agent_name": "DeterministicPricingAnalyst",
        "tokens": 0,
        "trace_id": None,
    }


def analyze_and_draft_pricing(
    breakdown: PricingBreakdown,
    *,
    shg_id: str,
    order_code: str,
    product_name: str,
    quantity: int,
    leader_language: str = "en",
    session_id: str = "pricing",
    force_draft: bool = False,
) -> dict:
    """Code computes exact cost numbers; LyzrPricingAnalystAgent writes context-aware message when configured."""
    from app.adapters.lyzr.client import PricingAnalysisSchema, call_lyzr_agent
    from app.config import get_settings

    deterministic = draft_buyer_counter_offer(
        breakdown,
        order_code=order_code,
        product_name=product_name,
        quantity=quantity,
        leader_language=leader_language,
        force_draft=force_draft,
    )

    if breakdown.recommendation == "INSUFFICIENT_DATA":
        return deterministic

    settings = get_settings()
    if not (settings.lyzr_api_key and settings.lyzr_pricing_agent_id):
        return deterministic

    try:
        prompt = (
            f"Analyze order {order_code} ({quantity} x {product_name}) using ONLY these exact figures "
            f"(do not invent or alter any rupee numbers): "
            f"verdict={breakdown.recommendation}, buyer_offer={breakdown.buyer_offer_per_unit_inr}, "
            f"minimum_viable_price={breakdown.minimum_viable_price_per_unit_inr}, "
            f"material={breakdown.material_cost_per_unit_inr}, labour={breakdown.labour_cost_per_unit_inr}, "
            f"overhead={breakdown.overhead_per_unit_inr}, margin={breakdown.margin_per_unit_inr}, "
            f"language={leader_language}, force_draft={force_draft}. "
            f"Return JSON matching PricingAnalysisSchema. "
            f"If verdict is ACCEPT and force_draft is false, set draft_message to null and explain the margin surplus in rationale. "
            f"If verdict is COUNTER_OFFER or DECLINE (or force_draft is true), write a polite, persuasive draft_message citing the exact cost breakdown."
        )
        res = call_lyzr_agent(
            agent_id=settings.lyzr_pricing_agent_id,
            user_id=shg_id,
            session_id=session_id,
            message=prompt,
        )
        parsed = PricingAnalysisSchema.model_validate_json(res.raw_response)
        # Code remains authoritative for the verdict & whether counter-offer is needed
        draft_msg = parsed.draft_message if (deterministic["needs_counter_offer"] or force_draft) else None
        return {
            **deterministic,
            "rationale": parsed.rationale,
            "draft_message": draft_msg,
            "engine": "lyzr_adk",
            "agent_name": "LyzrPricingAnalystAgent",
            "tokens": res.total_tokens,
            "trace_id": res.trace_id,
        }
    except Exception:
        return deterministic
