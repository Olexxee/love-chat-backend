from enum import Enum


class RelationshipType(str, Enum):
    ROMANTIC = "ROMANTIC"
    FRIEND = "FRIEND"
    FAMILY = "FAMILY"
    OTHER = "OTHER"


class RelationshipStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    DECLINED = "DECLINED"
    ENDED = "ENDED"


class MediaProvider(str, Enum):
    CLOUDINARY = "CLOUDINARY"


class MediaResourceType(str, Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    RAW = "RAW"


class MediaPurpose(str, Enum):
    AVATAR = "AVATAR"
    CHAT_ATTACHMENT = "CHAT_ATTACHMENT"
    OTHER = "OTHER"
