from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.enums import RelationshipStatus, RelationshipType
from app.db.models import (
    Conversation,
    MediaAsset,
    Relationship,
    User,
    UserProfile,
)
from app.schemas.relationship import CreateRelationshipRequest


def _get_partner_id(
    relationship: Relationship,
    current_user: User,
) -> int:
    if relationship.user_one_id == current_user.id:
        return relationship.user_two_id

    if relationship.user_two_id == current_user.id:
        return relationship.user_one_id

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not belong to this relationship.",
    )


def _serialize_relationship(
    db: Session,
    relationship: Relationship,
    current_user: User,
) -> dict:
    partner_id = _get_partner_id(relationship, current_user)

    partner = db.scalar(select(User).where(User.id == partner_id))

    conversation = db.scalar(
        select(Conversation).where(Conversation.relationship_id == relationship.id)
    )

    if partner is None or conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship or conversation not found.",
        )

    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == partner.id))

    avatar_url = None

    if profile and profile.avatar_media_id:
        avatar = db.scalar(
            select(MediaAsset).where(
                MediaAsset.id == profile.avatar_media_id,
                MediaAsset.deleted_at.is_(None),
            )
        )

        if avatar:
            avatar_url = avatar.secure_url

    return {
        "id": relationship.id,
        "user_one_id": relationship.user_one_id,
        "user_two_id": relationship.user_two_id,
        "relationship_type": relationship.relationship_type,
        "status": relationship.status,
        "created_at": relationship.created_at,
        "conversation_id": conversation.id,
        "partner": {
            "id": partner.id,
            "name": partner.name,
            "avatar_url": avatar_url,
        },
    }


def create_relationship(
    db: Session,
    current_user: User,
    data: CreateRelationshipRequest,
) -> dict:
    identifier = data.identifier.strip()

    if not identifier:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter a name or email address.",
        )

    if "@" in identifier:
        partner = db.scalar(select(User).where(User.email == identifier.lower()))
    else:
        partners = db.scalars(select(User).where(User.name.ilike(identifier))).all()

        if len(partners) > 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Multiple users found. Search using their email address.",
            )

        partner = partners[0] if partners else None

    if partner is None or not partner.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if partner.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot create a relationship with yourself.",
        )

    # Canonical ordering ensures A-B and B-A use the same pair.
    user_one_id, user_two_id = sorted([current_user.id, partner.id])

    existing = db.scalar(
        select(Relationship).where(
            Relationship.user_one_id == user_one_id,
            Relationship.user_two_id == user_two_id,
        )
    )

    # ---- NEW: reactivate an ENDED relationship instead of 409-ing ----
    if existing is not None:
        if existing.status != RelationshipStatus.ENDED.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A relationship already exists between these users.",
            )

        existing.status = RelationshipStatus.ACTIVE.value
        existing.relationship_type = data.relationship_type.value

        try:
            result = _serialize_relationship(db, existing, current_user)
            db.commit()
            return result
        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

    try:
        relationship = Relationship(
            user_one_id=user_one_id,
            user_two_id=user_two_id,
            relationship_type=data.relationship_type.value,
            # ---- NEW: use the enum, not a hardcoded string ----
            status=RelationshipStatus.ACTIVE.value,
        )

        db.add(relationship)
        db.flush()

        conversation = Conversation(relationship_id=relationship.id)

        db.add(conversation)
        db.flush()

        result = _serialize_relationship(
            db,
            relationship,
            current_user,
        )

        db.commit()
        return result

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def list_relationships(
    db: Session,
    current_user: User,
) -> list[dict]:
    relationships = db.scalars(
        select(Relationship)
        .where(
            or_(
                Relationship.user_one_id == current_user.id,
                Relationship.user_two_id == current_user.id,
            )
        )
        .order_by(Relationship.created_at.desc())
    ).all()

    return [
        _serialize_relationship(db, relationship, current_user)
        for relationship in relationships
    ]


def get_relationship_by_id(
    db: Session,
    current_user: User,
    relationship_id: int,
) -> dict:
    relationship = db.scalar(
        select(Relationship).where(
            Relationship.id == relationship_id,
            or_(
                Relationship.user_one_id == current_user.id,
                Relationship.user_two_id == current_user.id,
            ),
        )
    )

    if relationship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found.",
        )

    return _serialize_relationship(
        db,
        relationship,
        current_user,
    )


def get_relationship_partner(
    db: Session,
    relationship: Relationship,
    current_user: User,
) -> User:
    partner_id = _get_partner_id(
        relationship,
        current_user,
    )

    partner = db.get(User, partner_id)

    if partner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship partner not found.",
        )

    return partner


def get_conversation_for_relationship(
    db: Session,
    current_user: User,
    relationship_id: int,
) -> Conversation:
    relationship = db.scalar(
        select(Relationship).where(
            Relationship.id == relationship_id,
            or_(
                Relationship.user_one_id == current_user.id,
                Relationship.user_two_id == current_user.id,
            ),
            Relationship.status == RelationshipStatus.ACTIVE.value,
        )
    )

    if relationship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active relationship not found.",
        )

    conversation = db.scalar(
        select(Conversation).where(Conversation.relationship_id == relationship.id)
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    return conversation


def get_authorized_conversation(
    db: Session,
    current_user: User,
    conversation_id: int,
) -> tuple[Conversation, Relationship, User]:
    result = db.execute(
        select(Conversation, Relationship)
        .join(
            Relationship,
            Conversation.relationship_id == Relationship.id,
        )
        .where(
            Conversation.id == conversation_id,
            Relationship.status == RelationshipStatus.ACTIVE.value,
            or_(
                Relationship.user_one_id == current_user.id,
                Relationship.user_two_id == current_user.id,
            ),
        )
    ).first()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    conversation, relationship = result

    partner = get_relationship_partner(
        db,
        relationship,
        current_user,
    )

    return conversation, relationship, partner


# ---- NEW: end (soft-delete) a relationship ----
def end_relationship(
    db: Session,
    current_user: User,
    relationship_id: int,
) -> None:
    relationship = db.scalar(
        select(Relationship).where(
            Relationship.id == relationship_id,
            or_(
                Relationship.user_one_id == current_user.id,
                Relationship.user_two_id == current_user.id,
            ),
        )
    )

    if relationship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship not found.",
        )

    # Idempotent — hitting DELETE twice is fine.
    if relationship.status == RelationshipStatus.ENDED.value:
        return

    try:
        relationship.status = RelationshipStatus.ENDED.value
        db.commit()
    except Exception:
        db.rollback()
        raise
