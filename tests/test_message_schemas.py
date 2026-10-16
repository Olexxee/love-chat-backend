from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.message import (
    CreateMessageRequest,
    MessageResponse,
)


def test_message_request_defaults_to_textless_message_for_attachment_flow():
    request = CreateMessageRequest(attachment_ids=[1])

    assert request.content == ""
    assert request.attachment_ids == [1]
    assert request.client_message_id is None


def test_message_request_rejects_more_than_five_attachments():
    with pytest.raises(ValidationError):
        CreateMessageRequest(attachment_ids=[1, 2, 3, 4, 5, 6])


def test_message_request_rejects_client_ids_over_36_characters():
    with pytest.raises(ValidationError):
        CreateMessageRequest(content="hello", client_message_id="x" * 37)


def test_message_request_rejects_non_positive_reply_ids():
    with pytest.raises(ValidationError):
        CreateMessageRequest(content="hello", reply_to_message_id=0)


def test_message_response_accepts_canonical_message_payload():
    created_at = datetime.now(timezone.utc)
    payload = {
        "id": 12,
        "conversation_id": 4,
        "sender_id": 2,
        "client_message_id": "client-message-123",
        "content": "Hello",
        "created_at": created_at,
        "read_at": None,
        "deleted_at": None,
        "reply_to_message_id": None,
        "reply_to": None,
        "attachments": [],
    }

    response = MessageResponse.model_validate(payload)

    assert response.id == 12
    assert response.created_at == created_at
    assert response.attachments == []


def test_fastapi_application_imports_and_registers_health_route(monkeypatch):
    import importlib

    monkeypatch.setenv("DATABASE_URL", "sqlite:///./lovechat-test.db")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-only-secret-key")

    app_module = importlib.import_module("app.main")
    paths = {
        path
        for route in app_module.app.routes
        if (path := getattr(route, "path", None)) is not None
    }

    assert "/health" in paths
