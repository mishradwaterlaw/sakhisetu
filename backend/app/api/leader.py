"""Leader operations API: quarantine onboarding, order review, CP-SAT planner, QC, recovery, payout, usage (§4-§11)."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.governance import AgentEvent, Approval
from app.models.intake import ExtractedField, InboundMessage, Order
from app.models.money import PayoutBatch
from app.models.people import Member, Party, SHG
from app.models.planning import Blocker, RecoveryOption, Task, TaskAssignment
from app.models.quality import QCCheck, QualityRubric, ReviewRotation
from app.security import blind_index
from app.services.consent import ConsentRequiredError, export_bank_payout_csv, grant_consent
from app.services.payout import (
    approve_payout_by_committee,
    finalize_payout_if_window_elapsed,
    initiate_payout_batch,
)
from app.services.planner import MemberCapacity, TaskSpec, solve_allocation
from app.services.pricing import compute_order_pricing
from app.services.quality import agree_or_flag_rubric, record_human_qc_decision
from app.services.rotation import opt_out_and_reshuffle
from app.services.state_machine import StateTransitionError, record_approval_and_transition
from app.services.usage import get_shg_monthly_cost_summary

router = APIRouter(prefix="/api/leader", tags=["leader"])


class OnboardMemberFromQuarantineIn(BaseModel):
    leader_id: str
    name: str
    phone: str
    preferred_language: str = "kn"
    default_channel: str = "basic_phone_voice"
    skills: list[str] = ["stitching"]
    tools: list[str] = ["sewing_machine"]
    available_minutes_per_day: int = 240


class OnboardBuyerFromQuarantineIn(BaseModel):
    leader_id: str
    name: str
    phone: str
    preferred_language: str = "en"


class ConfirmOrderIn(BaseModel):
    leader_id: str
    agreed_price_per_unit_inr: float | None = None
    quantity: int | None = None
    reason: str | None = None


class ApprovePricingIn(BaseModel):
    leader_id: str
    agreed_price_per_unit_inr: float
    reason: str | None = None


class ApproveAllocationIn(BaseModel):
    leader_id: str
    overrides: list[dict] = []  # [{"assignment_id": ..., "new_member_id": ..., "reason": ...}]


class RubricIn(BaseModel):
    criteria: list[dict]
    reference_media_ids: list[str] = []
    leader_agreed: bool
    buyer_agreed: bool
    disagreement_notes: str | None = None


class QCRecordIn(BaseModel):
    assignment_id: str
    reviewer_member_id: str
    units_checked: int
    outcome: str  # PASS | FLAG | ESCALATE
    flag_reason: str | None = None
    submitted_media_id: str | None = None


class BlockerIn(BaseModel):
    assignment_id: str | None = None
    reported_by_member_id: str
    reason: str
    remaining_units: int


class ApproveRecoveryIn(BaseModel):
    leader_id: str
    recovery_option_id: str
    reason: str | None = None


class CommitteeApproveIn(BaseModel):
    reviewer_member_id: str
    contest_window_hours: int = 24
    reason: str | None = None


class OptOutIn(BaseModel):
    member_id: str


class GrantConsentIn(BaseModel):
    granted_by_member_id: str
    recipient_type: str = "BANK"
    recipient_id: str | None = None
    purpose: str = "Bank payout disbursement file export"


@router.get("/shgs/{shg_id}/dashboard")
def get_leader_dashboard(shg_id: str, db: Session = Depends(get_db)):
    shg = db.get(SHG, shg_id)
    if not shg:
        raise HTTPException(status_code=404, detail="SHG not found")

    orders = db.scalars(select(Order).where(Order.shg_id == shg_id).order_by(Order.created_at.desc())).all()
    quarantined = db.scalars(
        select(InboundMessage).where(InboundMessage.shg_id == shg_id, InboundMessage.is_quarantined.is_(True))
    ).all()
    unrouted = db.scalars(
        select(InboundMessage).where(InboundMessage.shg_id == shg_id, InboundMessage.intent == "UNROUTED")
    ).all()
    open_blockers = db.scalars(
        select(Blocker).join(Order, Order.id == Blocker.order_id).where(Order.shg_id == shg_id, Blocker.status == "OPEN")
    ).all()
    payouts = db.scalars(
        select(PayoutBatch).where(PayoutBatch.shg_id == shg_id).order_by(PayoutBatch.created_at.desc())
    ).all()
    members = db.scalars(select(Member).where(Member.shg_id == shg_id, Member.is_active.is_(True))).all()
    usage = get_shg_monthly_cost_summary(db, shg_id)

    # Priority 1 & 2 supporting data: buyers, materials, products, live member tracking, and impact metrics
    from app.models.catalogue import Material, Product
    from app.models.pricing import QuoteCheck

    buyers = db.scalars(select(Party).where(Party.party_type == "buyer")).all()
    materials = db.scalars(select(Material)).all()
    products = db.scalars(select(Product).where(Product.is_active.is_(True))).all()

    quote_checks = db.scalars(
        select(QuoteCheck).join(Order, Order.id == QuoteCheck.order_id).where(Order.shg_id == shg_id)
    ).all()
    underpricing_caught = 0.0
    for qc in quote_checks:
        if qc.buyer_offer_per_unit_inr is not None and qc.buyer_offer_per_unit_inr < qc.minimum_viable_price_per_unit_inr:
            qty = float((qc.breakdown_details or {}).get("quantity", 1))
            underpricing_caught += (qc.minimum_viable_price_per_unit_inr - qc.buyer_offer_per_unit_inr) * qty

    resolved_blockers = db.scalars(
        select(Blocker)
        .join(Order, Order.id == Blocker.order_id)
        .where(Order.shg_id == shg_id, Blocker.status.in_(["RECOVERY_APPROVED", "RESOLVED"]))
    ).all()

    open_blocker_member_ids = {b.reported_by_member_id for b in open_blockers}
    member_live_status = []
    for m in members:
        m_assignments = db.scalars(
            select(TaskAssignment).join(Order, Order.id == TaskAssignment.order_id).where(
                Order.shg_id == shg_id, TaskAssignment.member_id == m.id, TaskAssignment.assigned_units > 0
            )
        ).all()
        zero_unit_note = db.scalar(
            select(TaskAssignment.solver_explanation)
            .join(Order, Order.id == TaskAssignment.order_id)
            .where(
                Order.shg_id == shg_id,
                TaskAssignment.member_id == m.id,
                TaskAssignment.assigned_units == 0,
            )
            .order_by(TaskAssignment.created_at.desc())
        )
        total_assigned = sum(a.assigned_units for a in m_assignments)
        total_passed = sum(a.passed_units for a in m_assignments)
        if m.id in open_blocker_member_ids:
            live_state = "BLOCKED"
        elif total_assigned == 0:
            live_state = "NOT_STARTED"
        elif total_passed >= total_assigned:
            live_state = "SUBMITTED"
        else:
            live_state = "IN_PROGRESS"
        member_live_status.append(
            {
                "member_id": m.id,
                "name": m.name,
                "workload_preference": m.workload_preference,
                "live_status": live_state,
                "assigned_units": total_assigned,
                "passed_units": total_passed,
                "unhonored_preference_reason": zero_unit_note,
            }
        )

    return {
        "shg": {"id": shg.id, "name": shg.name, "village": shg.village, "language": shg.primary_language},
        "orders": [
            {
                "id": o.id,
                "order_code": o.order_code,
                "status": o.status,
                "quantity": o.quantity,
                "offered_price_per_unit_inr": o.offered_price_per_unit_inr,
                "agreed_price_per_unit_inr": o.agreed_price_per_unit_inr,
                "has_uncertain_fields": o.has_uncertain_fields,
                "rubric_disagreement_risk": o.rubric_disagreement_risk,
                "due_date": o.due_date.isoformat() if o.due_date else None,
            }
            for o in orders
        ],
        "quarantined_messages": [
            {"id": m.id, "channel": m.channel, "raw_text": m.raw_text, "created_at": m.created_at.isoformat()}
            for m in quarantined
        ],
        "unrouted_messages": [
            {"id": m.id, "channel": m.channel, "raw_text": m.raw_text, "created_at": m.created_at.isoformat()}
            for m in unrouted
        ],
        "open_blockers": [
            {"id": b.id, "order_id": b.order_id, "reason": b.reason, "remaining_units": b.remaining_units}
            for b in open_blockers
        ],
        "payout_batches": [
            {
                "id": p.id,
                "order_id": p.order_id,
                "total_amount_inr": p.total_amount_inr,
                "status": p.status,
                "rotation_id": p.rotation_id,
                "breakdown_snapshot": p.breakdown_snapshot,
                "contest_window_ends_at": p.contest_window_ends_at.isoformat() if p.contest_window_ends_at else None,
            }
            for p in payouts
        ],
        "members": [
            {
                "id": m.id,
                "name": m.name,
                "role": m.role,
                "preferred_language": m.preferred_language,
                "default_channel": m.default_channel,
                "skills": m.skills,
                "tools": m.tools,
                "available_minutes_per_day": m.available_minutes_per_day,
                "workload_preference": m.workload_preference,
            }
            for m in members
        ],
        "buyers": [{"id": b.id, "name": b.name} for b in buyers],
        "materials": [{"id": mat.id, "name": mat.name, "unit": mat.unit} for mat in materials],
        "products": [{"id": p.id, "name": p.name, "sku": p.sku} for p in products],
        "member_live_status": member_live_status,
        "impact_metrics": {
            "underpricing_caught_inr": round(underpricing_caught, 2),
            "recovery_actions_resolved": len(resolved_blockers),
        },
        "usage_summary": usage,
    }


@router.post("/quarantine/{message_id}/onboard-member")
def onboard_member_from_quarantine(
    message_id: str, body: OnboardMemberFromQuarantineIn, db: Session = Depends(get_db)
):
    msg = db.get(InboundMessage, message_id)
    if not msg or not msg.is_quarantined:
        raise HTTPException(status_code=404, detail="Quarantined message not found")

    member = Member(
        shg_id=msg.shg_id,
        name=body.name,
        role="member",
        phone_enc=body.phone,
        phone_hash=blind_index(body.phone),
        preferred_language=body.preferred_language,
        default_channel=body.default_channel,
        skills=body.skills,
        tools=body.tools,
        available_minutes_per_day=body.available_minutes_per_day,
    )
    db.add(member)
    db.flush()

    msg.sender_member_id = member.id
    msg.is_quarantined = False
    msg.intent = "PENDING"
    db.commit()
    return {"member_id": member.id, "message_id": msg.id, "status": "ONBOARDED_AND_UNQUARANTINED"}


@router.post("/quarantine/{message_id}/onboard-buyer")
def onboard_buyer_from_quarantine(
    message_id: str, body: OnboardBuyerFromQuarantineIn, db: Session = Depends(get_db)
):
    msg = db.get(InboundMessage, message_id)
    if not msg or not msg.is_quarantined:
        raise HTTPException(status_code=404, detail="Quarantined message not found")

    buyer = Party(
        party_type="buyer",
        name=body.name,
        phone_enc=body.phone,
        phone_hash=blind_index(body.phone),
        preferred_language=body.preferred_language,
    )
    db.add(buyer)
    db.flush()

    msg.sender_party_id = buyer.id
    msg.is_quarantined = False
    msg.intent = "PENDING"
    db.commit()
    return {"buyer_party_id": buyer.id, "message_id": msg.id, "status": "ONBOARDED_AND_UNQUARANTINED"}


@router.get("/orders/{order_id}")
def get_order_review_detail(order_id: str, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    source_msg = db.get(InboundMessage, order.source_message_id) if order.source_message_id else None
    fields = db.scalars(select(ExtractedField).where(ExtractedField.order_id == order_id)).all()
    tasks = db.scalars(select(Task).where(Task.order_id == order_id)).all()
    assignments = db.scalars(select(TaskAssignment).where(TaskAssignment.order_id == order_id)).all()
    rubric = db.scalar(select(QualityRubric).where(QualityRubric.order_id == order_id))
    qc_checks = db.scalars(select(QCCheck).where(QCCheck.order_id == order_id)).all()

    return {
        "order": {
            "id": order.id,
            "order_code": order.order_code,
            "status": order.status,
            "quantity": order.quantity,
            "offered_price_per_unit_inr": order.offered_price_per_unit_inr,
            "agreed_price_per_unit_inr": order.agreed_price_per_unit_inr,
            "due_date": order.due_date.isoformat() if order.due_date else None,
            "has_uncertain_fields": order.has_uncertain_fields,
            "rubric_disagreement_risk": order.rubric_disagreement_risk,
        },
        "raw_input": source_msg.raw_text if source_msg else None,
        "extracted_fields": [
            {
                "id": f.id,
                "field_name": f.field_name,
                "extracted_value": f.extracted_value,
                "confidence": f.confidence,
                "source_span": f.source_span,
                "is_uncertain": f.is_uncertain,
            }
            for f in fields
        ],
        "tasks": [
            {
                "id": t.id,
                "step_name": t.step_name,
                "required_skill": t.required_skill,
                "total_units": t.total_units,
                "minutes_per_unit": t.minutes_per_unit,
                "piece_rate_inr": t.piece_rate_inr,
            }
            for t in tasks
        ],
        "assignments": [
            {
                "id": a.id,
                "task_id": a.task_id,
                "member_id": a.member_id,
                "member_name": (db.get(Member, a.member_id).name if db.get(Member, a.member_id) else ""),
                "assigned_units": a.assigned_units,
                "completed_units": a.completed_units,
                "passed_units": a.passed_units,
                "estimated_minutes": a.estimated_minutes,
                "solver_explanation": a.solver_explanation,
                "solver_metadata": a.solver_metadata,
                "is_leader_override": a.is_leader_override,
                "status": a.status,
            }
            for a in assignments
        ],
        "rubric": (
            {
                "status": rubric.status,
                "criteria": rubric.criteria,
                "leader_agreed": rubric.leader_agreed,
                "buyer_agreed": rubric.buyer_agreed,
                "disagreement_notes": rubric.disagreement_notes,
            }
            if rubric
            else None
        ),
        "qc_checks": [
            {
                "id": q.id,
                "member_id": q.member_id,
                "units_checked": q.units_checked,
                "outcome": q.outcome,
                "flag_reason": q.flag_reason,
                "rotation_id": q.rotation_id,
            }
            for q in qc_checks
        ],
    }


@router.post("/orders/{order_id}/confirm")
def confirm_order(order_id: str, body: ConfirmOrderIn, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if body.quantity is not None:
        order.quantity = body.quantity
    if body.agreed_price_per_unit_inr is not None:
        order.agreed_price_per_unit_inr = body.agreed_price_per_unit_inr

    try:
        approval = record_approval_and_transition(
            db,
            shg_id=order.shg_id,
            entity_obj=order,
            entity_type="order",
            entity_id=order.id,
            current_state=order.status,
            target_state="CONFIRMED",
            actor_type="LEADER",
            actor_id=body.leader_id,
            reason=body.reason or "Leader confirmed draft order",
        )
        db.commit()
        return {"order_id": order.id, "status": order.status, "approval_id": approval.id}
    except StateTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/{order_id}/pricing")
def evaluate_pricing(order_id: str, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order or not order.product_id:
        raise HTTPException(status_code=404, detail="Order or product not found")

    breakdown = compute_order_pricing(
        db,
        order_id=order.id,
        product_id=order.product_id,
        quantity=order.quantity,
        buyer_offer_per_unit_inr=order.offered_price_per_unit_inr,
    )
    db.commit()
    return breakdown.__dict__


@router.post("/orders/{order_id}/approve-pricing")
def approve_pricing(order_id: str, body: ApprovePricingIn, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    order.agreed_price_per_unit_inr = body.agreed_price_per_unit_inr
    try:
        approval = record_approval_and_transition(
            db,
            shg_id=order.shg_id,
            entity_obj=order,
            entity_type="order",
            entity_id=order.id,
            current_state=order.status,
            target_state="PRICING_APPROVED",
            actor_type="LEADER",
            actor_id=body.leader_id,
            reason=body.reason or f"Agreed price ₹{body.agreed_price_per_unit_inr:.2f}/unit",
        )
        db.commit()
        return {"order_id": order.id, "status": order.status, "approval_id": approval.id}
    except StateTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/{order_id}/plan")
def run_cpsat_planner(order_id: str, horizon_days: int = 5, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    tasks = db.scalars(select(Task).where(Task.order_id == order_id)).all()
    members = db.scalars(select(Member).where(Member.shg_id == order.shg_id, Member.is_active.is_(True))).all()

    task_specs = [
        TaskSpec(
            task_id=t.id,
            step_name=t.step_name,
            required_skill=t.required_skill,
            required_tools=list(t.required_tools or []),
            total_units=t.total_units,
            minutes_per_unit=t.minutes_per_unit,
        )
        for t in tasks
    ]
    member_caps = [
        MemberCapacity(
            member_id=m.id,
            name=m.name,
            skills=list(m.skills or []),
            tools=list(m.tools or []),
            available_minutes=m.available_minutes_per_day,
            workload_preference=m.workload_preference,
            consecutive_max_share_cycles=m.consecutive_max_share_cycles,
        )
        for m in members
    ]

    result = solve_allocation(task_specs, member_caps, horizon_days=horizon_days)
    if not result.feasible:
        raise HTTPException(status_code=422, detail=result.infeasibility_reason)

    # Replace any prior PROPOSED assignments
    existing = db.scalars(select(TaskAssignment).where(TaskAssignment.order_id == order_id)).all()
    for e in existing:
        db.delete(e)

    created = []
    for a in result.assignments:
        ta = TaskAssignment(
            order_id=order_id,
            task_id=a.task_id,
            member_id=a.member_id,
            assigned_units=a.assigned_units,
            estimated_minutes=a.estimated_minutes,
            solver_explanation=a.explanation,
            solver_metadata=a.solver_metadata,
            status="PROPOSED",
        )
        db.add(ta)
        created.append(ta)

    if order.status == "PRICING_APPROVED":
        order.status = "ALLOCATION_PROPOSED"
    db.commit()
    return {
        "order_id": order.id,
        "status": order.status,
        "fairness_max_utilization_pct": result.fairness_max_utilization_pct,
        "fairness_warnings": result.fairness_warnings,
        "assignments": [
            {
                "id": ta.id,
                "task_id": ta.task_id,
                "member_id": ta.member_id,
                "assigned_units": ta.assigned_units,
                "explanation": ta.solver_explanation,
            }
            for ta in created
        ],
    }


@router.post("/orders/{order_id}/approve-allocation")
def approve_allocation(order_id: str, body: ApproveAllocationIn, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    for ov in body.overrides:
        ta = db.get(TaskAssignment, ov["assignment_id"])
        if ta and ta.order_id == order_id:
            ta.member_id = ov["new_member_id"]
            ta.is_leader_override = True
            ta.override_reason = ov.get("reason", "Leader override")

    try:
        approval = record_approval_and_transition(
            db,
            shg_id=order.shg_id,
            entity_obj=order,
            entity_type="order",
            entity_id=order.id,
            current_state=order.status,
            target_state="ALLOCATION_APPROVED",
            actor_type="LEADER",
            actor_id=body.leader_id,
            reason=f"Allocation approved ({len(body.overrides)} overrides)",
        )
        assignments = db.scalars(select(TaskAssignment).where(TaskAssignment.order_id == order_id)).all()
        for a in assignments:
            a.status = "APPROVED"
        db.commit()
        return {"order_id": order.id, "status": order.status, "approval_id": approval.id}
    except StateTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/orders/{order_id}/rubric")
def update_rubric(order_id: str, body: RubricIn, db: Session = Depends(get_db)):
    rubric = agree_or_flag_rubric(
        db,
        order_id=order_id,
        criteria=body.criteria,
        reference_media_ids=body.reference_media_ids,
        leader_agreed=body.leader_agreed,
        buyer_agreed=body.buyer_agreed,
        disagreement_notes=body.disagreement_notes,
    )
    db.commit()
    return {"rubric_id": rubric.id, "status": rubric.status}


@router.post("/orders/{order_id}/qc")
def record_qc(order_id: str, body: QCRecordIn, db: Session = Depends(get_db)):
    qc = record_human_qc_decision(
        db,
        order_id=order_id,
        assignment_id=body.assignment_id,
        submitted_media_id=body.submitted_media_id,
        reviewer_member_id=body.reviewer_member_id,
        units_checked=body.units_checked,
        outcome=body.outcome,
        flag_reason=body.flag_reason,
    )
    db.commit()
    return {"qc_check_id": qc.id, "outcome": qc.outcome, "rotation_id": qc.rotation_id}


@router.post("/orders/{order_id}/blockers")
def report_blocker(order_id: str, body: BlockerIn, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    blocker = Blocker(
        order_id=order_id,
        assignment_id=body.assignment_id,
        reported_by_member_id=body.reported_by_member_id,
        reason=body.reason,
        remaining_units=body.remaining_units,
        status="OPEN",
    )
    db.add(blocker)
    db.flush()

    opt1 = RecoveryOption(
        blocker_id=blocker.id,
        option_type="REASSIGN_UNITS",
        summary=f"Reassign {body.remaining_units} remaining units to members with free capacity",
        proposed_payload={"remaining_units": body.remaining_units},
    )
    opt2 = RecoveryOption(
        blocker_id=blocker.id,
        option_type="EXTEND_DEADLINE",
        summary="Request 48-hour deadline extension from buyer",
        proposed_payload={"extension_hours": 48},
    )
    db.add_all([opt1, opt2])
    db.commit()
    return {
        "blocker_id": blocker.id,
        "options": [
            {"id": opt1.id, "type": opt1.option_type, "summary": opt1.summary},
            {"id": opt2.id, "type": opt2.option_type, "summary": opt2.summary},
        ],
    }


@router.post("/blockers/{blocker_id}/approve-recovery")
def approve_recovery(blocker_id: str, body: ApproveRecoveryIn, db: Session = Depends(get_db)):
    blocker = db.get(Blocker, blocker_id)
    if not blocker:
        raise HTTPException(status_code=404, detail="Blocker not found")
    order = db.get(Order, blocker.order_id)
    opt = db.get(RecoveryOption, body.recovery_option_id)
    if not opt or opt.blocker_id != blocker_id:
        raise HTTPException(status_code=404, detail="Recovery option not found")

    opt.is_selected = True
    approval = record_approval_and_transition(
        db,
        shg_id=order.shg_id,
        entity_obj=blocker,
        entity_type="blocker",
        entity_id=blocker.id,
        current_state=blocker.status,
        target_state="RECOVERY_APPROVED",
        actor_type="LEADER",
        actor_id=body.leader_id,
        reason=body.reason or f"Selected {opt.option_type}",
    )
    db.commit()
    return {"blocker_id": blocker.id, "status": blocker.status, "approval_id": approval.id}


@router.post("/orders/{order_id}/payouts/initiate")
def initiate_payout(order_id: str, db: Session = Depends(get_db)):
    try:
        batch = initiate_payout_batch(db, order_id=order_id)
        db.commit()
        rotation = db.get(ReviewRotation, batch.rotation_id)
        return {
            "batch_id": batch.id,
            "status": batch.status,
            "total_amount_inr": batch.total_amount_inr,
            "selected_committee_member_ids": rotation.selected_member_ids if rotation else [],
            "selection_seed": rotation.selection_seed if rotation else None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/payouts/{batch_id}/committee-approve")
def committee_approve_payout(batch_id: str, body: CommitteeApproveIn, db: Session = Depends(get_db)):
    try:
        batch = approve_payout_by_committee(
            db,
            batch_id=batch_id,
            reviewer_member_id=body.reviewer_member_id,
            contest_window_hours=body.contest_window_hours,
            reason=body.reason,
        )
        db.commit()
        return {
            "batch_id": batch.id,
            "status": batch.status,
            "contest_window_ends_at": batch.contest_window_ends_at.isoformat() if batch.contest_window_ends_at else None,
        }
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ValueError, StateTransitionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/rotations/{rotation_id}/opt-out")
def rotation_opt_out(rotation_id: str, body: OptOutIn, db: Session = Depends(get_db)):
    rot = opt_out_and_reshuffle(db, rotation_id=rotation_id, member_id=body.member_id)
    db.commit()
    return {
        "rotation_id": rot.id,
        "selected_member_ids": rot.selected_member_ids,
        "opted_out_member_ids": rot.opted_out_member_ids,
        "selection_seed": rot.selection_seed,
    }


@router.post("/payouts/{batch_id}/evaluate-window")
def evaluate_payout_window(batch_id: str, db: Session = Depends(get_db)):
    batch = finalize_payout_if_window_elapsed(db, batch_id=batch_id)
    db.commit()
    return {"batch_id": batch.id, "status": batch.status}


@router.post("/shgs/{shg_id}/consent")
def grant_shg_consent(shg_id: str, body: GrantConsentIn, db: Session = Depends(get_db)):
    ev = grant_consent(
        db,
        shg_id=shg_id,
        granted_by_member_id=body.granted_by_member_id,
        recipient_type=body.recipient_type,
        recipient_id=body.recipient_id,
        purpose=body.purpose,
        scope={"shg_id": shg_id},
    )
    db.commit()
    return {"consent_event_id": ev.id}


@router.get("/payouts/{batch_id}/export-bank-csv")
def export_bank_csv(batch_id: str, consent_event_id: str | None = None, db: Session = Depends(get_db)):
    try:
        csv_text = export_bank_payout_csv(db, batch_id=batch_id, consent_event_id=consent_event_id)
        return Response(content=csv_text, media_type="text/csv")
    except ConsentRequiredError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.get("/traces/{trace_id}")
def get_agent_trace(trace_id: str, db: Session = Depends(get_db)):
    events = db.scalars(
        select(AgentEvent).where(AgentEvent.trace_id == trace_id).order_by(AgentEvent.created_at.asc())
    ).all()
    return {
        "trace_id": trace_id,
        "events": [
            {
                "step_name": e.step_name,
                "agent_name": e.agent_name,
                "confidence": e.confidence,
                "latency_ms": e.latency_ms,
                "status": e.status,
                "input_summary": e.input_summary,
                "output_summary": e.output_summary,
            }
            for e in events
        ],
    }


class ManualOrderIn(BaseModel):
    shg_id: str
    leader_id: str
    buyer_party_id: str
    product_name: str
    quantity: int
    offered_price_per_unit_inr: float
    due_in_days: int = 10
    notes: str = ""


@router.post("/orders/manual")
def create_manual_leader_order(body: ManualOrderIn, db: Session = Depends(get_db)):
    """§21: Direct manual order-entry by leader. Converges into the exact same InboundMessage -> DRAFT pipeline."""
    from app.adapters.channels.base import NormalizedInbound
    from app.adapters.lyzr.orchestrator import run_intake_pipeline

    leader = db.get(Member, body.leader_id)
    if not leader:
        raise HTTPException(status_code=404, detail="Leader not found")

    synthetic_text = (
        f"New order: {body.quantity} {body.product_name} at Rs {body.offered_price_per_unit_inr} "
        f"in {body.due_in_days} days. {body.notes}"
    ).strip()
    inbound = NormalizedInbound(
        channel="leader_manual",
        provider_message_id=None,
        sender_phone=leader.phone_enc,
        raw_text=synthetic_text,
        button_payload_id="NEW_ORDER",
        operator_id=leader.id,
        member_consented=True,
        raw_payload=body.model_dump(),
    )
    outcome = run_intake_pipeline(
        db, shg_id=body.shg_id, inbound=inbound, buyer_party_id_hint=body.buyer_party_id
    )
    db.commit()
    return {
        "trace_id": outcome.trace_id,
        "order_id": outcome.order_id,
        "status": outcome.status,
    }


@router.post("/orders/{order_id}/counter-offer-draft")
def get_buyer_counter_offer_draft(order_id: str, db: Session = Depends(get_db)):
    """§15: Draft (never auto-send) buyer counter-offer grounded in real MVP cost breakdown."""
    from app.models.catalogue import Product
    from app.services.pricing import draft_buyer_counter_offer

    order = db.get(Order, order_id)
    if not order or not order.product_id:
        raise HTTPException(status_code=404, detail="Order or product not found")
    product = db.get(Product, order.product_id)
    shg = db.get(SHG, order.shg_id)
    breakdown = compute_order_pricing(
        db,
        order_id=order.id,
        product_id=order.product_id,
        quantity=order.quantity,
        buyer_offer_per_unit_inr=order.offered_price_per_unit_inr,
        persist=False,
    )
    return draft_buyer_counter_offer(
        breakdown,
        order_code=order.order_code,
        product_name=product.name if product else "Product",
        quantity=order.quantity,
        leader_language=shg.primary_language if shg else "en",
    )


class SupplierQuoteIn(BaseModel):
    federation_id: str | None = None
    shg_id: str | None = None
    supplier_party_id: str
    material_id: str
    unit_price_inr: float
    min_order_qty: int = 1
    delivery_days: int = 5
    notes: str | None = None


@router.post("/supplier-quotes")
def add_supplier_quote(body: SupplierQuoteIn, db: Session = Depends(get_db)):
    from app.models.pricing import SupplierQuote

    q = SupplierQuote(**body.model_dump())
    db.add(q)
    db.commit()
    return {"supplier_quote_id": q.id}


@router.get("/supplier-quotes/compare")
def compare_quotes(material_id: str, required_quantity: float, federation_id: str | None = None, db: Session = Depends(get_db)):
    from app.services.pricing import compare_supplier_quotes

    return {
        "material_id": material_id,
        "required_quantity": required_quantity,
        "quotes": compare_supplier_quotes(
            db, material_id=material_id, required_quantity=required_quantity, federation_id=federation_id
        ),
    }


@router.get("/shgs/{shg_id}/bank-summary")
def preview_bank_summary(shg_id: str, months: int = 6, db: Session = Depends(get_db)):
    """§16: Preview group-level bank creditworthiness summary (no external share)."""
    from app.services.consent import generate_bank_creditworthiness_summary

    return generate_bank_creditworthiness_summary(db, shg_id=shg_id, months=months)


@router.post("/shgs/{shg_id}/bank-summary/share")
def share_bank_summary(shg_id: str, consent_event_id: str | None = None, months: int = 6, db: Session = Depends(get_db)):
    """§16: Share bank-ready summary externally (requires group-approved ConsentEvent)."""
    from app.services.consent import share_bank_summary_with_group_consent

    try:
        return share_bank_summary_with_group_consent(
            db, shg_id=shg_id, consent_event_id=consent_event_id, months=months
        )
    except ConsentRequiredError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


class PooledBuyIn(BaseModel):
    material_id: str
    shg_quantities: dict[str, float]


@router.post("/federations/{federation_id}/pooled-buy")
def federation_pooled_buy(federation_id: str, body: PooledBuyIn, db: Session = Depends(get_db)):
    """§17a: Federation pooled material buying across SHGs (separate group ledgers preserved)."""
    from app.services.federation import create_pooled_material_buy

    res = create_pooled_material_buy(
        db, federation_id=federation_id, material_id=body.material_id, shg_quantities=body.shg_quantities
    )
    db.commit()
    return res


@router.post("/contests/{contest_id}/escalate-federation")
def escalate_contest(contest_id: str, db: Session = Depends(get_db)):
    from app.services.federation import escalate_contest_to_federation

    c = escalate_contest_to_federation(db, contest_id=contest_id)
    db.commit()
    return {"contest_id": c.id, "status": c.status}


class ResolveFederationContestIn(BaseModel):
    federation_reviewer_id: str
    upheld: bool
    resolution_notes: str


@router.post("/contests/{contest_id}/resolve-federation")
def resolve_contest_federation(contest_id: str, body: ResolveFederationContestIn, db: Session = Depends(get_db)):
    from app.services.federation import resolve_federation_contest

    c = resolve_federation_contest(
        db,
        contest_id=contest_id,
        federation_reviewer_id=body.federation_reviewer_id,
        upheld=body.upheld,
        resolution_notes=body.resolution_notes,
    )
    db.commit()
    return {"contest_id": c.id, "status": c.status}


class WorkloadPreferenceIn(BaseModel):
    workload_preference: str  # standard | more | less


@router.put("/members/{member_id}/workload-preference")
def set_member_workload_preference(member_id: str, body: WorkloadPreferenceIn, db: Session = Depends(get_db)):
    if body.workload_preference not in ("standard", "more", "less"):
        raise HTTPException(status_code=400, detail="workload_preference must be standard, more, or less")
    m = db.get(Member, member_id)
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    m.workload_preference = body.workload_preference
    db.commit()
    return {"member_id": m.id, "workload_preference": m.workload_preference}
