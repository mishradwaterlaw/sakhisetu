"""Tests for the enforced two-type state machine (§2 & §7)."""

from datetime import datetime, timedelta, timezone
import pytest

from app.models.intake import Order
from app.models.money import PayoutBatch
from app.models.people import Member, SHG
from app.models.quality import Contest
from app.services.state_machine import (
    StateTransitionError,
    evaluate_payout_contest_window,
    record_approval_and_transition,
    verify_explicit_transition_has_approval,
)


def test_cannot_advance_explicit_gate_without_approval(db_session):
    shg = db_session.query(SHG).first()
    order = Order(shg_id=shg.id, order_code="ORD-TEST1", status="DRAFT", quantity=10)
    db_session.add(order)
    db_session.flush()

    with pytest.raises(StateTransitionError, match="no explicit Approval record exists"):
        verify_explicit_transition_has_approval(
            db_session,
            entity_type="order",
            entity_id=order.id,
            from_state="DRAFT",
            to_state="CONFIRMED",
        )


def test_explicit_approval_advances_order_and_writes_audit(db_session):
    shg = db_session.query(SHG).first()
    leader = db_session.query(Member).filter_by(shg_id=shg.id, role="leader").first()
    order = Order(shg_id=shg.id, order_code="ORD-TEST2", status="DRAFT", quantity=10)
    db_session.add(order)
    db_session.flush()

    approval = record_approval_and_transition(
        db_session,
        shg_id=shg.id,
        entity_obj=order,
        entity_type="order",
        entity_id=order.id,
        current_state="DRAFT",
        target_state="CONFIRMED",
        actor_type="LEADER",
        actor_id=leader.id,
    )
    assert order.status == "CONFIRMED"
    assert approval.decision == "APPROVED"


def test_payout_contest_window_never_auto_approves_and_halts_on_contest(db_session):
    shg = db_session.query(SHG).first()
    member = db_session.query(Member).filter_by(shg_id=shg.id, role="member").first()
    order = Order(shg_id=shg.id, order_code="ORD-PAY1", status="QC_CLEARED", quantity=10)
    db_session.add(order)
    db_session.flush()

    now = datetime.now(timezone.utc)
    batch = PayoutBatch(
        shg_id=shg.id,
        order_id=order.id,
        total_amount_inr=500.0,
        status="PAYOUT_PENDING",
    )
    db_session.add(batch)
    db_session.flush()

    # 1. Cannot evaluate contest window OR advance past PAYOUT_PENDING without a persisted Approval row
    with pytest.raises(StateTransitionError, match="no explicit Approval record exists"):
        verify_explicit_transition_has_approval(
            db_session,
            entity_type="payout_batch",
            entity_id=batch.id,
            from_state="PAYOUT_PENDING",
            to_state="PAYOUT_APPROVED",
        )
    with pytest.raises(StateTransitionError):
        evaluate_payout_contest_window(db_session, batch, now=now + timedelta(hours=48))

    # 2. Explicit committee approval moves to PAYOUT_APPROVED
    record_approval_and_transition(
        db_session,
        shg_id=shg.id,
        entity_obj=batch,
        entity_type="payout_batch",
        entity_id=batch.id,
        current_state="PAYOUT_PENDING",
        target_state="PAYOUT_APPROVED",
        actor_type="REVIEW_COMMITTEE",
        actor_id=member.id,
    )
    batch.contest_window_ends_at = now + timedelta(hours=24)
    db_session.flush()

    # 3. Before window ends -> stays PAYOUT_APPROVED
    assert evaluate_payout_contest_window(db_session, batch, now=now + timedelta(hours=12)) == "PAYOUT_APPROVED"

    # 4. If an OPEN contest exists -> halts into DISPUTED even after window
    db_session.add(
        Contest(
            shg_id=shg.id,
            target_type="PAYOUT_BATCH",
            target_id=batch.id,
            raised_by_member_id=member.id,
            reason="Count mismatch",
            status="OPEN",
        )
    )
    db_session.flush()
    assert evaluate_payout_contest_window(db_session, batch, now=now + timedelta(hours=30)) == "DISPUTED"
    assert batch.status == "DISPUTED"

    # 5. Once contest is resolved & re-approved, window elapsed with 0 open contests -> DISBURSED
    c = db_session.query(Contest).filter_by(target_id=batch.id).first()
    c.status = "RESOLVED_UPHELD"
    record_approval_and_transition(
        db_session,
        shg_id=shg.id,
        entity_obj=batch,
        entity_type="payout_batch",
        entity_id=batch.id,
        current_state="DISPUTED",
        target_state="PAYOUT_APPROVED",
        actor_type="LEADER",
        actor_id=member.id,
    )
    assert evaluate_payout_contest_window(db_session, batch, now=now + timedelta(hours=30)) == "DISBURSED"
