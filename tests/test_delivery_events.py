from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.models import Conversation, DeliveryEvent, Relationship, User
from app.services.message import delete_message, get_messages, mark_message_as_read, send_message


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)

    first = User(name="First", email="first@example.com", password_hash="hash")
    second = User(name="Second", email="second@example.com", password_hash="hash")
    session.add_all([first, second])
    session.flush()

    relationship = Relationship(
        user_one_id=first.id,
        user_two_id=second.id,
        requested_by_id=first.id,
        relationship_type="ROMANTIC",
        status="ACTIVE",
    )
    session.add(relationship)
    session.flush()
    conversation = Conversation(relationship_id=relationship.id)
    session.add(conversation)
    session.commit()
    return engine, session, first, second, conversation


def test_message_history_is_paginated_and_delivery_events_are_persisted():
    engine, db, first, _, conversation = make_session()
    try:
        first_message = send_message(
            db, first, conversation.id, "one", client_message_id="client-1"
        )
        second_message = send_message(
            db, first, conversation.id, "two", client_message_id="client-2"
        )
        third_message = send_message(
            db, first, conversation.id, "three", client_message_id="client-3"
        )

        first_page = get_messages(db, first, conversation.id, limit=2)
        assert [item["content"] for item in first_page] == ["two", "three"]

        older_page = get_messages(
            db, first, conversation.id, before_id=first_page[0]["id"], limit=2
        )
        assert [item["content"] for item in older_page] == ["one"]

        events = db.scalars(
            select(DeliveryEvent)
            .where(DeliveryEvent.conversation_id == conversation.id)
            .order_by(DeliveryEvent.id.asc())
        ).all()
        assert [event.event_type for event in events] == ["message", "message", "message"]
        assert events[-1].payload["message"]["content"] == "three"
        assert first_message["event_id"] < second_message["event_id"] < third_message["event_id"]
    finally:
        db.close()
        engine.dispose()


def test_read_and_delete_actions_are_recorded_for_recovery():
    engine, db, first, second, conversation = make_session()
    try:
        sent = send_message(
            db, first, conversation.id, "persist this", client_message_id="client-4"
        )
        read = mark_message_as_read(db, second, sent["id"])
        deleted = delete_message(db, first, sent["id"])

        assert read["event_id"] > sent["event_id"]
        assert deleted["event_id"] > read["event_id"]
        event_types = db.scalars(
            select(DeliveryEvent.event_type)
            .where(DeliveryEvent.conversation_id == conversation.id)
            .order_by(DeliveryEvent.id.asc())
        ).all()
        assert event_types == ["message", "message_read", "message_deleted"]
    finally:
        db.close()
        engine.dispose()
