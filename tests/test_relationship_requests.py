import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.models import Conversation, Relationship, User
from app.schemas.relationship import CreateRelationshipRequest
from app.services.relationship import (
    create_relationship,
    respond_to_relationship,
    search_users,
)


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    requester = User(name="Amina Yusuf", email="amina@example.com", password_hash="hash")
    recipient = User(name="Tunde Bello", email="tunde@example.com", password_hash="hash")
    other = User(name="Tunde Ade", email="tunde.ade@example.com", password_hash="hash")
    db.add_all([requester, recipient, other])
    db.commit()
    return engine, db, requester, recipient, other


def test_new_relationship_stays_pending_until_recipient_accepts():
    engine, db, requester, recipient, _ = make_session()
    try:
        result = create_relationship(
            db,
            requester,
            CreateRelationshipRequest(
                identifier=recipient.email,
                relationship_type="FRIEND",
            ),
        )

        relationship = db.get(Relationship, result["id"])
        assert relationship.status == "PENDING"
        assert relationship.requested_by_id == requester.id
        assert result["conversation_id"] is None
        assert db.scalar(select(Conversation)) is None

        with pytest.raises(HTTPException) as exc:
            respond_to_relationship(db, requester, relationship.id, accept=True)
        assert exc.value.status_code == 403
        db.rollback()

        accepted = respond_to_relationship(db, recipient, relationship.id, accept=True)
        assert accepted["status"] == "ACTIVE"
        assert accepted["conversation_id"] is not None
        assert db.scalar(select(Conversation)) is not None
    finally:
        db.close()
        engine.dispose()


def test_recipient_can_decline_request_without_creating_conversation():
    engine, db, requester, recipient, _ = make_session()
    try:
        created = create_relationship(
            db,
            requester,
            CreateRelationshipRequest(identifier=recipient.email),
        )
        declined = respond_to_relationship(db, recipient, created["id"], accept=False)
        assert declined["status"] == "DECLINED"
        assert declined["conversation_id"] is None
        assert db.scalar(select(Conversation)) is None
    finally:
        db.close()
        engine.dispose()


def test_user_search_matches_partial_name_and_email_and_excludes_current_user():
    engine, db, requester, recipient, _ = make_session()
    try:
        by_name = search_users(db, requester, "Tunde")
        assert {item["id"] for item in by_name} == {recipient.id}
        by_email = search_users(db, requester, "tunde@example")
        assert [item["email"] for item in by_email] == ["tunde@example.com"]
        assert search_users(db, requester, "a") == []
    finally:
        db.close()
        engine.dispose()
