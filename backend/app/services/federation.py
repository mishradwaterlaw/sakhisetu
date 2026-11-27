"""Federation operational features (§17a pooled material buying, §17b neutral dispute escalation)."""

from sqlalchemy.orm import Session

from app.models.people import Federation, SHG
from app.models.pricing import PooledBuyAllocation
from app.models.quality import Contest
from app.services.pricing import compare_supplier_quotes
from app.services.state_machine import record_approval_and_transition

EVIDENCE_NOTES = {
    "17a_pooled_buying": (
        "Evidenced by two independent field-research citations: SHGs struggle to source small material lots "
        "at fair prices; federation-level pooled buying preserves separate group ledgers."
    ),
    "17b_dispute_escalation": (
        "Reasonable inference from the same field research (not independently field-confirmed): provides "
        "a neutral federation reviewer when a member contests a leader-raised quality flag."
    ),
}


def create_pooled_material_buy(
    db: Session,
    *,
    federation_id: str,
    material_id: str,
    shg_quantities: dict[str, float],  # {shg_id: qty}
) -> dict:
    """Combine material needs across SHGs under one federation while attributing cost back to each SHG (§17a)."""
    fed = db.get(Federation, federation_id)
    if not fed:
        raise ValueError("Federation not found")

    total_qty = sum(shg_quantities.values())
    if total_qty <= 0:
        raise ValueError("Total pooled quantity must be positive")

    quotes = compare_supplier_quotes(
        db, material_id=material_id, required_quantity=total_qty, federation_id=federation_id
    )
    if not quotes:
        # Fallback to any quote for this material if federation-specific quote absent
        quotes = compare_supplier_quotes(db, material_id=material_id, required_quantity=total_qty)
    if not quotes:
        raise ValueError("No supplier quotes available for this material")

    best = quotes[0]
    allocations = []
    for shg_id, qty in shg_quantities.items():
        shg = db.get(SHG, shg_id)
        if not shg or shg.federation_id != federation_id:
            raise ValueError(f"SHG {shg_id} does not belong to federation {federation_id}")
        alloc = PooledBuyAllocation(
            federation_id=federation_id,
            supplier_quote_id=best["supplier_quote_id"],
            shg_id=shg_id,
            allocated_quantity=qty,
            status="PROPOSED",
        )
        db.add(alloc)
        db.flush()
        allocations.append(
            {
                "allocation_id": alloc.id,
                "shg_id": shg_id,
                "shg_name": shg.name,
                "quantity": qty,
                "attributed_cost_inr": round(qty * best["unit_price_inr"], 2),
            }
        )

    return {
        "federation_id": federation_id,
        "selected_supplier": best,
        "total_pooled_quantity": total_qty,
        "per_shg_allocations": allocations,
        "evidence_note": EVIDENCE_NOTES["17a_pooled_buying"],
    }


def escalate_contest_to_federation(db: Session, *, contest_id: str) -> Contest:
    """Move an OPEN contest to FEDERATION_REVIEW (§17b)."""
    contest = db.get(Contest, contest_id)
    if not contest:
        raise ValueError("Contest not found")
    if contest.status != "OPEN":
        raise ValueError(f"Contest must be OPEN to escalate (currently {contest.status})")
    contest.status = "FEDERATION_REVIEW"
    db.flush()
    return contest


def resolve_federation_contest(
    db: Session,
    *,
    contest_id: str,
    federation_reviewer_id: str,
    upheld: bool,
    resolution_notes: str,
) -> Contest:
    """Neutral federation reviewer resolves a disputed contest (§17b)."""
    contest = db.get(Contest, contest_id)
    if not contest:
        raise ValueError("Contest not found")

    target_state = "RESOLVED_UPHELD" if upheld else "RESOLVED_DISMISSED"
    contest.resolution_notes = resolution_notes
    contest.resolved_by_id = federation_reviewer_id
    record_approval_and_transition(
        db,
        shg_id=contest.shg_id,
        entity_obj=contest,
        entity_type="contest",
        entity_id=contest.id,
        current_state=contest.status,
        target_state=target_state,
        actor_type="FEDERATION",
        actor_id=federation_reviewer_id,
        reason=resolution_notes,
    )
    return contest
