"""Leader conversation summaries, cursor-based timelines and group notice history."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.api.deps import require_group_leader
from app.database import get_db
from app.models.catalogue import Product
from app.models.communications import (
    Conversation, ConversationMessage as Message, ConversationOrder,
    ConversationParticipant, ConversationRead,
)
from app.models.governance import CommsLog
from app.models.intake import InboundMessage, Order
from app.models.people import Member, Party
from app.services.conversations import insert_for, link_order

router = APIRouter(prefix="/api/leader/shgs/{shg_id}/communications", tags=["communications"])


def stamp(value: datetime) -> str:
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


def scoped_thread(
    conversation_id: str, leader: Member = Depends(require_group_leader), db: Session = Depends(get_db)
) -> Conversation:
    thread = db.get(Conversation, conversation_id)
    if not thread or thread.shg_id != leader.shg_id:
        raise HTTPException(404, "Conversation not found")
    return thread


@router.get("/conversations")
def inbox(
    q: str = Query("", max_length=500),
    leader: Member = Depends(require_group_leader),
    db: Session = Depends(get_db),
):
    unread = and_(Message.direction == "incoming", Message.position > func.coalesce(ConversationRead.position, 0))
    review = InboundMessage.is_quarantined.is_(True) | (InboundMessage.intent == "UNROUTED")
    records = (
        select(
            Message.conversation_id,
            func.max(Message.position).label("latest"),
            func.count().filter(unread).label("unread"),
            func.count().filter(review).label("review"),
            func.count().filter(Message.topic == "tasks").label("tasks"),
            func.count().filter(Message.topic == "orders").label("orders"),
            func.count().filter(Message.topic == "general").label("general"),
        )
        .join(Conversation, Conversation.id == Message.conversation_id)
        .outerjoin(ConversationRead, and_(
            ConversationRead.conversation_id == Conversation.id, ConversationRead.leader_id == leader.id
        ))
        .outerjoin(InboundMessage, InboundMessage.id == Message.inbound_id)
        .where(Conversation.shg_id == leader.shg_id)
        .group_by(Message.conversation_id)
        .subquery()
    )
    query = (
        select(Conversation, Message, records.c.unread, records.c.review, records.c.tasks, records.c.orders, records.c.general)
        .join(records, records.c.conversation_id == Conversation.id)
        .join(Message, Message.position == records.c.latest)
    )
    term = q.strip().lower()
    if term:
        history = (
            select(Message.position)
            .where(Message.conversation_id == Conversation.id, func.lower(Message.body).contains(term, autoescape=True))
            .correlate(Conversation).exists()
        )
        order_match = (
            select(ConversationOrder.order_id)
            .join(Order, Order.id == ConversationOrder.order_id)
            .where(ConversationOrder.conversation_id == Conversation.id, Order.shg_id == leader.shg_id,
                   func.lower(Order.order_code).contains(term, autoescape=True))
            .exists()
        )
        query = query.where(func.lower(Conversation.title).contains(term, autoescape=True) | history | order_match)

    linked_codes = {}
    order_links = (
        select(ConversationOrder.conversation_id, Order.order_code)
        .join(Order, Order.id == ConversationOrder.order_id)
        .join(Conversation, Conversation.id == ConversationOrder.conversation_id)
        .where(Conversation.shg_id == leader.shg_id, Order.shg_id == leader.shg_id)
    )
    for thread_id, code in db.execute(order_links):
        linked_codes.setdefault(thread_id, []).append(code)

    conversations = []
    for thread, last, unread_count, review_count, tasks, orders, general in db.execute(
        query.order_by(Message.created_at.desc(), Message.position.desc())
    ):
        codes = linked_codes.get(thread.id, [])
        topics = (("tasks", tasks), ("orders", orders or codes), ("general", general))
        conversations.append({
            "id": thread.id, "title": thread.title, "kind": thread.kind, "channel": thread.channel,
            "is_demo": thread.is_demo, "preview": last.body, "latest": last.position,
            "updated_at": stamp(last.created_at), "unread": unread_count, "needs_review": bool(review_count),
            "order_codes": codes, "topics": [name for name, present in topics if present],
        })
    return {"conversations": conversations}


@router.get("/conversations/{conversation_id}")
def timeline(
    thread: Conversation = Depends(scoped_thread),
    db: Session = Depends(get_db),
    before: int | None = Query(None, gt=0),
    limit: int = Query(40, ge=1, le=100),
):
    query = (
        select(Message, InboundMessage.is_quarantined, InboundMessage.intent)
        .outerjoin(InboundMessage, InboundMessage.id == Message.inbound_id)
        .where(Message.conversation_id == thread.id)
    )
    if before is not None:
        query = query.where(Message.position < before)
    rows = db.execute(query.order_by(Message.position.desc()).limit(limit + 1)).all()
    page = rows[:limit][::-1]

    participants = (
        select(Member.name, Party.name).select_from(ConversationParticipant)
        .outerjoin(Member, and_(Member.id == ConversationParticipant.member_id, Member.shg_id == thread.shg_id))
        .outerjoin(Party, Party.id == ConversationParticipant.party_id)
        .where(ConversationParticipant.conversation_id == thread.id)
        .order_by(Member.name, Party.name)
    )
    orders = (
        select(Order, Product.name)
        .join(ConversationOrder, ConversationOrder.order_id == Order.id)
        .outerjoin(Product, Product.id == Order.product_id)
        .where(ConversationOrder.conversation_id == thread.id, Order.shg_id == thread.shg_id)
        .order_by(Order.created_at.desc(), Order.id)
    )
    return {
        "id": thread.id,
        "participants": [member or party for member, party in db.execute(participants) if member or party],
        "orders": [
            {"id": order.id, "code": order.order_code, "product": product or order.spec_summary or "Order",
             "quantity": order.quantity, "status": order.status}
            for order, product in db.execute(orders)
        ],
        "before": page[0][0].position if len(rows) > limit else None,
        "messages": [
            {"position": message.position, "sender": message.sender, "direction": message.direction,
             "text": message.body, "created_at": stamp(message.created_at), "inbound_id": message.inbound_id,
             "quarantined": bool(quarantined), "needs_review": intent == "UNROUTED", "sample_photo": message.sample_photo}
            for message, quarantined, intent in page
        ],
    }


class ReadThrough(BaseModel):
    position: int


@router.put("/conversations/{conversation_id}/read")
def mark_read(
    body: ReadThrough, thread: Conversation = Depends(scoped_thread),
    leader: Member = Depends(require_group_leader), db: Session = Depends(get_db),
):
    message = db.get(Message, body.position)
    if not message or message.conversation_id != thread.id:
        raise HTTPException(422, "Read position must belong to this conversation")
    stmt = insert_for(db, ConversationRead).values(conversation_id=thread.id, leader_id=leader.id, position=body.position)
    db.execute(stmt.on_conflict_do_update(
        index_elements=["conversation_id", "leader_id"],
        set_={"position": body.position},
        where=ConversationRead.position < body.position,
    ))
    db.commit()
    return {"ok": True}


@router.put("/conversations/{conversation_id}/orders/{order_id}")
def attach_order(order_id: str, thread: Conversation = Depends(scoped_thread), db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order or order.shg_id != thread.shg_id:
        raise HTTPException(404, "Order not found")
    link_order(db, thread.id, order.id)
    db.commit()
    return {"order_id": order.id}


@router.get("/announcements")
def announcements(leader: Member = Depends(require_group_leader), db: Session = Depends(get_db)):
    query = (
        select(CommsLog)
        .where(CommsLog.shg_id == leader.shg_id, CommsLog.recipient_member_id == leader.id,
               CommsLog.message_category.in_(("GROUP_APPROVAL_BROADCAST", "GROUP_PAYOUT_NOTICE")))
        .order_by(CommsLog.created_at.desc(), CommsLog.id)
    )
    return {"announcements": [
        {"id": notice.id, "title": notice.fact_text, "text": " ".join((notice.action_text, notice.request_text)),
         "channel": notice.channel, "created_at": stamp(notice.created_at)}
        for notice in db.scalars(query)
    ]}
