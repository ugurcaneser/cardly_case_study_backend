from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from sqlmodel import func, select

from app.api.deps import DeviceIdDep, SessionDep
from app.db.models import Card, Collection, CollectionCard
from app.schemas.collection import (
    CollectionCreate,
    CollectionDetail,
    CollectionRead,
    CollectionUpdate,
)

router = APIRouter(prefix="/collections", tags=["collections"])


def _get_collection_or_404(collection_id: int, device_id: str, session: SessionDep) -> Collection:
    collection = session.exec(
        select(Collection).where(Collection.id == collection_id, Collection.user_id == device_id)
    ).first()
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return collection


def _get_card_or_404(card_id: int, device_id: str, session: SessionDep) -> Card:
    card = session.exec(
        select(Card).where(Card.id == card_id, Card.user_id == device_id)
    ).first()
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    return card


def _card_count(collection_id: int, session: SessionDep) -> int:
    return session.exec(
        select(func.count()).select_from(CollectionCard).where(
            CollectionCard.collection_id == collection_id
        )
    ).one()


@router.post("", response_model=CollectionRead, status_code=status.HTTP_201_CREATED)
def create_collection(payload: CollectionCreate, session: SessionDep, device_id: DeviceIdDep) -> CollectionRead:
    existing = session.exec(
        select(Collection).where(Collection.name == payload.name, Collection.user_id == device_id)
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Collection name already exists")

    collection = Collection(name=payload.name, user_id=device_id)
    session.add(collection)
    session.commit()
    session.refresh(collection)
    return CollectionRead(**collection.model_dump(), card_count=0)


@router.get("", response_model=list[CollectionRead])
def list_collections(session: SessionDep, device_id: DeviceIdDep) -> list[CollectionRead]:
    statement = (
        select(Collection, func.count(CollectionCard.card_id))
        .join(CollectionCard, CollectionCard.collection_id == Collection.id, isouter=True)
        .where(Collection.user_id == device_id)
        .group_by(Collection.id)
        .order_by(Collection.created_at.desc())
    )
    results = session.exec(statement).all()
    return [
        CollectionRead(**collection.model_dump(), card_count=count)
        for collection, count in results
    ]


@router.get("/{collection_id}", response_model=CollectionDetail)
def get_collection(collection_id: int, session: SessionDep, device_id: DeviceIdDep) -> CollectionDetail:
    collection = _get_collection_or_404(collection_id, device_id, session)

    statement = (
        select(Card)
        .join(CollectionCard, CollectionCard.card_id == Card.id)
        .where(CollectionCard.collection_id == collection_id)
        .order_by(Card.created_at.desc())
    )
    cards = session.exec(statement).all()
    return CollectionDetail(**collection.model_dump(), card_count=len(cards), cards=cards)


@router.patch("/{collection_id}", response_model=CollectionRead)
def rename_collection(
    collection_id: int, payload: CollectionUpdate, session: SessionDep, device_id: DeviceIdDep
) -> CollectionRead:
    collection = _get_collection_or_404(collection_id, device_id, session)

    name_taken = session.exec(
        select(Collection).where(
            Collection.name == payload.name,
            Collection.user_id == device_id,
            Collection.id != collection_id,
        )
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
def delete_collection(collection_id: int, session: SessionDep, device_id: DeviceIdDep) -> None:
    collection = _get_collection_or_404(collection_id, device_id, session)
    session.delete(collection)
    session.commit()


@router.post("/{collection_id}/cards/{card_id}", response_model=CollectionDetail, status_code=status.HTTP_201_CREATED)
def add_card_to_collection(
    collection_id: int, card_id: int, session: SessionDep, device_id: DeviceIdDep
) -> CollectionDetail:
    _get_collection_or_404(collection_id, device_id, session)
    _get_card_or_404(card_id, device_id, session)

    existing = session.get(CollectionCard, (collection_id, card_id))
    if existing is None:
        session.add(CollectionCard(collection_id=collection_id, card_id=card_id))
        session.commit()

    return get_collection(collection_id, session, device_id)


@router.delete("/{collection_id}/cards/{card_id}", response_model=CollectionDetail)
def remove_card_from_collection(
    collection_id: int, card_id: int, session: SessionDep, device_id: DeviceIdDep
) -> CollectionDetail:
    _get_collection_or_404(collection_id, device_id, session)

    membership = session.get(CollectionCard, (collection_id, card_id))
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card is not in this collection")

    session.delete(membership)
    session.commit()
    return get_collection(collection_id, session, device_id)
