"""Tests for multi-channel intake pipeline, quarantine onboarding, Lyzr trace, and UsageMeter (§3, §4, §8, §9)."""

from app.models.governance import AgentEvent, UsageMeter
from app.models.people import SHG


def test_unknown_sender_quarantined_and_onboarded(client, db_session):
    shg = db_session.query(SHG).first()
    resp = client.post(
        "/api/webhooks/whatsapp",
        json={
            "shg_id": shg.id,
            "sender_phone": "+919111222333",
            "text": "Need 25 Cotton Tote Bag pieces at Rs 180",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "QUARANTINED"

    # Leader can onboard directly from quarantine (no dead end)
    dash = client.get(f"/api/leader/shgs/{shg.id}/dashboard").json()
    assert len(dash["quarantined_messages"]) == 1
    qm_id = dash["quarantined_messages"][0]["id"]

    onb = client.post(
        f"/api/leader/quarantine/{qm_id}/onboard-buyer",
        json={"leader_id": dash["members"][0]["id"], "name": "Walk-in Boutique", "phone": "+919111222333"},
    )
    assert onb.status_code == 200
    assert onb.json()["status"] == "ONBOARDED_AND_UNQUARANTINED"


def test_exotel_unrouted_returns_dtmf_exoml_and_whatsapp_draft_traces_steps(client, db_session):
    shg = db_session.query(SHG).first()

    # Ambiguous voice call -> returns ExoML <Gather> DTMF prompt
    ex_resp = client.post(
        "/api/webhooks/exotel",
        json={"shg_id": shg.id, "From": "+919800000002", "transcript": "hello"},
    )
    assert ex_resp.status_code == 200
    assert "<Gather" in ex_resp.text
    assert "Press 1 for New Order" in ex_resp.text

    # Valid WhatsApp order -> traced AgentEvents + UsageMeter recorded
    wa_resp = client.post(
        "/api/webhooks/whatsapp",
        json={
            "shg_id": shg.id,
            "sender_phone": "+919900000099",
            "text": "Order 30 Cotton Tote Bag pieces at Rs 190 in 10 days",
        },
    )
    assert wa_resp.status_code == 200
    wa_data = wa_resp.json()
    assert wa_data["status"] == "DRAFT_CREATED"

    events = db_session.query(AgentEvent).filter_by(trace_id=wa_data["trace_id"]).all()
    step_names = [e.step_name for e in events]
    assert step_names == ["receive", "identify", "normalize", "route", "extract", "validate"]

    meters = db_session.query(UsageMeter).filter_by(trace_id=wa_data["trace_id"]).all()
    assert len(meters) >= 2  # WHATSAPP_MSG + LLM_TOKENS
