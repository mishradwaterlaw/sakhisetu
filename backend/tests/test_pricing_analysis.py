"""Tests for margin-aware pricing analysis, INSUFFICIENT_DATA, and LyzrPricingAnalystAgent."""

from app.adapters.lyzr import client as lyzr_client
from app.adapters.lyzr.client import LyzrCallResult
from app.models.catalogue import Product
from app.models.governance import UsageMeter
from app.models.intake import Order
from app.models.people import SHG
from app.services import pricing


def test_accept_offer_above_mvp_never_proposes_lower_counter_offer(client, db_session):
    shg = db_session.query(SHG).first()
    product = db_session.query(Product).first()

    order = Order(
        shg_id=shg.id,
        product_id=product.id,
        order_code="ORD-HIGH1",
        status="CONFIRMED",
        quantity=20,
        offered_price_per_unit_inr=185.0,
    )
    db_session.add(order)
    db_session.commit()

    resp = client.post(f"/api/leader/orders/{order.id}/counter-offer-draft")
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "ACCEPT"
    assert data["needs_counter_offer"] is False
    assert data["draft_message"] is None
    assert data["proposed_unit_price_inr"] == 185.0
    assert data["agent_name"] == "DeterministicPricingAnalyst"

    # Secondary "Draft custom quote anyway" path when leader explicitly requests it
    forced = client.post(f"/api/leader/orders/{order.id}/counter-offer-draft?force_draft=true")
    assert forced.status_code == 200
    fdata = forced.json()
    assert fdata["proposed_unit_price_inr"] > 185.0
    assert fdata["draft_message"] is not None


def test_below_mvp_and_insufficient_data_outcomes(client, db_session):
    shg = db_session.query(SHG).first()
    product = db_session.query(Product).first()

    # Below-MVP order
    low = Order(
        shg_id=shg.id,
        product_id=product.id,
        order_code="ORD-LOW1",
        status="CONFIRMED",
        quantity=20,
        offered_price_per_unit_inr=50.0,
    )
    # Unmapped product -> INSUFFICIENT_DATA (never guess)
    unmapped = Order(
        shg_id=shg.id,
        product_id=None,
        order_code="ORD-UNMAP1",
        status="DRAFT",
        quantity=10,
        offered_price_per_unit_inr=150.0,
    )
    db_session.add_all([low, unmapped])
    db_session.commit()

    low_resp = client.post(f"/api/leader/orders/{low.id}/counter-offer-draft").json()
    assert low_resp["verdict"] in ("COUNTER_OFFER", "DECLINE")
    assert low_resp["needs_counter_offer"] is True
    assert low_resp["proposed_unit_price_inr"] > 50.0
    assert "below our minimum viable cost" in low_resp["draft_message"]

    unmap_resp = client.post(f"/api/leader/orders/{unmapped.id}/counter-offer-draft").json()
    assert unmap_resp["verdict"] == "INSUFFICIENT_DATA"
    assert unmap_resp["needs_counter_offer"] is False
    assert unmap_resp["draft_message"] is None


def test_lyzr_pricing_analyst_agent_uses_exact_numbers_and_meters_tokens(client, db_session, monkeypatch):
    shg = db_session.query(SHG).first()
    product = db_session.query(Product).first()

    order = Order(
        shg_id=shg.id,
        product_id=product.id,
        order_code="ORD-LYZR-PR1",
        status="CONFIRMED",
        quantity=15,
        offered_price_per_unit_inr=60.0,
    )
    db_session.add(order)
    db_session.commit()

    from app import config

    class FakeSettings:
        lyzr_api_key = "test-key"
        lyzr_pricing_agent_id = "pricing-agent-1"

    monkeypatch.setattr(config, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(
        lyzr_client,
        "call_lyzr_agent",
        lambda **kwargs: LyzrCallResult(
            trace_id="lyzr_pricing_trace_42",
            raw_response=(
                '{"verdict":"DECLINE","recommended_price_inr":88.87,'
                '"rationale":"Buyer offer Rs 60 is below base cost.",'
                '"draft_message":"Namaste, our minimum viable price is Rs 88.87/unit to cover material and fair wages."}'
            ),
            total_tokens=140,
        ),
    )

    resp = client.post(f"/api/leader/orders/{order.id}/counter-offer-draft")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_name"] == "LyzrPricingAnalystAgent"
    assert data["engine"] == "lyzr_adk"
    assert data["trace_id"] == "lyzr_pricing_trace_42"
    assert "88.87" in data["draft_message"]

    meters = db_session.query(UsageMeter).filter_by(trace_id="lyzr_pricing_trace_42").all()
    assert len(meters) == 1
    assert meters[0].quantity == 140
