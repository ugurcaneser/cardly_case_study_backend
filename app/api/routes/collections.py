from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from sqlmodel import func, select

from app.api.deps import SessionDep
from app.db.models import Card, Collection, CollectionCard
from app.schemas.collection import (
    CollectionCreate,
    CollectionDetail,
    CollectionRead,
    CollectionUpdate,
)

router = APIRouter(prefix="/collections", tags=["collections"])


def _get_collection_or_404(collection_id: int, session: SessionDep) -> Collection:
    collection = session.get(Collection, collection_id)
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return collection


def _card_count(collection_id: int, session: SessionDep) -> int:
    return session.exec(
        select(func.count()).select_from(CollectionCard).where(
            CollectionCard.collection_id == collection_id
        )
    ).one()


@router.post("", response_model=CollectionRead, status_code=status.HTTP_201_CREATED)
def create_collection(payload: CollectionCreate, session: SessionDep) -> CollectionRead:
    existing = session.exec(select(Collection).where(Collection.name == payload.name)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Collection name already exists")

    collection = Collection(name=payload.name)
    session.add(collection)
    session.commit()
    session.refresh(collection)
    return CollectionRead(**collection.model_dump(), card_count=0)


@router.get("", response_model=list[CollectionRead])
def list_collections(session: SessionDep) -> list[CollectionRead]:
    statement = (
        select(Collection, func.count(CollectionCard.card_id))
        .join(CollectionCard, CollectionCard.collection_id == Collection.id, isouter=True)
        .group_by(Collection.id)
        .order_by(Collection.created_at.desc())
    )
    results = session.exec(statement).all()
    return [
        CollectionRead(**collection.model_dump(), card_count=count)
        for collection, count in results
    ]


@router.get("/{collection_id}", response_model=CollectionDetail)
def get_collection(collection_id: int, session: SessionDep) -> CollectionDetail:
    collection = _get_collection_or_404(collection_id, session)

    statement = (
        select(Card)
        .join(CollectionCard, CollectionCard.card_id == Card.id)
        .where(CollectionCard.collection_id == collection_id)
        .order_by(Card.created_at.desc())
    )
    cards = session.exec(statement).all()
    return CollectionDetail(**collection.model_dump(), card_count=len(cards), cards=cards)


@router.patch("/{collection_id}", response_model=CollectionRead)
def rename_collection(collection_id: int, payload: CollectionUpdate, session: SessionDep) -> CollectionRead:
    collection = _get_collection_or_404(collection_id, session)

    name_taken = session.exec(
        select(Collection).where(Collection.name == payload.name, Collection.id != collection_id)
    ).first()
    if name_taken:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Collection name already exists")

    collection.name = payload.name
    collection.updated_at = datetime.utcnow()
    session.add(collection)
    session.commit()
    session.refresh(collection)
    return CollectionRead(**collection.model_dump(), card_count=_card_count(collection_id, session))


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(collection_id: int, session: SessionDep) -> None:
    collection = _get_collection_or_404(collection_id, session)
    session.delete(collection)
    session.commit()


@router.post("/{collection_id}/cards/{card_id}", response_model=CollectionDetail, status_code=status.HTTP_201_CREATED)
def add_card_to_collection(collection_id: int, card_id: int, session: SessionDep) -> CollectionDetail:
    _get_collection_or_404(collection_id, session)
    card = session.get(Card, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

    existing = session.get(CollectionCard, (collection_id, card_id))
    if existing is None:
        session.add(CollectionCard(collection_id=collection_id, card_id=card_id))
        session.commit()

    return get_collection(collection_id, session)


@router.delete("/{collection_id}/cards/{card_id}", response_model=CollectionDetail)
def remove_card_from_collection(collection_id: int, card_id: int, session: SessionDep) -> CollectionDetail:
    _get_collection_or_404(collection_id, session)

    membership = session.get(CollectionCard, (collection_id, card_id))
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card is not in this collection")

    session.delete(membership)
    session.commit()
    return get_collection(collection_id, session)
