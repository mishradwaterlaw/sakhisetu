"""Tests for Phase 2 governance fixes: append-only assignments and QC rotation enforcement."""

from app.models.intake import Order
from app.models.people import Member, SHG
from app.models.planning import Task, TaskAssignment
from app.models.quality import ReviewRotation
from app.services.rotation import create_review_rotation


def test_allocation_override_and_recovery_are_append_only(client, db_session):
    shg = db_session.query(SHG).first()
    leader = db_session.query(Member).filter_by(shg_id=shg.id, role="leader").first()
    members = db_session.query(Member).filter_by(shg_id=shg.id, role="member").all()
    assert len(members) >= 2

    order = Order(shg_id=shg.id, order_code="ORD-APP1", status="ALLOCATION_PROPOSED", quantity=10)
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

    orig = TaskAssignment(
        order_id=order.id,
        task_id=task.id,
        member_id=members[0].id,
        assigned_units=10,
        estimated_minutes=100.0,
        solver_explanation="Initial solver plan",
        status="PROPOSED",
    )
    db_session.add(orig)
    db_session.commit()

    # 1. Leader override must keep original row as OVERRIDDEN and append a new row
    ov_resp = client.post(
        f"/api/leader/orders/{order.id}/approve-allocation",
        json={
            "leader_id": leader.id,
            "overrides": [
                {
                    "assignment_id": orig.id,
                    "new_member_id": members[1].id,
                    "reason": "Rebalance workload",
                }
            ],
        },
    )
    assert ov_resp.status_code == 200

    all_rows = db_session.query(TaskAssignment).filter_by(order_id=order.id).all()
    assert len(all_rows) == 2
    db_session.refresh(orig)
    assert orig.status == "OVERRIDDEN"
    assert orig.member_id == members[0].id  # original row preserved untouched

    override_row = [r for r in all_rows if r.id != orig.id][0]
    assert override_row.member_id == members[1].id
    assert override_row.is_leader_override is True
    assert override_row.status == "APPROVED"

    # 2. Blocker + REASSIGN_UNITS recovery must mark old assignment REASSIGNED and append new row
    blk_resp = client.post(
        f"/api/leader/orders/{order.id}/blockers",
        json={
            "assignment_id": override_row.id,
            "reported_by_member_id": members[1].id,
            "reason": "Machine belt broke",
            "remaining_units": 6,
        },
    )
    assert blk_resp.status_code == 200
    blk_data = blk_resp.json()
    reassign_opt = [o for o in blk_data["options"] if o["type"] == "REASSIGN_UNITS"][0]

    rec_resp = client.post(
        f"/api/leader/blockers/{blk_data['blocker_id']}/approve-recovery",
        json={"leader_id": leader.id, "recovery_option_id": reassign_opt["id"]},
    )
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()
    assert len(rec_data["created_assignment_ids"]) == 1

    all_rows_after = db_session.query(TaskAssignment).filter_by(order_id=order.id).all()
    assert len(all_rows_after) == 3
    db_session.refresh(override_row)
    assert override_row.status == "REASSIGNED"

    new_rec_row = db_session.get(TaskAssignment, rec_data["created_assignment_ids"][0])
    assert new_rec_row.assigned_units == 6
    assert new_rec_row.member_id != members[1].id
    assert new_rec_row.status == "APPROVED"


def test_qc_decision_enforces_rotating_committee_membership(client, db_session):
    shg = db_session.query(SHG).first()
    members = db_session.query(Member).filter_by(shg_id=shg.id).all()
    worker = [m for m in members if m.role == "member"][0]

    order = Order(shg_id=shg.id, order_code="ORD-QCROT", status="QC_PENDING", quantity=10)
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

    ta = TaskAssignment(
        order_id=order.id,
        task_id=task.id,
        member_id=worker.id,
        assigned_units=10,
        estimated_minutes=100.0,
        solver_explanation="test",
        status="COMPLETED",
    )
    db_session.add(ta)
    db_session.flush()

    rot = create_review_rotation(
        db_session,
        shg_id=shg.id,
        purpose="QUALITY",
        target_entity_type="order",
        target_entity_id=order.id,
        committee_size=2,
        exclude_member_ids={worker.id},
    )
    db_session.commit()

    outsiders = [m.id for m in members if m.id not in rot.selected_member_ids]
    assert outsiders, "Expected at least one SHG member outside the 2-member rotation"

    # Non-committee reviewer must be rejected with 403
    bad = client.post(
        f"/api/leader/orders/{order.id}/qc",
        json={
            "assignment_id": ta.id,
            "reviewer_member_id": outsiders[0],
            "units_checked": 5,
            "outcome": "PASS",
        },
    )
    assert bad.status_code == 403

    # Selected rotating committee member succeeds
    good = client.post(
        f"/api/leader/orders/{order.id}/qc",
        json={
            "assignment_id": ta.id,
            "reviewer_member_id": rot.selected_member_ids[0],
            "units_checked": 5,
            "outcome": "PASS",
        },
    )
    assert good.status_code == 200
    assert good.json()["rotation_id"] == rot.id


def test_leader_autonomous_quantity_override_and_split_addition(client, db_session):
    shg = db_session.query(SHG).first()
    leader = db_session.query(Member).filter_by(shg_id=shg.id, role="leader").first()
    members = db_session.query(Member).filter_by(shg_id=shg.id, role="member").all()

    order = Order(shg_id=shg.id, order_code="ORD-QTY1", status="ALLOCATION_PROPOSED", quantity=10)
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

    orig = TaskAssignment(
        order_id=order.id,
        task_id=task.id,
        member_id=members[0].id,
        assigned_units=10,
        estimated_minutes=100.0,
        solver_explanation="Initial solver plan",
        status="PROPOSED",
    )
    db_session.add(orig)
    db_session.commit()

    # Leader splits 10u into 6u for members[0] + 4u for members[1]
    resp = client.post(
        f"/api/leader/orders/{order.id}/approve-allocation",
        json={
            "leader_id": leader.id,
            "overrides": [
                {
                    "assignment_id": orig.id,
                    "new_member_id": members[0].id,
                    "assigned_units": 6,
                    "reason": "Reduced to 6u",
                }
            ],
            "new_assignments": [
                {
                    "task_id": task.id,
                    "member_id": members[1].id,
                    "assigned_units": 4,
                    "reason": "Split remaining 4u",
                }
            ],
        },
    )
    assert resp.status_code == 200
    rows = db_session.query(TaskAssignment).filter_by(order_id=order.id).all()
    active = [r for r in rows if r.status == "APPROVED"]
    assert sum(r.assigned_units for r in active) == 10
    assert {r.member_id: r.assigned_units for r in active} == {members[0].id: 6, members[1].id: 4}
    db_session.refresh(orig)
    assert orig.status == "OVERRIDDEN"
