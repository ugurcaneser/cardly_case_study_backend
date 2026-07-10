from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.card import CardRead


class CollectionCreate(BaseModel):
    name: str


class CollectionUpdate(BaseModel):
    name: str


class CollectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    card_count: int


class CollectionDetail(CollectionRead):
    cards: list[CardRead]
