from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MediaResponse(BaseModel):
    id: int
    purpose: str
    resource_type: str
    secure_url: str
    format: str | None
    width: int | None
    height: int | None
    size_bytes: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
