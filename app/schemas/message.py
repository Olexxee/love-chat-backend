from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateMessageRequest(BaseModel):
    content: str = Field(default="", max_length=10000)
    attachment_ids: list[int] = Field(default_factory=list, max_length=5)
    client_message_id: str | None = Field(default=None, min_length=1, max_length=36)
    reply_to_message_id: int | None = Field(default=None, gt=0)

    model_config = ConfigDict(extra="forbid")


class MessageAttachmentResponse(BaseModel):
    id: int
    media_asset_id: int
    secure_url: str
    format: str | None = None
    width: int | None = None
    height: int | None = None


class ReplyToMessageResponse(BaseModel):
    id: int
    sender_id: int
    content: str
    deleted_at: datetime | None = None
    has_attachments: bool = False


class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    client_message_id: str | None = None
    content: str
    created_at: datetime
    read_at: datetime | None = None
    deleted_at: datetime | None = None
    reply_to_message_id: int | None = None
    reply_to: ReplyToMessageResponse | None = None
    attachments: list[MessageAttachmentResponse] = Field(default_factory=list)
