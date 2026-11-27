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
