"""Strictly isolated Buyer API (§6, §12).

Queries ONLY `buyer_order_summary_v` (or explicit group-level aggregate columns).
Structurally incapable of exposing individual member identities, assignments, or compensation.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import ActorContext, require_buyer_actor
from app.database import get_db
from app.models.intake import Order
from app.models.pricing import QuoteCheck
from app.services.state_machine import StateTransitionError, get_transition_spec

router = APIRouter(prefix="/api/buyer", tags=["buyer"])


def _latest_pricing_for_order(db: Session, order_id: str) -> dict | None:
    qc = db.scalar(
        select(QuoteCheck).where(QuoteCheck.order_id == order_id).order_by(QuoteCheck.created_at.desc())
    )
    if not qc:
        return None
    return {
        "material_cost_inr": qc.material_cost_inr,
        "labour_cost_inr": qc.labour_cost_inr,
        "overhead_inr": qc.overhead_inr,
        "margin_inr": qc.margin_inr,
        "minimum_viable_price_per_unit_inr": qc.minimum_viable_price_per_unit_inr,
        "buyer_offer_per_unit_inr": qc.buyer_offer_per_unit_inr,
        "recommendation": qc.recommendation,
    }


@router.get("/orders")
def list_buyer_orders(
    actor: ActorContext = Depends(require_buyer_actor),
    db: Session = Depends(get_db),
):
    rows = db.execute(
        text(
            """
            SELECT
                order_id,
                order_code,
                shg_name,
                status,
                quantity,
                due_date,
                agreed_price_per_unit_inr,
                rubric_disagreement_risk,
                total_tasks,
                completed_tasks,
                group_qc_passed_units,
                group_qc_flagged_units,
                updated_at
            FROM buyer_order_summary_v
            WHERE buyer_party_id = :buyer_id
            ORDER BY updated_at DESC
            """
        ),
        {"buyer_id": actor.party_id},
    ).mappings().all()

    orders = []
    for r in rows:
        item = dict(r)
        item["pricing_breakdown"] = _latest_pricing_for_order(db, item["order_id"])
        orders.append(item)
    return {"buyer_party_id": actor.party_id, "orders": orders}


@router.get("/orders/{order_id}")
def get_buyer_order_detail(
    order_id: str,
    actor: ActorContext = Depends(require_buyer_actor),
    db: Session = Depends(get_db),
):
    row = db.execute(
        text(
            """
            SELECT
                order_id,
                order_code,
                shg_name,
                status,
                quantity,
                due_date,
                agreed_price_per_unit_inr,
                rubric_disagreement_risk,
                total_tasks,
                completed_tasks,
                group_qc_passed_units,
                group_qc_flagged_units,
                created_at,
                updated_at
            FROM buyer_order_summary_v
            WHERE order_id = :order_id AND buyer_party_id = :buyer_id
            """
        ),
        {"order_id": order_id, "buyer_id": actor.party_id},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Order not found for this buyer")
    item = dict(row)
    item["pricing_breakdown"] = _latest_pricing_for_order(db, item["order_id"])
    return item


class BuyerRevisedOfferBody(BaseModel):
    offered_price_per_unit_inr: float


@router.post("/orders/{order_id}/revised-offer")
def submit_buyer_revised_offer(
    order_id: str,
    body: BuyerRevisedOfferBody,
    actor: ActorContext = Depends(require_buyer_actor),
    db: Session = Depends(get_db),
):
    order = db.get(Order, order_id)
    if not order or order.buyer_party_id != actor.party_id:
        raise HTTPException(status_code=404, detail="Order not found for this buyer")
    if body.offered_price_per_unit_inr <= 0:
        raise HTTPException(status_code=400, detail="offered_price_per_unit_inr must be positive")
    try:
        get_transition_spec("order", order.status, "CONFIRMED")
    except StateTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    order.offered_price_per_unit_inr = body.offered_price_per_unit_inr
    order.status = "CONFIRMED"
    db.commit()
    return {
        "order_id": order.id,
        "status": order.status,
        "offered_price_per_unit_inr": order.offered_price_per_unit_inr,
    }
