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

    # A distinct quantity avoids duplicating the seeded 30-piece order.
    wa_resp = client.post(
        "/api/webhooks/whatsapp",
        json={
            "shg_id": shg.id,
            "sender_phone": "+919900000099",
            "text": "Order 31 Cotton Tote Bag pieces at Rs 190 in 10 days",
        },
    )
    assert wa_resp.status_code == 200
    wa_data = wa_resp.json()
    assert wa_data["status"] == "DRAFT_CREATED"

    events = db_session.query(AgentEvent).filter_by(trace_id=wa_data["trace_id"]).all()
    step_names = [e.step_name for e in events]
    assert step_names == ["receive", "identify", "normalize", "route", "extract", "validate"]

    meters = db_session.query(UsageMeter).filter_by(trace_id=wa_data["trace_id"]).all()
    # Offline/local deterministic fallback meters only WHATSAPP_MSG (0 fake LLM_TOKENS)
    assert len(meters) == 1
    assert meters[0].resource_type == "WHATSAPP_MSG"


def test_voice_note_normalize_and_lyzr_adk_paths(db_session, monkeypatch):
    from app.adapters.channels.base import NormalizedInbound
    from app.adapters.lyzr import orchestrator
    from app.adapters.lyzr.client import LyzrCallResult
    from app.adapters.speech.bhashini import SpeechResult

    shg = db_session.query(SHG).first()

    # 1. Mock Bhashini ASR for voice note
    monkeypatch.setattr(
        orchestrator,
        "transcribe_audio_sync",
        lambda audio_bytes, source_language="kn": SpeechResult(
            transcript="Please make 40 Cotton Tote Bag pieces at Rs 185 in 12 days",
            confidence=0.88,
            language=source_language,
            provider="bhashini",
        ),
    )

    # 2. Mock Lyzr ADK settings + call_lyzr_agent
    class FakeSettings:
        lyzr_api_key = "test-key"
        lyzr_router_agent_id = "router-agent-1"
        lyzr_extractor_agent_id = "extractor-agent-1"

    monkeypatch.setattr(orchestrator, "get_settings", lambda: FakeSettings())

    def fake_call_lyzr(*, agent_id, user_id, session_id, message):
        return LyzrCallResult(
            trace_id="lyzr_trace_real_999",
            raw_response=(
                '{"product":{"value":"Cotton Tote Bag","confidence":0.95,"source_span":"Cotton Tote Bag"},'
                '"quantity":{"value":40,"confidence":0.96,"source_span":"40"},'
                '"offered_price":{"value":185,"confidence":0.94,"source_span":"Rs 185"},'
                '"due_date":{"value":"2026-12-15","confidence":0.91,"source_span":"in 12 days"}}'
            ),
            total_tokens=412,
        )

    monkeypatch.setattr(orchestrator, "call_lyzr_agent", fake_call_lyzr)

    outcome = orchestrator.run_intake_pipeline(
        db_session,
        shg_id=shg.id,
        inbound=NormalizedInbound(
            channel="whatsapp_smartphone",
            provider_message_id="wa-voice-1",
            sender_phone="+919900000099",
            audio_bytes=b"RIFF....fakewav",
        ),
    )

    assert outcome.status == "DRAFT_CREATED"
    assert outcome.trace_id == "lyzr_trace_real_999"

    events = db_session.query(AgentEvent).filter_by(trace_id="lyzr_trace_real_999").all()
    by_step = {e.step_name: e for e in events}
    assert by_step["extract"].agent_name == "LyzrOrderExtractorAgent"
    assert by_step["extract"].input_summary["engine"] == "lyzr_adk"

    meters = db_session.query(UsageMeter).filter_by(resource_type="LLM_TOKENS", trace_id="lyzr_trace_real_999").all()
    assert len(meters) == 1
    assert meters[0].quantity == 412

    asr_meters = db_session.query(UsageMeter).filter_by(resource_type="ASR_MINUTES").all()
    assert len(asr_meters) >= 1


def test_route_by_intent_llm_fallback(db_session, monkeypatch):
    from app.adapters.channels.base import NormalizedInbound
    from app.adapters.lyzr import orchestrator
    from app.adapters.lyzr.client import LyzrCallResult

    shg = db_session.query(SHG).first()

    class FakeSettings:
        lyzr_api_key = "test-key"
        lyzr_router_agent_id = "router-agent-1"
        lyzr_extractor_agent_id = ""

    monkeypatch.setattr(orchestrator, "get_settings", lambda: FakeSettings())
    monkeypatch.setattr(
        orchestrator,
        "call_lyzr_agent",
        lambda **kwargs: LyzrCallResult(
            trace_id="lyzr_route_trace_77",
            raw_response='{"intent":"BLOCKER_REPORT","confidence":0.93,"reason":"Power outage"}',
            total_tokens=95,
        ),
    )

    outcome = orchestrator.run_intake_pipeline(
        db_session,
        shg_id=shg.id,
        inbound=NormalizedInbound(
            channel="whatsapp_smartphone",
            provider_message_id="wa-ambig-1",
            sender_phone="+919800000002",
            raw_text="No electricity in workshop since morning",
        ),
    )
    assert outcome.status == "BLOCKER_REPORTED"
    assert outcome.trace_id == "lyzr_route_trace_77"
    route_ev = (
        db_session.query(AgentEvent)
        .filter_by(trace_id="lyzr_route_trace_77", step_name="route")
        .first()
    )
    assert route_ev.agent_name == "LyzrRouterAgent"
    assert route_ev.output_summary["method"] == "lyzr_adk"
    assert route_ev.confidence == 0.93
