from app.models.intake import InboundMessage, Order
from app.models.people import Member, SHG


def test_leader_inbox_links_orders_and_scopes_messages_to_group(client, db_session):
    leader = db_session.query(Member).filter_by(role="leader").one()
    order = db_session.query(Order).filter_by(shg_id=leader.shg_id).one()
    other = SHG(name="Other test group")
    db_session.add(other)
    db_session.flush()
    other_message = InboundMessage(shg_id=other.id, channel="janai_cafe", raw_text="Other group update")
    db_session.add(other_message)
    db_session.commit()

    inbox = f"/api/leader/shgs/{leader.shg_id}/communications"
    headers = {"X-Leader-Id": leader.id}
    assert client.get(inbox).status_code == 401
    assert client.get(f"/api/leader/shgs/{other.id}/communications", headers=headers).status_code == 403
    response = client.get(inbox, headers=headers)
    assert response.status_code == 200
    messages = response.json()["messages"]
    assert all(message["id"] != other_message.id for message in messages)
    message = next(message for message in messages if message["id"] == order.source_message_id)
    assert message["order_code"] == order.order_code
    assert message["order_id"] == order.id
    assert message["sender"]


def test_timeline_search_pagination_and_independent_read_positions(client, db_session):
    leader = db_session.query(Member).filter_by(role="leader").one()
    path = f"/api/leader/shgs/{leader.shg_id}/communications/conversations"
    headers = {"X-Leader-Id": leader.id}
    thread, = client.get(path, params={"q": "lining fabric"}, headers=headers).json()["conversations"]
    assert thread["unread"] == 2
    assert set(thread["topics"]) == {"orders", "tasks"}
    url = f"{path}/{thread['id']}"
    page = client.get(url, params={"limit": 2}, headers=headers).json()
    older = client.get(url, params={"before": page["before"], "limit": 2}, headers=headers).json()
    assert older["before"] is None
    first, second, third = [*older["messages"], *page["messages"]]
    assert first["position"] < second["position"] < third["position"]
    assert second["direction"] == "outgoing"
    assert len(page["participants"]) == 5

    def read(person, position):
        return client.put(url + "/read", headers={"X-Leader-Id": person}, json={"position": position})

    assert read(leader.id, third["position"]).is_success
    assert read(leader.id, first["position"]).is_success
    assert client.get(path, params={"q": "lining fabric"}, headers=headers).json()["conversations"][0]["unread"] == 0
    other = db_session.query(Member).filter_by(role="member").first()
    other.role = "leader"
    db_session.commit()
    theirs = {"X-Leader-Id": other.id}
    assert client.get(path, params={"q": "lining fabric"}, headers=theirs).json()["conversations"][0]["unread"] == 2
    assert client.get(path, params={"q": "%"}, headers=headers).json()["conversations"] == []


def test_linking_and_workspace_scope(client, db_session):
    from app.models.communications import Conversation
    leader = db_session.query(Member).filter_by(role="leader").one()
    other = SHG(name="Separate workspace")
    db_session.add(other)
    db_session.flush()
    foreign = Order(shg_id=other.id, order_code="FOREIGN-ORDER")
    foreign_thread = Conversation(shg_id=other.id, title="Private", kind="member", channel="basic_phone_voice")
    db_session.add_all([foreign, foreign_thread])
    db_session.commit()
    base = f"/api/leader/shgs/{leader.shg_id}/communications/conversations"
    h = {"X-Leader-Id": leader.id}
    assert client.get(base).status_code == 401
    assert client.get(f"{base}/{foreign_thread.id}", headers=h).status_code == 404
    threads = client.get(base, headers=h).json()["conversations"]
    assert all(t["id"] != foreign_thread.id for t in threads)
    url = base + "/" + next(t["id"] for t in threads if t["title"] == "Packing team")
    order = db_session.query(Order).filter_by(shg_id=leader.shg_id).one()
    assert client.put(f"{url}/orders/{foreign.id}", headers=h).status_code == 404
    assert client.put(f"{url}/orders/{order.id}", headers=h).is_success
    assert client.put(f"{url}/orders/{order.id}", headers=h).is_success
    assert [o["id"] for o in client.get(url, headers=h).json()["orders"]] == [order.id]
    assert client.put(url + "/read", headers=h, json={"position": next(t["latest"] for t in threads if t["title"] == "Quality circle")}).status_code == 422


