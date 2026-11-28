"""Tests for Phase 3 repeatable pricing negotiation loop (Flow A)."""

from app.models.intake import Order
from app.models.people import Member, Party, SHG


def test_repeatable_pricing_counter_offer_negotiation_loop(client, db_session):
    shg = db_session.query(SHG).first()
    leader = db_session.query(Member).filter_by(shg_id=shg.id, role="leader").first()
    buyer = db_session.query(Party).filter_by(party_type="buyer").first()

    order = Order(
        shg_id=shg.id,
        buyer_party_id=buyer.id,
        order_code="ORD-NEG1",
        status="CONFIRMED",
        quantity=20,
        offered_price_per_unit_inr=120.0,
    )
    db_session.add(order)
    db_session.commit()

    # Round 1: Leader sends counter-offer -> COUNTER_OFFER_SENT
    s1 = client.post(
        f"/api/leader/orders/{order.id}/send-counter-offer",
        json={
            "leader_id": leader.id,
            "message": "Minimum viable price is Rs 165/unit.",
            "counter_price_per_unit_inr": 165.0,
        },
    )
    assert s1.status_code == 200
    assert s1.json()["status"] == "COUNTER_OFFER_SENT"

    # Buyer sends revised offer #1 -> loops back to CONFIRMED for leader re-review
    b1 = client.post(
        f"/api/buyer/orders/{order.id}/revised-offer",
        headers={"X-Buyer-Party-Id": buyer.id},
        json={"offered_price_per_unit_inr": 150.0},
    )
    assert b1.status_code == 200
    assert b1.json()["status"] == "CONFIRMED"
    assert b1.json()["offered_price_per_unit_inr"] == 150.0

    # Round 2: Leader sends another counter-offer -> COUNTER_OFFER_SENT again
    s2 = client.post(
        f"/api/leader/orders/{order.id}/send-counter-offer",
        json={
            "leader_id": leader.id,
            "message": "We can meet at Rs 160/unit.",
            "counter_price_per_unit_inr": 160.0,
        },
    )
    assert s2.status_code == 200
    assert s2.json()["status"] == "COUNTER_OFFER_SENT"

    # Buyer revised offer #2 via leader simulation endpoint -> back to CONFIRMED
    b2 = client.post(
        f"/api/leader/orders/{order.id}/buyer-revised-offer",
        json={"offered_price_per_unit_inr": 160.0},
    )
    assert b2.status_code == 200
    assert b2.json()["status"] == "CONFIRMED"

    # Leader finally approves price -> PRICING_APPROVED
    fin = client.post(
        f"/api/leader/orders/{order.id}/approve-pricing",
        json={"leader_id": leader.id, "agreed_price_per_unit_inr": 160.0},
    )
    assert fin.status_code == 200
    assert fin.json()["status"] == "PRICING_APPROVED"
