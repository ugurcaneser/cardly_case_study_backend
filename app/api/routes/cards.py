from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.api.deps import DeviceIdDep, SessionDep
from app.db.models import Card
from app.schemas.card import CardCreate, CardRead

router = APIRouter(prefix="/cards", tags=["cards"])


def _get_card_or_404(card_id: int, device_id: str, session: SessionDep) -> Card:
    card = session.exec(
        select(Card).where(Card.id == card_id, Card.user_id == device_id)
    ).first()
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    return card


@router.post("", response_model=CardRead, status_code=status.HTTP_201_CREATED)
def create_card(payload: CardCreate, session: SessionDep, device_id: DeviceIdDep) -> Card:
    card = Card(**payload.model_dump(), user_id=device_id)
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


@router.get("", response_model=list[CardRead])
def list_cards(session: SessionDep, device_id: DeviceIdDep) -> list[Card]:
    return session.exec(
        select(Card).where(Card.user_id == device_id).order_by(Card.created_at.desc())
    ).all()


@router.get("/{card_id}", response_model=CardRead)
def get_card(card_id: int, session: SessionDep, device_id: DeviceIdDep) -> Card:
    return _get_card_or_404(card_id, device_id, session)


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(card_id: int, session: SessionDep, device_id: DeviceIdDep) -> None:
    card = _get_card_or_404(card_id, device_id, session)
    session.delete(card)
    session.commit()
