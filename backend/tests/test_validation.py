"""Tests for pure deterministic order validation (§4.6)."""

from datetime import datetime, timedelta, timezone

from app.models.catalogue import Product
from app.models.people import Party, SHG
from app.services.validation import validate_order_deterministic


def test_validation_accepts_valid_order(db_session):
    shg = db_session.query(SHG).first()
    buyer = db_session.query(Party).filter_by(party_type="buyer").first()
    prod = db_session.query(Product).first()

    res = validate_order_deterministic(
        db_session,
        shg_id=shg.id,
        buyer_party_id=buyer.id,
        product_id=prod.id,
        quantity=20,
        due_date=datetime.now(timezone.utc) + timedelta(days=7),
        offered_price_per_unit_inr=180.0,
    )
    assert res.is_valid is True
    assert res.issues == []


def test_validation_rejects_past_due_date_and_material_shortfall(db_session):
    shg = db_session.query(SHG).first()
    buyer = db_session.query(Party).filter_by(party_type="buyer").first()
    prod = db_session.query(Product).first()

    res = validate_order_deterministic(
        db_session,
        shg_id=shg.id,
        buyer_party_id=buyer.id,
        product_id=prod.id,
        quantity=5000,  # exceeds 500m cotton inventory (0.6m/unit -> 3000m needed)
        due_date=datetime.now(timezone.utc) - timedelta(days=1),
        offered_price_per_unit_inr=180.0,
    )
    codes = {i.code for i in res.issues}
    assert res.is_valid is False
    assert "PAST_DUE_DATE" in codes
    assert "INSUFFICIENT_MATERIAL" in codes
