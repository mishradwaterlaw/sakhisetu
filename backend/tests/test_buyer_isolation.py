"""Tests for strict data-layer Buyer isolation (§6, §12)."""

from app.models.intake import Order
from app.models.people import Member, Party, SHG
from app.models.planning import Task, TaskAssignment
from app.models.quality import QCCheck


def test_buyer_api_never_exposes_member_data(client, db_session):
    shg = db_session.query(SHG).first()
    buyer = db_session.query(Party).filter_by(party_type="buyer").first()
    member = db_session.query(Member).filter_by(shg_id=shg.id, role="member").first()

    order = Order(
        shg_id=shg.id,
        buyer_party_id=buyer.id,
        order_code="ORD-BUYER1",
        status="IN_PRODUCTION",
        quantity=30,
        agreed_price_per_unit_inr=190.0,
    )
    db_session.add(order)
    db_session.flush()

    task = Task(
        order_id=order.id,
        step_name="stitch",
        required_skill="stitching",
        total_units=30,
        minutes_per_unit=10.0,
        piece_rate_inr=20.0,
        status="COMPLETED",
    )
    db_session.add(task)
    db_session.flush()

    ta = TaskAssignment(
        order_id=order.id,
        task_id=task.id,
        member_id=member.id,
        assigned_units=30,
        passed_units=28,
        estimated_minutes=300.0,
        solver_explanation="test",
    )
    db_session.add(ta)
    db_session.flush()

    db_session.add(
        QCCheck(
            order_id=order.id,
            assignment_id=ta.id,
            member_id=member.id,
            units_checked=28,
            outcome="PASS",
        )
    )
    db_session.commit()

    resp = client.get("/api/buyer/orders", headers={"X-Buyer-Party-Id": buyer.id})
    assert resp.status_code == 200
    payload_text = resp.text
    assert "ORD-BUYER1" in payload_text
    assert member.name not in payload_text
    assert member.id not in payload_text
    assert "member_id" not in payload_text
    assert "piece_rate" not in payload_text
    assert "breakdown_snapshot" not in payload_text

    detail_resp = client.get(f"/api/buyer/orders/{order.id}", headers={"X-Buyer-Party-Id": buyer.id})
    assert detail_resp.status_code == 200
    detail_text = detail_resp.text
    assert "ORD-BUYER1" in detail_text
    assert member.name not in detail_text
    assert member.id not in detail_text
    assert "member_id" not in detail_text
    assert "piece_rate" not in detail_text
