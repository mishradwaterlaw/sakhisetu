"""Tests for §15-§21 addendums: supplier comparison, counter-offer, bank summary, federation, member privacy, workload pref, photo routing, manual entry."""

from app.models.catalogue import Material
from app.models.people import Federation, Member, Party, SHG
from app.models.quality import Contest
from app.services.planner import MemberCapacity, TaskSpec, solve_allocation


def test_supplier_comparison_and_counter_offer_draft(client, db_session):
    shg = db_session.query(SHG).first()
    buyer = db_session.query(Party).filter_by(party_type="buyer").first()
    mat = db_session.query(Material).first()

    sup1 = Party(party_type="supplier", name="Karnataka Looms")
    sup2 = Party(party_type="supplier", name="Mysuru Cotton Co")
    db_session.add_all([sup1, sup2])
    db_session.flush()

    client.post(
        "/api/leader/supplier-quotes",
        json={"supplier_party_id": sup1.id, "material_id": mat.id, "unit_price_inr": 62.0, "min_order_qty": 50, "delivery_days": 4},
    )
    client.post(
        "/api/leader/supplier-quotes",
        json={"supplier_party_id": sup2.id, "material_id": mat.id, "unit_price_inr": 58.0, "min_order_qty": 100, "delivery_days": 6},
    )

    cmp_res = client.get(f"/api/leader/supplier-quotes/compare?material_id={mat.id}&required_quantity=80").json()
    assert len(cmp_res["quotes"]) == 2
    assert cmp_res["quotes"][0]["supplier_name"] == "Karnataka Looms"  # 80*62=4960 < 100*58=5800

    # §21 Manual order entry -> DRAFT, then §15 counter-offer draft
    leader = db_session.query(Member).filter_by(shg_id=shg.id, role="leader").first()
    man = client.post(
        "/api/leader/orders/manual",
        json={
            "shg_id": shg.id,
            "leader_id": leader.id,
            "buyer_party_id": buyer.id,
            "product_name": "Cotton Tote Bag",
            "quantity": 20,
            "offered_price_per_unit_inr": 70.0,
        },
    ).json()
    assert man["status"] == "DRAFT_CREATED"

    draft = client.post(f"/api/leader/orders/{man['order_id']}/counter-offer-draft").json()
    assert draft["requires_leader_review_before_send"] is True
    assert "Material" in draft["draft_message"]
    assert "Labour" in draft["draft_message"]


def test_bank_creditworthiness_and_group_consent_gate(client, db_session):
    from datetime import datetime, timezone
    from app.models.intake import Order
    from app.models.money import PayoutBatch

    shg = db_session.query(SHG).first()
    leader = db_session.query(Member).filter_by(shg_id=shg.id, role="leader").first()
    members = db_session.query(Member).filter_by(shg_id=shg.id).all()

    # Seed a disbursed PayoutBatch with per-member monetary breakdown to prove no per-member
    # payout figure or name leaks into the bank-ready summary (§16).
    order = Order(shg_id=shg.id, order_code="ORD-BANK1", status="DISBURSED", quantity=10)
    db_session.add(order)
    db_session.flush()
    batch = PayoutBatch(
        shg_id=shg.id,
        order_id=order.id,
        total_amount_inr=437.50,
        status="DISBURSED",
        disbursed_at=datetime.now(timezone.utc),
        breakdown_snapshot=[
            {"member_id": members[1].id, "member_name": members[1].name, "units": 7, "amount_inr": 262.25},
            {"member_id": members[2].id, "member_name": members[2].name, "units": 3, "amount_inr": 175.25},
        ],
    )
    db_session.add(batch)
    db_session.commit()

    resp = client.get(f"/api/leader/shgs/{shg.id}/bank-summary")
    assert resp.status_code == 200
    preview = resp.json()
    preview_text = resp.text

    assert preview["total_group_disbursed_inr"] == 437.50
    assert "group_quality_score_pct" in preview
    for m in members:
        assert m.id not in preview_text
        assert m.name not in preview_text
    assert "262.25" not in preview_text
    assert "175.25" not in preview_text
    assert "breakdown_snapshot" not in preview_text

    # Unilateral share without group ConsentEvent must fail (403)
    bad = client.post(f"/api/leader/shgs/{shg.id}/bank-summary/share")
    assert bad.status_code == 403

    # Consent without group_committee_approved=True must also fail
    from app.services.consent import grant_consent

    unilateral = grant_consent(
        db_session,
        shg_id=shg.id,
        granted_by_member_id=leader.id,
        recipient_type="BANK",
        recipient_id="SBI",
        purpose="Credit check",
        scope={"group_committee_approved": False},
    )
    db_session.commit()
    assert client.post(f"/api/leader/shgs/{shg.id}/bank-summary/share?consent_event_id={unilateral.id}").status_code == 403

    # Partial member consent (only members[1], missing members[2]) must fail with 403
    from app.models.governance import ConsentEvent

    partial = grant_consent(
        db_session,
        shg_id=shg.id,
        granted_by_member_id=members[1].id,
        recipient_type="BANK",
        recipient_id="SBI",
        purpose="Credit check",
        scope={"group_committee_approved": True},
        member_ids=[members[1].id],
    )
    db_session.commit()
    assert client.post(f"/api/leader/shgs/{shg.id}/bank-summary/share?consent_event_id={partial.id}").status_code == 403

    # Full per-member consent writes one ConsentEvent row per contributing member
    group_ok = grant_consent(
        db_session,
        shg_id=shg.id,
        granted_by_member_id=leader.id,
        recipient_type="BANK",
        recipient_id="SBI",
        purpose="Credit check",
        scope={"group_committee_approved": True},
    )
    db_session.commit()
    bank_consents = (
        db_session.query(ConsentEvent)
        .filter_by(shg_id=shg.id, recipient_type="BANK", consented=True)
        .all()
    )
    consented_ids = {c.granted_by_member_id for c in bank_consents if c.scope.get("group_committee_approved")}
    assert {members[1].id, members[2].id}.issubset(consented_ids)

    ok = client.post(f"/api/leader/shgs/{shg.id}/bank-summary/share?consent_event_id={group_ok.id}")
    assert ok.status_code == 200
    assert ok.json()["consented_member_count"] == 2
    assert ok.json()["consent_event_id"] == group_ok.id


