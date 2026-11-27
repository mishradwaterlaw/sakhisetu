"""Idempotent demo/bootstrap seed for local dev and first-run verification."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.catalogue import Material, PriceModel, Product, TaskTemplate, TemplateRequirement, Tool
from app.models.people import Federation, Member, Party, SHG
from app.models.planning import Inventory
from app.security import blind_index
from app.services.demo_conversations import seed_demo_conversations


def seed_demo_data(db: Session) -> dict:
    existing = db.scalar(select(SHG).where(SHG.name == "Kaveri Mahila Sangha"))
    if existing:
        seed_demo_conversations(db, existing)
        db.commit()
        buyer = db.scalar(select(Party).where(Party.party_type == "buyer"))
        leader = db.scalar(select(Member).where(Member.shg_id == existing.id, Member.role == "leader"))
        return {
            "shg_id": existing.id,
            "leader_id": leader.id if leader else None,
            "buyer_party_id": buyer.id if buyer else None,
        }

    fed = Federation(name="Mysuru Gramin Mahila Federation", district="Mysuru", state="Karnataka")
    db.add(fed)
    db.flush()

    shg = SHG(
        federation_id=fed.id,
        name="Kaveri Mahila Sangha",
        village="Nanjangud",
        primary_language="kn",
    )
    db.add(shg)
    db.flush()

    members_spec = [
        ("Lakshmi Devi", "leader", "+919800000001", "kn", "whatsapp_smartphone", ["cutting", "stitching", "qc"], ["scissors", "sewing_machine"], 180),
        ("Anita Kumari", "member", "+919800000002", "kn", "basic_phone_voice", ["stitching", "packing"], ["sewing_machine"], 240),
        ("Geeta Bai", "member", "+919800000003", "kn", "basic_phone_voice", ["cutting", "stitching"], ["scissors", "sewing_machine"], 240),
        ("Radhaamma", "member", "+919800000004", "kn", "janai_cafe", ["qc", "packing"], [], 240),
        ("Savitha N", "member", "+919800000005", "kn", "whatsapp_smartphone", ["stitching", "qc"], ["sewing_machine"], 240),
    ]
    leader_id = None
    for name, role, phone, lang, ch, skills, tools, mins in members_spec:
        m = Member(
            shg_id=shg.id,
            name=name,
            role=role,
            phone_enc=phone,
            phone_hash=blind_index(phone),
            preferred_language=lang,
            default_channel=ch,
            skills=skills,
            tools=tools,
            available_minutes_per_day=mins,
            bank_account_enc="XXXX1234",
            ifsc_enc="SBIN0001234",
        )
        db.add(m)
        db.flush()
        if role == "leader":
            leader_id = m.id

    buyer = Party(
        party_type="buyer",
        name="Deccan Craft Collective",
        phone_enc="+919900000099",
        phone_hash=blind_index("+919900000099"),
        preferred_language="en",
    )
    db.add(buyer)
    db.flush()

    t_scissors = Tool(name="scissors")
    t_machine = Tool(name="sewing_machine")
    mat_cotton = Material(name="Organic Cotton Canvas", unit="meters", unit_cost_inr=65.0)
    db.add_all([t_scissors, t_machine, mat_cotton])
    db.flush()

    db.add(Inventory(shg_id=shg.id, material_id=mat_cotton.id, quantity_on_hand=500.0))

    prod = Product(
        sku="TOTE-COT-01",
        name="Cotton Tote Bag",
        aliases=["tote bag", "cotton bag", "tote bags"],
        category="stitching",
        unit="piece",
    )
    db.add(prod)
    db.flush()

    t_cut = TaskTemplate(
        product_id=prod.id, step_name="cut", sequence_order=1, minutes_per_unit=6.0, required_skill="cutting", piece_rate_inr=8.0
    )
    t_stitch = TaskTemplate(
        product_id=prod.id,
        step_name="stitch",
        sequence_order=2,
        depends_on_step_name="cut",
        minutes_per_unit=14.0,
        required_skill="stitching",
        piece_rate_inr=22.0,
    )
    t_qc = TaskTemplate(
        product_id=prod.id,
        step_name="check_and_pack",
        sequence_order=3,
        depends_on_step_name="stitch",
        minutes_per_unit=4.0,
        required_skill="qc",
        piece_rate_inr=6.0,
    )
    db.add_all([t_cut, t_stitch, t_qc])
    db.flush()

    db.add_all(
        [
            TemplateRequirement(task_template_id=t_cut.id, requirement_type="tool", tool_id=t_scissors.id, quantity_per_unit=1),
            TemplateRequirement(task_template_id=t_cut.id, requirement_type="material", material_id=mat_cotton.id, quantity_per_unit=0.6),
            TemplateRequirement(task_template_id=t_stitch.id, requirement_type="tool", tool_id=t_machine.id, quantity_per_unit=1),
            PriceModel(product_id=prod.id, hourly_wage_benchmark_inr=75.0, overhead_pct=0.12, target_margin_pct=0.15),
        ]
    )
    db.flush()

    # Seed one sample DRAFT order so first-time onboarding immediately shows live data
    from app.adapters.channels.base import NormalizedInbound
    from app.adapters.lyzr.orchestrator import run_intake_pipeline

    sample_inbound = NormalizedInbound(
        channel="whatsapp_smartphone",
        provider_message_id="seed-demo-msg-1",
        sender_phone="+919900000099",
        raw_text="New order: 30 Cotton Tote Bag pieces at Rs 185 per piece, due in 12 days",
    )
    run_intake_pipeline(db, shg_id=shg.id, inbound=sample_inbound, buyer_party_id_hint=buyer.id)

    seed_demo_conversations(db, shg)
    db.commit()
    return {"shg_id": shg.id, "leader_id": leader_id, "buyer_party_id": buyer.id}
