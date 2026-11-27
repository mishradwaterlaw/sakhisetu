"""Project durable intake and eligible outbound records into the leader inbox."""

from heapq import merge
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.communications import Conversation, ConversationMessage, ConversationOrder, ConversationParticipant
from app.models.governance import CommsLog
from app.models.intake import InboundMessage, Order
from app.models.people import Member, Party


def insert_for(db, model):
    return (sqlite_insert if db.get_bind().dialect.name == "sqlite" else pg_insert)(model)


def conversation_id(shg_id, channel, identity):
    return str(uuid5(NAMESPACE_URL, f"sakhisetu/{shg_id}/{channel}/{identity}"))


def add_participant(db, thread_id, contact):
    is_member = isinstance(contact, Member)
    identity = ("member/" if is_member else "party/") + contact.id
    db.execute(insert_for(db, ConversationParticipant).values(
        conversation_id=thread_id, identity=identity,
        member_id=contact.id if is_member else None, party_id=None if is_member else contact.id,
    ).on_conflict_do_nothing())


def link_order(db, thread_id, order_id):
    db.execute(insert_for(db, ConversationOrder).values(conversation_id=thread_id, order_id=order_id).on_conflict_do_nothing())


def direct_thread_id(db, shg_id, channel, contact, phone, message_id=None):
    unidentified = conversation_id(shg_id, channel, f"phone/{phone}" if phone else f"message/{message_id}")
    if not contact:
        return unidentified
    # An onboarded sender can retain an existing quarantine thread, its order links
    # and its read markers. Registered contacts otherwise follow their stable ID.
    identity = ("member/" if isinstance(contact, Member) else "party/") + contact.id
    existing = db.scalar(select(Conversation.id).join(ConversationParticipant).where(
        Conversation.shg_id == shg_id, Conversation.channel == channel,
        Conversation.is_demo.is_(False), ConversationParticipant.identity == identity,
    ))
    if existing:
        return existing
    previous = db.get(Conversation, unidentified)
    if previous and previous.kind == "unknown":
        return previous.id
    return conversation_id(shg_id, channel, identity)


def project_inbound(db: Session, msg: InboundMessage):
    if not msg.shg_id:
        return
    member = db.get(Member, msg.sender_member_id) if msg.sender_member_id else None
    if member and member.shg_id != msg.shg_id:
        member = None
    party = db.get(Party, msg.sender_party_id) if msg.sender_party_id else None
    contact = member or party
    thread_id = direct_thread_id(db, msg.shg_id, msg.channel, contact, msg.sender_phone_hash, msg.id)
    name = contact.name if contact else "Unknown sender"
    kind = "member" if member else party.party_type if party else "unknown"
    stmt = insert_for(db, Conversation).values(id=thread_id, shg_id=msg.shg_id, channel=msg.channel, title=name, kind=kind)
    # Serialize writers per conversation so a read marker cannot overtake a pending insert.
    if contact:
        stmt = stmt.on_conflict_do_update(index_elements=["id"], set_={"title": name, "kind": kind})
    else:
        stmt = stmt.on_conflict_do_nothing()
    db.execute(stmt)
    db.execute(select(Conversation.id).where(Conversation.id == thread_id).with_for_update())
    if contact:
        add_participant(db, thread_id, contact)
    topic = "orders" if msg.intent == "NEW_ORDER" else "tasks" if msg.intent in ("BLOCKER_REPORT", "FINISHED_WORK") else "general"
    values = dict(conversation_id=thread_id, sender=name, body=msg.raw_text or msg.normalized_text or "Voice or media message", topic=topic)
    db.execute(insert_for(db, ConversationMessage).values(
        **values, source_key=f"in/{msg.id}", inbound_id=msg.id, direction="incoming", created_at=msg.created_at,
    ).on_conflict_do_update(index_elements=["source_key"], set_=values))
    for order_id in db.scalars(select(Order.id).where(Order.shg_id == msg.shg_id, Order.source_message_id == msg.id)):
        link_order(db, thread_id, order_id)
    return thread_id


def project_outbound(db, log):
    # Individual payout records stay in the member's private ledger.
    if log.message_category not in ("ONBOARDING", "CLARIFICATION") or not log.shg_id:
        return
    contact = db.get(Member, log.recipient_member_id) if log.recipient_member_id else None
    if contact and contact.shg_id != log.shg_id:
        return
    contact = contact or (db.get(Party, log.recipient_party_id) if log.recipient_party_id else None)
    if not contact:
        return
    is_member = isinstance(contact, Member)
    tid = direct_thread_id(db, log.shg_id, log.channel, contact, contact.phone_hash)
    db.execute(insert_for(db, Conversation).values(id=tid, shg_id=log.shg_id, channel=log.channel,
        title=contact.name, kind="member" if is_member else contact.party_type).on_conflict_do_nothing())
    db.execute(select(Conversation.id).where(Conversation.id == tid).with_for_update())
    add_participant(db, tid, contact)
    db.execute(insert_for(db, ConversationMessage).values(conversation_id=tid, source_key=f"out/{log.id}",
        direction="outgoing", sender="SakhiSetu", body=" ".join(filter(None, (log.fact_text, log.action_text, log.request_text))),
        created_at=log.created_at).on_conflict_do_nothing())


def backfill(db):
    # Insert historical messages in timestamp order, including outbound onboarding.
    incoming = select(InboundMessage.created_at, InboundMessage.id).where(InboundMessage.shg_id.is_not(None))
    outgoing = select(CommsLog.created_at, CommsLog.id).where(CommsLog.message_category.in_(("ONBOARDING", "CLARIFICATION")))
    for _, identifier, incoming_record in merge(
        ((t, i, True) for t, i in db.execute(incoming.order_by(InboundMessage.created_at, InboundMessage.id))),
        ((t, i, False) for t, i in db.execute(outgoing.order_by(CommsLog.created_at, CommsLog.id))),
    ):
        if incoming_record:
            project_inbound(db, db.get(InboundMessage, identifier))
        else:
            project_outbound(db, db.get(CommsLog, identifier))
