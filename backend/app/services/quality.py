"""Quality control service (§6): rubric agreement, human-assisted photo QC, private coaching, and deferred classifier seam."""

from datetime import datetime, timedelta, timezone
from typing import Protocol
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.intake import Order
from app.models.planning import TaskAssignment
from app.models.quality import Contest, QCCheck, QualityRubric
from app.services.rotation import create_review_rotation


class QualityClassifierPort(Protocol):
    """Explicit seam for future automated visual defect classification (deferred per §6)."""

    def classify_defect(self, submitted_media_uri: str, reference_media_uris: list[str]) -> dict:
        ...


def agree_or_flag_rubric(
    db: Session,
    *,
    order_id: str,
    criteria: list[dict],
    reference_media_ids: list[str],
    leader_agreed: bool,
    buyer_agreed: bool,
    disagreement_notes: str | None = None,
) -> QualityRubric:
    order = db.get(Order, order_id)
    if not order:
        raise ValueError(f"Order {order_id} not found")

    rubric = db.scalar(select(QualityRubric).where(QualityRubric.order_id == order_id))
    if not rubric:
        rubric = QualityRubric(order_id=order_id)
        db.add(rubric)

    rubric.criteria = criteria
    rubric.reference_media_ids = reference_media_ids
    rubric.leader_agreed = leader_agreed
    rubric.buyer_agreed = buyer_agreed
    rubric.disagreement_notes = disagreement_notes

    if leader_agreed and buyer_agreed:
        rubric.status = "AGREED"
        order.rubric_disagreement_risk = False
    else:
        rubric.status = "DISAGREEMENT_FLAGGED"
        order.rubric_disagreement_risk = True

    db.flush()
    return rubric


def record_human_qc_decision(
    db: Session,
    *,
    order_id: str,
    assignment_id: str,
    submitted_media_id: str | None,
    reviewer_member_id: str,
    units_checked: int,
    outcome: str,  # PASS | FLAG | ESCALATE
    flag_reason: str | None = None,
    contest_window_hours: int = 24,
) -> QCCheck:
    if outcome not in ("PASS", "FLAG", "ESCALATE"):
        raise ValueError(f"Invalid QC outcome: {outcome}")

    assignment = db.get(TaskAssignment, assignment_id)
    if not assignment or assignment.order_id != order_id:
        raise ValueError("Assignment not found for order")

    order = db.get(Order, order_id)
    if not order:
        raise ValueError("Order not found")

    # Ensure shared rotation exists for QUALITY on this order
    rotation = create_review_rotation(
        db,
        shg_id=order.shg_id,
        purpose="QUALITY",
        target_entity_type="order",
        target_entity_id=order_id,
        committee_size=2,
        exclude_member_ids={assignment.member_id},
    )

    # Check repeat-defect pattern for private coaching note (never punitive or public)
    coaching_note: str | None = None
    if outcome in ("FLAG", "ESCALATE"):
        prior_flags = db.scalars(
            select(QCCheck).where(
                QCCheck.member_id == assignment.member_id,
                QCCheck.outcome.in_(["FLAG", "ESCALATE"]),
            )
        ).all()
        if len(prior_flags) >= 1:
            coaching_note = (
                f"Private coaching note: {len(prior_flags) + 1} recent quality flags observed "
                f"(latest: {flag_reason or 'see reference photo'}). Offer 1-on-1 stitching tip."
            )

    qc = QCCheck(
        order_id=order_id,
        assignment_id=assignment_id,
        member_id=assignment.member_id,
        submitted_media_id=submitted_media_id,
        reviewer_member_id=reviewer_member_id,
        rotation_id=rotation.id,
        units_checked=units_checked,
        outcome=outcome,
        flag_reason=flag_reason,
        private_coaching_note=coaching_note,
        contest_deadline_at=datetime.now(timezone.utc) + timedelta(hours=contest_window_hours),
    )
    db.add(qc)

    if outcome == "PASS":
        assignment.passed_units = min(assignment.assigned_units, assignment.passed_units + units_checked)

    db.flush()
    return qc


def contest_qc_flag(
    db: Session,
    *,
    qc_check_id: str,
    member_id: str,
    reason: str,
) -> Contest:
    qc = db.get(QCCheck, qc_check_id)
    if not qc:
        raise ValueError("QC check not found")
    if qc.member_id != member_id:
        raise ValueError("Only the member whose work was flagged can contest this QC check")
    if qc.contest_deadline_at:
        deadline = qc.contest_deadline_at
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > deadline:
            raise ValueError("Contest window for this QC check has closed")

    order = db.get(Order, qc.order_id)
    contest = Contest(
        shg_id=order.shg_id,
        target_type="QC_CHECK",
        target_id=qc.id,
        raised_by_member_id=member_id,
        reason=reason,
        status="OPEN",
    )
    db.add(contest)
    db.flush()
    return contest
