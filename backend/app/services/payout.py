"""Payout service (§7): ledger computation, rotating committee, group-first broadcast, contest window, replayable read-back."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.governance import CommsLog
from app.models.intake import Order
from app.models.money import LedgerAccount, LedgerEntry, PayoutBatch
from app.models.people import Member
from app.models.planning import Task, TaskAssignment
from app.models.quality import Contest
from app.services.rotation import create_review_rotation
from app.services.state_machine import evaluate_payout_contest_window, record_approval_and_transition


def _get_or_create_member_account(db: Session, shg_id: str, member_id: str) -> LedgerAccount:
    acct = db.scalar(select(LedgerAccount).where(LedgerAccount.member_id == member_id))
    if not acct:
        acct = LedgerAccount(shg_id=shg_id, owner_type="MEMBER", member_id=member_id, balance_inr=0.0)
        db.add(acct)
        db.flush()
    return acct


def initiate_payout_batch(
    db: Session,
    *,
    order_id: str,
    committee_size: int = 2,
) -> PayoutBatch:
    """Compute per-member payout from passed units, assign rotating committee, and notify ALL members."""
    order = db.get(Order, order_id)
    if not order:
        raise ValueError(f"Order {order_id} not found")

    assignments = db.scalars(select(TaskAssignment).where(TaskAssignment.order_id == order_id)).all()
    if not assignments:
        raise ValueError("No task assignments found for order")

    by_member: dict[str, dict] = {}
    total_inr = 0.0
    for a in assignments:
        task = db.get(Task, a.task_id)
        member = db.get(Member, a.member_id)
        if not task or not member:
            continue
        units = a.passed_units if a.passed_units > 0 else a.completed_units
        amount = round(units * task.piece_rate_inr, 2)
        if amount <= 0:
            continue
        total_inr += amount
        entry = by_member.setdefault(
            member.id,
            {"member_id": member.id, "member_name": member.name, "units": 0, "amount_inr": 0.0},
        )
        entry["units"] += units
        entry["amount_inr"] = round(entry["amount_inr"] + amount, 2)

    if total_inr <= 0:
        raise ValueError("No passed/completed units with positive payout amount")

    batch = PayoutBatch(
        shg_id=order.shg_id,
        order_id=order_id,
        total_amount_inr=round(total_inr, 2),
        status="PAYOUT_PENDING",
        breakdown_snapshot=list(by_member.values()),
    )
    db.add(batch)
    db.flush()

    rotation = create_review_rotation(
        db,
        shg_id=order.shg_id,
        purpose="PAYOUT",
        target_entity_type="payout_batch",
        target_entity_id=batch.id,
        committee_size=committee_size,
    )
    batch.rotation_id = rotation.id

    # Create ledger accrual entries
    for item in by_member.values():
        acct = _get_or_create_member_account(db, order.shg_id, item["member_id"])
        db.add(
            LedgerEntry(
                payout_batch_id=batch.id,
                account_id=acct.id,
                member_id=item["member_id"],
                amount_inr=item["amount_inr"],
                entry_type="EARNINGS_ACCRUAL",
                description=f"Order {order.order_code}: {item['units']} passed units",
                is_disbursed=False,
            )
        )

    # Notify EVERY member (not just the reviewing sub-group) that payout is pending group review (§7)
    all_members = db.scalars(
        select(Member).where(Member.shg_id == order.shg_id, Member.is_active.is_(True))
    ).all()
    selected_set = set(rotation.selected_member_ids or [])
    for m in all_members:
        is_reviewer = m.id in selected_set
        db.add(
            CommsLog(
                shg_id=order.shg_id,
                recipient_member_id=m.id,
                channel=m.default_channel,
                language=m.preferred_language,
                message_category="GROUP_PAYOUT_NOTICE",
                fact_text=f"Order {order.order_code} payout of ₹{batch.total_amount_inr:.2f} is pending group review.",
                action_text=(
                    "You are on the rotating review committee for this cycle."
                    if is_reviewer
                    else "The rotating member committee is reviewing the group split."
                ),
                request_text=(
                    "Review and confirm or flag any concern."
                    if is_reviewer
                    else "No action needed now; you will receive the group approval notice before disbursement."
                ),
                is_replayable=True,
            )
        )

    batch.group_notice_sent = True
    db.flush()
    return batch


def approve_payout_by_committee(
    db: Session,
    *,
    batch_id: str,
    reviewer_member_id: str,
    decision: str = "APPROVED",  # APPROVED | REJECTED
    contest_window_hours: int = 24,
    reason: str | None = None,
) -> dict:
    """Record an individual committee member's response (one Approval row per responder).

    Quorum rule (explicitly hard-coded):
    - Requires strict majority of the selected committee: `(len(selected) // 2) + 1`
      (e.g., 2 of 2 for a 2-member committee, 2 of 3 for a 3-member committee).
    - If any committee member responds REJECTED, writes her individual Approval(REJECTED)
      row and halts the batch into DISPUTED immediately.
    - Only transitions PAYOUT_PENDING -> PAYOUT_APPROVED and broadcasts group approval +
      earnings read-backs once distinct APPROVED rows >= required_quorum.
    """
    from app.models.governance import Approval
    from app.models.quality import ReviewRotation

    if decision not in ("APPROVED", "REJECTED"):
        raise ValueError("decision must be APPROVED or REJECTED")

    batch = db.get(PayoutBatch, batch_id)
    if not batch:
        raise ValueError("Payout batch not found")
    if batch.status != "PAYOUT_PENDING":
        raise ValueError(f"Payout batch is in status {batch.status}, expected PAYOUT_PENDING")

    rotation = db.get(ReviewRotation, batch.rotation_id) if batch.rotation_id else None
    selected_ids = list(rotation.selected_member_ids or []) if rotation else []
    if not rotation or reviewer_member_id not in selected_ids:
        raise PermissionError("Only a selected rotating committee member can review this payout")

    existing_vote = db.scalar(
        select(Approval).where(
            Approval.entity_type == "payout_batch",
            Approval.entity_id == batch.id,
            Approval.transition_name == "PAYOUT_PENDING->PAYOUT_APPROVED",
            Approval.actor_type == "REVIEW_COMMITTEE",
            Approval.actor_id == reviewer_member_id,
        )
    )
    if existing_vote:
        raise ValueError(f"Committee member {reviewer_member_id} has already recorded a response")

    required_quorum = (len(selected_ids) // 2) + 1

    if decision == "REJECTED":
        db.add(
            Approval(
                shg_id=batch.shg_id,
                entity_type="payout_batch",
                entity_id=batch.id,
                transition_name="PAYOUT_PENDING->PAYOUT_APPROVED",
                actor_type="REVIEW_COMMITTEE",
                actor_id=reviewer_member_id,
                decision="REJECTED",
                reason=reason or "Flagged by rotating committee member",
                evidence={"rotation_id": rotation.id, "seed": rotation.selection_seed},
            )
        )
        batch.status = "DISPUTED"
        db.flush()
        return {
            "batch": batch,
            "required_quorum": required_quorum,
            "approved_member_ids": [],
            "pending_member_ids": [m for m in selected_ids if m != reviewer_member_id],
        }

    # Record individual committee member approval row
    individual_approval = Approval(
        shg_id=batch.shg_id,
        entity_type="payout_batch",
        entity_id=batch.id,
        transition_name="PAYOUT_PENDING->PAYOUT_APPROVED",
        actor_type="REVIEW_COMMITTEE",
        actor_id=reviewer_member_id,
        decision="APPROVED",
        reason=reason or "Approved by rotating committee member",
        evidence={"rotation_id": rotation.id, "seed": rotation.selection_seed},
    )
    db.add(individual_approval)
    db.flush()

    approved_rows = db.scalars(
        select(Approval).where(
            Approval.entity_type == "payout_batch",
            Approval.entity_id == batch.id,
            Approval.transition_name == "PAYOUT_PENDING->PAYOUT_APPROVED",
            Approval.actor_type == "REVIEW_COMMITTEE",
            Approval.decision == "APPROVED",
        )
    ).all()
    approved_member_ids = [r.actor_id for r in approved_rows]
    pending_member_ids = [m for m in selected_ids if m not in approved_member_ids]

    if len(approved_member_ids) < required_quorum:
        # Quorum not yet met: remain in PAYOUT_PENDING with pending members visibly distinct
        db.flush()
        return {
            "batch": batch,
            "required_quorum": required_quorum,
            "approved_member_ids": approved_member_ids,
            "pending_member_ids": pending_member_ids,
        }

    now = datetime.now(timezone.utc)
    batch.status = "PAYOUT_APPROVED"
    batch.approved_at = now
    batch.contest_window_ends_at = now + timedelta(hours=contest_window_hours)

    all_members = db.scalars(
        select(Member).where(Member.shg_id == batch.shg_id, Member.is_active.is_(True))
    ).all()
    order = db.get(Order, batch.order_id)
    order_code = order.order_code if order else batch.order_id

    # 1. Group-level approval broadcast FIRST (§7)
    for m in all_members:
        db.add(
            CommsLog(
                shg_id=batch.shg_id,
                recipient_member_id=m.id,
                channel=m.default_channel,
                language=m.preferred_language,
                message_category="GROUP_APPROVAL_BROADCAST",
                fact_text=f"GROUP DECISION: Payout of ₹{batch.total_amount_inr:.2f} for {order_code} was approved by the rotating committee ({len(approved_member_ids)}/{len(selected_ids)}).",
                action_text=f"Contest window is open for {contest_window_hours}h for any member.",
                request_text="Reply or press 9 to raise an objection if your count looks wrong.",
                is_replayable=True,
            )
        )
    batch.group_approval_broadcast_sent = True

    # 2. Individual replayable earnings read-backs AFTER group broadcast
    for item in batch.breakdown_snapshot or []:
        m = db.get(Member, item["member_id"])
        if not m:
            continue
        db.add(
            CommsLog(
                shg_id=batch.shg_id,
                recipient_member_id=m.id,
                channel=m.default_channel,
                language=m.preferred_language,
                message_category="EARNINGS_READBACK",
                fact_text=f"Your earnings for {order_code}: {item['units']} passed units = ₹{item['amount_inr']:.2f}.",
                action_text="This record is saved and replayable anytime.",
                request_text="Confirm if accurate, or raise a contest before the window closes.",
                is_replayable=True,
            )
        )

    db.flush()
    return {
        "batch": batch,
        "required_quorum": required_quorum,
        "approved_member_ids": approved_member_ids,
        "pending_member_ids": pending_member_ids,
    }


def raise_payout_contest(
    db: Session,
    *,
    batch_id: str,
    member_id: str,
    reason: str,
) -> Contest:
    """Any member can contest an approved payout during the contest window, halting disbursement into DISPUTED."""
    batch = db.get(PayoutBatch, batch_id)
    if not batch:
        raise ValueError("Payout batch not found")
    if batch.status != "PAYOUT_APPROVED":
        raise ValueError(f"Cannot contest payout in status {batch.status}")

    contest = Contest(
        shg_id=batch.shg_id,
        target_type="PAYOUT_BATCH",
        target_id=batch.id,
        raised_by_member_id=member_id,
        reason=reason,
        status="OPEN",
    )
    db.add(contest)
    batch.status = "DISPUTED"
    db.flush()
    return contest


def finalize_payout_if_window_elapsed(
    db: Session,
    *,
    batch_id: str,
    now: datetime | None = None,
) -> PayoutBatch:
    batch = db.get(PayoutBatch, batch_id)
    if not batch:
        raise ValueError("Payout batch not found")
    new_status = evaluate_payout_contest_window(db, batch, now=now)
    if new_status == "DISBURSED":
        entries = db.scalars(select(LedgerEntry).where(LedgerEntry.payout_batch_id == batch.id)).all()
        for e in entries:
            e.is_disbursed = True
            acct = db.get(LedgerAccount, e.account_id)
            if acct:
                acct.balance_inr = round(acct.balance_inr + e.amount_inr, 2)
        db.flush()
    return batch
