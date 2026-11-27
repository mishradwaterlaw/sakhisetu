"""Strictly isolated Buyer API (§6, §12).

Queries ONLY `buyer_order_summary_v` (or explicit group-level aggregate columns).
Structurally incapable of exposing individual member identities, assignments, or compensation.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import ActorContext, require_buyer_actor
from app.database import get_db

router = APIRouter(prefix="/api/buyer", tags=["buyer"])


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

    return {"buyer_party_id": actor.party_id, "orders": [dict(r) for r in rows]}


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
    return dict(row)
