from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from app.api.deps import SessionDep
from app.db.models import Card
from app.schemas.card import CardCreate, CardRead

router = APIRouter(prefix="/cards", tags=["cards"])


@router.post("", response_model=CardRead, status_code=status.HTTP_201_CREATED)
def create_card(payload: CardCreate, session: SessionDep) -> Card:
    card = Card(**payload.model_dump())
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


@router.get("", response_model=list[CardRead])
def list_cards(session: SessionDep) -> list[Card]:
    return session.exec(select(Card).order_by(Card.created_at.desc())).all()


@router.get("/{card_id}", response_model=CardRead)
def get_card(card_id: int, session: SessionDep) -> Card:
    card = session.get(Card, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    return card


@router.delete("/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(card_id: int, session: SessionDep) -> None:
    card = session.get(Card, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    session.delete(card)
    session.commit()
