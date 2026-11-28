"""Tests for shared rotation, group-first payout broadcasts, and ConsentEvent gate (§7, §8)."""

import pytest

from app.models.governance import CommsLog
from app.models.intake import Order
from app.models.people import Member, SHG
from app.models.planning import Task, TaskAssignment
from app.services.consent import ConsentRequiredError, export_bank_payout_csv, grant_consent
from app.services.payout import approve_payout_by_committee, initiate_payout_batch
from app.services.rotation import create_review_rotation, opt_out_and_reshuffle


def test_shared_rotation_deterministic_and_opt_out_reshuffle(db_session):
    shg = db_session.query(SHG).first()
    r1 = create_review_rotation(
        db_session,
        shg_id=shg.id,
        purpose="QUALITY",
        target_entity_type="order",
        target_entity_id="order-123",
        committee_size=2,
    )
    first_selected = list(r1.selected_member_ids)
    assert len(first_selected) == 2

    dropped = first_selected[0]
    r2 = opt_out_and_reshuffle(db_session, rotation_id=r1.id, member_id=dropped)
    assert dropped in r2.opted_out_member_ids
    assert dropped not in r2.selected_member_ids
    assert len(r2.selected_member_ids) == 2


def test_payout_group_notice_broadcast_and_consent_gate(db_session):
    shg = db_session.query(SHG).first()
    members = db_session.query(Member).filter_by(shg_id=shg.id).all()
    order = Order(shg_id=shg.id, order_code="ORD-GRP1", status="QC_CLEARED", quantity=10)
    db_session.add(order)
    db_session.flush()

    task = Task(
        order_id=order.id,
        step_name="stitch",
        required_skill="stitching",
        total_units=10,
        minutes_per_unit=10.0,
        piece_rate_inr=25.0,
    )
    db_session.add(task)
    db_session.flush()

    db_session.add(
        TaskAssignment(
            order_id=order.id,
            task_id=task.id,
            member_id=members[1].id,
            assigned_units=10,
            completed_units=10,
            passed_units=10,
            estimated_minutes=100.0,
            solver_explanation="test",
            status="COMPLETED",
        )
    )
    db_session.flush()

    batch = initiate_payout_batch(db_session, order_id=order.id, committee_size=2)
    assert batch.group_notice_sent is True
    notices = db_session.query(CommsLog).filter_by(message_category="GROUP_PAYOUT_NOTICE").all()
    assert len(notices) == len(members)  # Every member notified, not just committee

    from app.models.governance import Approval
    from app.models.quality import ReviewRotation

    rot = db_session.get(ReviewRotation, batch.rotation_id)
    assert len(rot.selected_member_ids) == 2

    # First committee member approves -> quorum (2/2) not yet met; must stay PAYOUT_PENDING
    res1 = approve_payout_by_committee(db_session, batch_id=batch.id, reviewer_member_id=rot.selected_member_ids[0])
    assert batch.status == "PAYOUT_PENDING"
    assert batch.group_approval_broadcast_sent is False
    assert res1["required_quorum"] == 2
    assert res1["approved_member_ids"] == [rot.selected_member_ids[0]]
    assert res1["pending_member_ids"] == [rot.selected_member_ids[1]]

    # Second committee member approves -> quorum met -> PAYOUT_APPROVED + broadcast
    res2 = approve_payout_by_committee(db_session, batch_id=batch.id, reviewer_member_id=rot.selected_member_ids[1])
    assert batch.status == "PAYOUT_APPROVED"
    assert res2["pending_member_ids"] == []

    # Verify one Approval row per individual committee member
    approvals = (
        db_session.query(Approval)
        .filter_by(entity_type="payout_batch", entity_id=batch.id, decision="APPROVED")
        .all()
    )
    assert {a.actor_id for a in approvals} == set(rot.selected_member_ids)

    assert batch.group_approval_broadcast_sent is True
    broadcasts = db_session.query(CommsLog).filter_by(message_category="GROUP_APPROVAL_BROADCAST").all()
    readbacks = db_session.query(CommsLog).filter_by(message_category="EARNINGS_READBACK").all()
    assert len(broadcasts) == len(members)
    assert len(readbacks) == 1
    assert readbacks[0].is_replayable is True

    # Bank CSV export MUST fail without ConsentEvent
    with pytest.raises(ConsentRequiredError):
        export_bank_payout_csv(db_session, batch_id=batch.id, consent_event_id=None)

    consent = grant_consent(
        db_session,
        shg_id=shg.id,
        granted_by_member_id=members[0].id,
        recipient_type="BANK",
        recipient_id="SBI",
        purpose="Disbursement",
        scope={"batch_id": batch.id},
    )
    csv_out = export_bank_payout_csv(db_session, batch_id=batch.id, consent_event_id=consent.id)
    assert members[1].name in csv_out
