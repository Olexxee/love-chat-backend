from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.relationship import (
    CreateRelationshipRequest,
    RelationshipResponse,
    UserSearchResult,
)
from app.services.relationship import (
    create_relationship,
    end_relationship,
    get_relationship_by_id,
    list_relationships,
    respond_to_relationship,
    search_users,
)

router = APIRouter(
    prefix="/api/relationships",
    tags=["Relationships"],
)


@router.get("/search-users", response_model=list[UserSearchResult])
def search_relationship_users_route(
    q: str = Query(min_length=2, max_length=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return search_users(db, current_user, q)


@router.post(
    "",
    response_model=RelationshipResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_relationship_route(
    data: CreateRelationshipRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_relationship(db, current_user, data)


@router.get("", response_model=list[RelationshipResponse])
def list_relationships_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return list_relationships(db, current_user)


@router.post(
    "/{relationship_id}/accept",
    response_model=RelationshipResponse,
)
def accept_relationship_route(
    relationship_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return respond_to_relationship(db, current_user, relationship_id, accept=True)


@router.post(
    "/{relationship_id}/decline",
    response_model=RelationshipResponse,
)
def decline_relationship_route(
    relationship_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return respond_to_relationship(db, current_user, relationship_id, accept=False)


@router.get("/{relationship_id}", response_model=RelationshipResponse)
def get_relationship_route(
    relationship_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_relationship_by_id(db, current_user, relationship_id)


@router.delete("/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT)
def end_relationship_route(
    relationship_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    end_relationship(db, current_user, relationship_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
