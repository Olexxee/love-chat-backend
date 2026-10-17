from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.enums import RelationshipStatus
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


def _get_avatar_url(db: Session, user_id: int) -> str | None:
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    if profile is None or profile.avatar_media_id is None:
        return None
    avatar = db.scalar(
        select(MediaAsset).where(
            MediaAsset.id == profile.avatar_media_id,
            MediaAsset.deleted_at.is_(None),
        )
    )
    return avatar.secure_url if avatar else None


def _serialize_relationship(
    db: Session,
    relationship: Relationship,
    current_user: User,
) -> dict:
    partner_id = _get_partner_id(relationship, current_user)
    partner = db.get(User, partner_id)
    conversation = db.scalar(
        select(Conversation).where(Conversation.relationship_id == relationship.id)
    )
    if partner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Relationship partner not found.",
        )
    return {
        "id": relationship.id,
        "user_one_id": relationship.user_one_id,
        "user_two_id": relationship.user_two_id,
        "requested_by_id": relationship.requested_by_id,
        "relationship_type": relationship.relationship_type,
        "status": relationship.status,
        "created_at": relationship.created_at,
        "responded_at": relationship.responded_at,
        "conversation_id": conversation.id if conversation else None,
        "partner": {
            "id": partner.id,
            "name": partner.name,
            "avatar_url": _get_avatar_url(db, partner.id),
        },
    }


def search_users(db: Session, current_user: User, query: str) -> list[dict]:
    term = query.strip()
    if len(term) < 2:
        return []
    pattern = f"%{term}%"
    users = db.scalars(
        select(User)
        .where(
            User.id != current_user.id,
            User.is_active.is_(True),
            or_(User.name.ilike(pattern), User.email.ilike(pattern)),
        )
        .order_by(User.name.asc())
        .limit(20)
    ).all()
    return [
        {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "avatar_url": _get_avatar_url(db, user.id),
        }
        for user in users
    ]


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
        partners = db.scalars(
            select(User).where(User.name.ilike(identifier), User.is_active.is_(True))
        ).all()
        if len(partners) > 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Multiple users found. Search and select the correct person.",
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

    user_one_id, user_two_id = sorted([current_user.id, partner.id])
    existing = db.scalar(
        select(Relationship).where(
            Relationship.user_one_id == user_one_id,
            Relationship.user_two_id == user_two_id,
        )
    )
    now = datetime.now(timezone.utc)

    try:
        if existing is not None:
            if existing.status == RelationshipStatus.PENDING.value:
                detail = (
                    "You already sent this person a request."
                    if existing.requested_by_id == current_user.id
                    else "This person has already sent you a request. Accept or decline it from Requests."
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=detail,
                )
            if existing.status == RelationshipStatus.ACTIVE.value:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="You are already connected.",
                )
            if existing.status == RelationshipStatus.ENDED.value:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This relationship has ended and cannot be requested again.",
                )
            if (
                existing.status == RelationshipStatus.DECLINED.value
                and existing.requested_by_id == current_user.id
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Your previous request was declined.",
                )

            # A declined request can be initiated by the other person.
            existing.requested_by_id = current_user.id
            existing.relationship_type = data.relationship_type.value
            existing.status = RelationshipStatus.PENDING.value
            existing.responded_at = None
            existing.declined_at = None
            relationship = existing
        else:
            relationship = Relationship(
                user_one_id=user_one_id,
                user_two_id=user_two_id,
                requested_by_id=current_user.id,
                relationship_type=data.relationship_type.value,
                status=RelationshipStatus.PENDING.value,
            )
            db.add(relationship)
            db.flush()

        result = _serialize_relationship(db, relationship, current_user)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def respond_to_relationship(
    db: Session,
    current_user: User,
    relationship_id: int,
    accept: bool,
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
            detail="Relationship request not found.",
        )
    if relationship.status != RelationshipStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This request has already been answered or is no longer pending.",
        )
    if relationship.requested_by_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot respond to a request you sent.",
        )

    try:
        now = datetime.now(timezone.utc)
        if accept:
            relationship.status = RelationshipStatus.ACTIVE.value
            relationship.responded_at = now
            conversation = db.scalar(
                select(Conversation).where(
                    Conversation.relationship_id == relationship.id
                )
            )
            if conversation is None:
                db.add(Conversation(relationship_id=relationship.id))
                db.flush()
        else:
            relationship.status = RelationshipStatus.DECLINED.value
            relationship.responded_at = now
            relationship.declined_at = now

        result = _serialize_relationship(db, relationship, current_user)
        db.commit()
        return result
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


def list_relationships(db: Session, current_user: User) -> list[dict]:
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
    return _serialize_relationship(db, relationship, current_user)


def get_relationship_partner(
    db: Session,
    relationship: Relationship,
    current_user: User,
) -> User:
    partner_id = _get_partner_id(relationship, current_user)
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
        .join(Relationship, Conversation.relationship_id == Relationship.id)
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
    partner = get_relationship_partner(db, relationship, current_user)
    return conversation, relationship, partner


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
    if relationship.status == RelationshipStatus.ENDED.value:
        return
    try:
        relationship.status = RelationshipStatus.ENDED.value
        db.commit()
    except Exception:
        db.rollback()
        raise