def test_projection_for_existing_new_and_onboarded_contacts(client, db_session):
    from app.models.communications import ConversationMessage
    from app.services.conversations import backfill
    leader = db_session.query(Member).filter_by(role="leader").one()
    base = f"/api/leader/shgs/{leader.shg_id}/communications/conversations"
    h = {"X-Leader-Id": leader.id}
    incoming = {"shg_id": leader.shg_id, "sender_phone": "+919111222333", "text": "Sample packing question"}
    new = client.post("/api/webhooks/whatsapp", json=incoming).json()
    assert new["status"] == "QUARANTINED"
    candidate, = client.get(base, params={"q": "Sample packing"}, headers=h).json()["conversations"]
    thread = base + "/" + candidate["id"]
    assert client.get(thread, headers=h).json()["messages"][0]["quarantined"]
    identity = {"leader_id": leader.id, "name": "Workshop buyer", "phone": incoming["sender_phone"]}
    resp = client.post(f"/api/leader/quarantine/{new['inbound_message_id']}/onboard-buyer", headers=h, json=identity)
    assert resp.is_success
    client.post("/api/webhooks/whatsapp", json={**incoming, "text": "Another packing question"})
    assert client.get(thread, headers=h).json()["participants"] == ["Workshop buyer"]
    assert len(client.get(thread, headers=h).json()["messages"]) == 2
    for _ in range(2):
        backfill(db_session)
    db_session.commit()
    assert db_session.query(ConversationMessage).filter_by(conversation_id=candidate["id"]).count() == 2
    assert not client.get(thread, headers=h).json()["messages"][0]["quarantined"]


def test_group_notice_history_excludes_private_and_other_recipient_records(client, db_session):
    from app.models.governance import CommsLog
    leader = db_session.query(Member).filter_by(role="leader").one()
    member = db_session.query(Member).filter_by(role="member").first()
    for category, recipient in (("GROUP_PAYOUT_NOTICE", leader), ("EARNINGS_READBACK", leader), ("GROUP_PAYOUT_NOTICE", member)):
        db_session.add(CommsLog(shg_id=leader.shg_id, recipient_member_id=recipient.id, channel="basic_phone_voice",
            message_category=category, fact_text=f"{category}/{recipient.id}", action_text="Review", request_text="Confirm"))
    db_session.commit()
    url = f"/api/leader/shgs/{leader.shg_id}/communications/announcements"
    notices = client.get(url, headers={"X-Leader-Id": leader.id}).json()["announcements"]
    assert [n["title"] for n in notices] == [f"GROUP_PAYOUT_NOTICE/{leader.id}"]


def test_historical_messages_with_matching_display_names_have_separate_threads(client, db_session):
    from app.models.people import Party
    from app.services.conversations import backfill
    leader = db_session.query(Member).filter_by(role="leader").one()
    for body in ("Canvas sample", "Lining sample"):
        contact = Party(name="Workshop", party_type="buyer")
        db_session.add(contact)
        db_session.flush()
        db_session.add(InboundMessage(shg_id=leader.shg_id, channel="janai_cafe", sender_party_id=contact.id, raw_text=body))
    db_session.flush()
    backfill(db_session)
    db_session.commit()
    url = f"/api/leader/shgs/{leader.shg_id}/communications/conversations"
    headers = {"X-Leader-Id": leader.id}
    same_name = [t for t in client.get(url, headers=headers).json()["conversations"] if t["title"] == "Workshop"]
    assert len({t["id"] for t in same_name}) == 2
    assert {t["preview"] for t in same_name} == {"Canvas sample", "Lining sample"}
