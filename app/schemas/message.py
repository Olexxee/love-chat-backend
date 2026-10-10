from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateMessageRequest(BaseModel):
    content: str = Field(default="", max_length=5000)
    attachment_ids: list[int] = Field(default_factory=list, max_length=5)
    client_message_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=36,
    )


class MessageAttachmentResponse(BaseModel):
    id: int
    media_asset_id: int
    secure_url: str
    format: str | None = None
    width: int | None = None
    height: int | None = None

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    client_message_id: str | None = None
    content: str
    created_at: datetime
    read_at: datetime | None
    deleted_at: datetime | None
    attachments: list[MessageAttachmentResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