def test_federation_pooled_buy_and_dispute_escalation(client, db_session):
    fed = db_session.query(Federation).first()
    shg1 = db_session.query(SHG).first()
    shg2 = SHG(federation_id=fed.id, name="Cauvery Mahila Sangha", village="Hunsur", primary_language="kn")
    db_session.add(shg2)
    db_session.flush()

    mat = db_session.query(Material).first()
    sup = Party(party_type="supplier", name="Fed Bulk Supplier")
    db_session.add(sup)
    db_session.flush()

    client.post(
        "/api/leader/supplier-quotes",
        json={"federation_id": fed.id, "supplier_party_id": sup.id, "material_id": mat.id, "unit_price_inr": 50.0, "min_order_qty": 100},
    )

    pooled = client.post(
        f"/api/leader/federations/{fed.id}/pooled-buy",
        json={"material_id": mat.id, "shg_quantities": {shg1.id: 60.0, shg2.id: 50.0}},
    ).json()
    assert pooled["total_pooled_quantity"] == 110.0
    assert len(pooled["per_shg_allocations"]) == 2
    assert pooled["per_shg_allocations"][0]["attributed_cost_inr"] == 3000.0
    assert pooled["per_shg_allocations"][1]["attributed_cost_inr"] == 2500.0

    # §17b Dispute escalation
    m = db_session.query(Member).filter_by(shg_id=shg1.id).first()
    c = Contest(shg_id=shg1.id, target_type="QC_CHECK", target_id="qc-1", raised_by_member_id=m.id, reason="Leader flagged unfairly")
    db_session.add(c)
    db_session.commit()

    esc = client.post(f"/api/leader/contests/{c.id}/escalate-federation")
    assert esc.status_code == 200
    assert esc.json()["status"] == "FEDERATION_REVIEW"

    res = client.post(
        f"/api/leader/contests/{c.id}/resolve-federation",
        json={"federation_reviewer_id": "fed-officer-1", "upheld": True, "resolution_notes": "Stitching meets rubric"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "RESOLVED_UPHELD"


def test_member_to_member_privacy_boundary_enforced(client, db_session):
    members = db_session.query(Member).all()
    m1, m2 = members[0], members[1]

    # Member 1 cannot query Member 2's record
    forbidden = client.get(f"/api/member/{m2.id}/record", headers={"X-Member-Id": m1.id})
    assert forbidden.status_code == 403

    # Member 1 can query her own record
    allowed = client.get(f"/api/member/{m1.id}/record", headers={"X-Member-Id": m1.id})
    assert allowed.status_code == 200


def test_workload_preference_soft_constraint_and_anti_favoritism_warning():
    tasks = [TaskSpec("t1", "stitch", "stitching", ["sewing_machine"], 10, 10.0)]
    members = [
        MemberCapacity("m1", "Anita", ["stitching"], ["sewing_machine"], 200, workload_preference="more", consecutive_max_share_cycles=2),
        MemberCapacity("m2", "Geeta", ["stitching"], ["sewing_machine"], 200, workload_preference="less"),
    ]
    res = solve_allocation(tasks, members, horizon_days=1)
    assert res.feasible is True
    by_m = {a.member_name: a for a in res.assignments}
    assert by_m["Anita"].assigned_units > by_m.get("Geeta", type("X", (), {"assigned_units": 0})).assigned_units
    assert "workload preference='more'" in by_m["Anita"].explanation
    assert len(res.fairness_warnings) == 1
    assert "consecutive cycles" in res.fairness_warnings[0]


def test_zero_unit_member_with_more_preference_gets_explicit_disqualification_explanation():
    tasks = [TaskSpec("t1", "stitch", "stitching", ["sewing_machine"], 10, 10.0)]
    members = [
        MemberCapacity("m1", "Anita", ["stitching"], ["sewing_machine"], 200, workload_preference="standard"),
        MemberCapacity("m2", "Radha", ["qc"], [], 200, workload_preference="more"),
    ]
    res = solve_allocation(tasks, members, horizon_days=1)
    assert res.feasible is True
    by_m = {a.member_name: a for a in res.assignments}
    assert by_m["Anita"].assigned_units == 10
    assert "Radha" in by_m
    assert by_m["Radha"].assigned_units == 0
    assert "workload preference='more'" in by_m["Radha"].explanation
    assert "missing skill 'stitching'" in by_m["Radha"].explanation
    assert "missing tools ['sewing_machine']" in by_m["Radha"].explanation


def test_photo_disambiguation_ambiguous_vs_sample(client, db_session):
    shg = db_session.query(SHG).first()
    res = client.post(
        "/api/webhooks/whatsapp",
        json={
            "shg_id": shg.id,
            "sender_phone": "+919800000002",
            "text": "",
            "payload": {"has_image": True},
        },
    ).json()
    assert res["status"] == "UNROUTED"
    assert res["clarification_prompt"]["type"] == "interactive_buttons"
