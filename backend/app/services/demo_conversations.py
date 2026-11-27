"""Illustrative workshop discussions confined to the original seeded demo order."""

from datetime import timedelta

from sqlalchemy import select

from app.models.base import utc_now
from app.models.communications import Conversation, ConversationMessage
from app.models.intake import InboundMessage, Order
from app.models.people import Member
from app.services.conversations import add_participant, conversation_id, insert_for, link_order


def seed_demo_conversations(db, group):
    channel = "whatsapp_smartphone"
    main_id = conversation_id(group.id, channel, "demo/workshop")
    if db.get(Conversation, main_id):
        return
    order = db.scalar(select(Order).join(InboundMessage, InboundMessage.id == Order.source_message_id)
        .where(Order.shg_id == group.id, InboundMessage.provider_message_id == "seed-demo-msg-1"))
    if not order:
        return
    members = {m.name: m for m in db.scalars(select(Member).where(Member.shg_id == group.id, Member.is_active.is_(True)))}
    names = ["Lakshmi Devi", "Savitha N", "Geeta Bai", "Anita Kumari", "Radhaamma"]
    if not all(name in members for name in names):
        return
    leader, savitha, geeta, anita, radha = names
    groups = [
        ("packing", "Packing team", [leader, radha, anita], [
            (radha, "The packing labels are ready for collection.", "tasks", 1450)]),
        ("materials", "Materials circle", [leader, geeta], [
            (geeta, "The canvas swatches are at the workshop.", "general", 230)]),
        ("quality", "Quality circle", [leader, radha, savitha], [
            (radha, "I’ll check the seams before we pack the first batch.", "tasks", 105)]),
        ("workshop", group.name, names, [
            (geeta, "Could we get two more rolls of lining fabric for the tote bags?", "orders", 42),
            (leader, "I’ll arrange the lining today and update the order.", "orders", 34),
            (savitha, "The first tote sample is stitched. Here’s the seam detail.", "tasks", 0)]),
    ]
    # The sample photo uses the built-in image generator with this prompt:
    # Photorealistic workshop phone snapshot, landscape 3:2. Close-up of a tan woven cotton canvas tote bag
    # with a diagonal double-stitched seam, a folded cotton handle at the edge and warm natural window light.
    # Fabric fills the frame. No text, hands or logos.
    now = utc_now()
    for key, title, people, messages in groups:
        tid = conversation_id(group.id, channel, f"demo/{key}")
        db.execute(insert_for(db, Conversation).values(id=tid, shg_id=group.id, channel=channel,
            title=title, kind="workspace", is_demo=True).on_conflict_do_nothing())
        for name in people:
            add_participant(db, tid, members[name])
        if key in ("quality", "workshop"):
            link_order(db, tid, order.id)
        for i, (name, body, topic, minutes_ago) in enumerate(messages):
            db.execute(insert_for(db, ConversationMessage).values(conversation_id=tid, source_key=f"demo/{tid}/{i}",
                direction="outgoing" if name == leader else "incoming", sender=name, body=body, topic=topic,
                sample_photo=key == "workshop" and name == savitha, created_at=now - timedelta(minutes=minutes_ago)).on_conflict_do_nothing())
