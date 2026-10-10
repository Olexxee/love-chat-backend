from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import RelationshipType


class CreateRelationshipRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    relationship_type: RelationshipType = RelationshipType.ROMANTIC


class RelationshipPartnerResponse(BaseModel):
    id: int
    name: str
    avatar_url: str | None = None
    model_config = ConfigDict(from_attributes=True)


class RelationshipResponse(BaseModel):
    id: int
    user_one_id: int
    user_two_id: int
    relationship_type: RelationshipType
    status: str
    created_at: datetime
    conversation_id: int
    partner: RelationshipPartnerResponse

    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    id: int
    relationship_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
